/**
 * Sending a large file straight to R2.
 *
 * The ordinary upload posts the whole file to Frappe, which holds it in memory,
 * writes it to disk and pushes it to R2 — fine for a photograph and hopeless for
 * a site video, which meets the request-body limit or the worker timeout long
 * before it finishes. This asks the server for signed URLs instead and PUTs the
 * bytes at Cloudflare itself; see `storage/direct.py` for the other half.
 *
 * `XMLHttpRequest` and not `fetch`, for one reason: `fetch` reports no progress
 * on an upload body. A progress bar that sits at zero for eleven minutes and
 * then jumps to done is worse than no bar, because the only thing a person
 * wants to know about a large upload is whether it is moving.
 *
 * Three parts at a time. One is slower than the link on any connection with
 * real latency; a dozen is the same total bandwidth split twelve ways, with
 * twelve chances to fail. Parts are retried individually — losing one of forty
 * to a dropped connection must not cost the other thirty-nine.
 */
import { call } from '@/ui'

const API = 'oneapp.oneapp_core.storage.direct'

/** Matches `direct.THRESHOLD`. Below it we do not even ask. */
export const THRESHOLD = 8 * 1024 * 1024

/** Parts in flight at once. */
const LANES = 3

/** Attempts per part before the whole upload fails. */
const TRIES = 3

/**
 * Put one file in R2 and make its `File` row.
 *
 * Returns the row, or `null` when this site cannot do it — no bucket, no
 * boto3, the control plane, or a file small enough that the ordinary POST is
 * the better trade. A `null` is not a failure: the caller falls back. Anything
 * that actually went wrong is thrown.
 */
export async function directUpload(file, options = {}) {
  const { folder = '', attachTo = null, private: isPrivate = true, onProgress } = options

  if (!file || file.size < THRESHOLD) return null

  const target = {
    folder,
    attached_to_doctype: attachTo?.doctype || '',
    attached_to_name: attachTo?.docname || '',
    attached_to_field: attachTo?.fieldname || '',
    is_private: isPrivate ? 1 : 0,
  }

  const started = await call(`${API}.begin`, {
    file_name: file.name,
    file_size: file.size,
    ...target,
  })
  if (!started?.direct) return null

  const { key, upload_id: uploadId, token, part_size: partSize, parts: count } = started

  try {
    const etags = await sendParts(file, {
      key,
      uploadId,
      token,
      partSize,
      count,
      urls: started.urls,
      onProgress,
    })

    // No `is_private` here: `begin` wrote it into the key and the token
    // vouches for the key, so the server does not ask us twice.
    return await call(`${API}.finish`, {
      key,
      upload_id: uploadId,
      token,
      parts: JSON.stringify(etags),
      file_name: file.name,
      folder: target.folder,
      attached_to_doctype: target.attached_to_doctype,
      attached_to_name: target.attached_to_name,
      attached_to_field: target.attached_to_field,
    })
  } catch (raised) {
    // The parts already in the bucket are billed until a lifecycle rule sweeps
    // them, and we know right now that nobody will ever complete this upload.
    call(`${API}.abort`, { key, upload_id: uploadId, token }).catch(() => {})
    throw raised
  }
}

/**
 * Every part, three lanes at a time, and their ETags.
 *
 * URLs arrive a batch at a time — a signature minted at the start of a 40 GB
 * upload has expired long before its part comes up — so the map is filled in as
 * the walk goes forward rather than up front.
 */
async function sendParts(file, { key, uploadId, token, partSize, count, urls, onProgress }) {
  const signed = new Map(urls.map((one) => [one.part, one.url]))
  const etags = new Array(count)
  const sent = new Array(count).fill(0)

  const report = () => {
    if (!onProgress) return
    const done = sent.reduce((sum, bytes) => sum + bytes, 0)
    onProgress({ loaded: done, total: file.size, percent: Math.round((done / file.size) * 100) })
  }

  // One lane failing stops the others taking new parts. Without it a dropped
  // connection on part three still pays to upload parts four through forty,
  // for an upload that has already failed.
  let next = 1
  let stopped = false
  const lane = async () => {
    for (;;) {
      const number = next
      if (stopped || number > count) return
      next += 1

      if (!signed.has(number)) {
        const more = await call(`${API}.sign`, {
          key,
          upload_id: uploadId,
          token,
          first: number,
          count: Math.min(50, count - number + 1),
        })
        for (const one of more.urls) signed.set(one.part, one.url)
      }

      const from = (number - 1) * partSize
      const chunk = file.slice(from, Math.min(from + partSize, file.size))

      etags[number - 1] = {
        part: number,
        etag: await put(signed.get(number), chunk, (loaded) => {
          sent[number - 1] = loaded
          report()
        }),
      }
      // The last progress event of a part can arrive short of its own size;
      // pinning it closes the gap so the bar reaches 100 rather than 99.
      sent[number - 1] = chunk.size
      report()
    }
  }

  const runs = await Promise.allSettled(
    Array.from({ length: Math.min(LANES, count) }, () =>
      lane().catch((raised) => {
        stopped = true
        throw raised
      }),
    ),
  )

  // `allSettled` and not `all`, so a second lane failing after the first is a
  // handled rejection rather than an unhandled one in the console.
  const failed = runs.find((run) => run.status === 'rejected')
  if (failed) throw failed.reason

  return etags
}

/**
 * One part, retried.
 *
 * The ETag is the whole point of the request: R2 completes a multipart upload
 * from the list of them, and a bucket whose CORS policy does not *expose*
 * `ETag` returns `null` here — every byte uploaded correctly and the upload
 * still fails at the last step. That is what `r2.ensure_cors()` is for, and it
 * is why this says so rather than throwing a bare "cannot complete".
 */
async function put(url, chunk, onBytes) {
  let last
  for (let attempt = 1; attempt <= TRIES; attempt += 1) {
    try {
      return await once(url, chunk, onBytes)
    } catch (raised) {
      last = raised
      onBytes(0)
      if (attempt < TRIES) await pause(attempt * 1000)
    }
  }
  throw last
}

function once(url, chunk, onBytes) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('PUT', url, true)

    request.upload.onprogress = (event) => onBytes(event.loaded)
    request.onerror = () => reject(new Error('The connection dropped while uploading.'))
    request.ontimeout = () => reject(new Error('That part timed out.'))

    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(`Storage refused a part (${request.status}).`))
        return
      }
      const etag = request.getResponseHeader('ETag')
      if (!etag) {
        reject(new Error('Storage did not return an ETag — the bucket needs its CORS policy.'))
        return
      }
      resolve(etag)
    }

    request.send(chunk)
  })
}

function pause(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
