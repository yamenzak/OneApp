/**
 * Putting one file into the workspace, wherever it is going.
 *
 * There were four ways a file could reach a `File` row and they behaved
 * differently: the Drive's queue, the picker's uploader, an image pasted into a
 * rich-text field, a mail attachment. The visible cost was that only one of
 * them could send a large file — the Drive's — so a 200 MB video went into the
 * Drive fine and failed the moment somebody tried to attach one to a record.
 *
 * So one function. It tries the direct path (presigned, straight to R2, see
 * `directUpload.js`) and falls back to frappe-ui's `upload`, which posts to
 * Frappe's own endpoint. Both end at the same place — a `File` row, private,
 * attached to whatever was asked for — and callers do not choose between them.
 */
import { upload } from '@/ui'

import { directUpload } from './directUpload'

/**
 * One file in, one `File` row out.
 *
 * `attachTo` is `{ doctype, docname, fieldname }` when the file belongs to a
 * record, and absent when it is only going into the Drive. `folder` is where
 * it lands when it is not attached to anything.
 *
 * Private, always, on both paths. A workspace's files are not world-readable
 * and `r2.download` is the only way to the bytes — see `storage/r2.py`.
 */
export async function putFile(file, { attachTo = null, folder = '', onProgress } = {}) {
  const direct = await directUpload(file, { attachTo, folder, private: true, onProgress })
  if (direct) return direct

  return upload(file, {
    folder: folder || undefined,
    doctype: attachTo?.doctype || undefined,
    docname: attachTo?.docname || undefined,
    fieldname: attachTo?.fieldname || undefined,
    private: true,
    onProgress,
  })
}
