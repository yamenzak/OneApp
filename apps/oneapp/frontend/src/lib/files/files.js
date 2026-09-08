/**
 * What a File row is, and how to say it.
 *
 * Shared by the attachment list and the gallery, because the two disagreeing
 * about which files are pictures is exactly the bug that would go unnoticed.
 */

import { __ } from '@/lib/runtime/translate'

// The extension is all a File row says about what it is, and it is enough for
// an icon. Anything unrecognised is a file, which is true.
const ICONS = [
  [/\.(png|jpe?g|gif|webp|svg|avif)$/i, 'lucide-image'],
  [/\.(pdf)$/i, 'lucide-file-text'],
  [/\.(csv|xlsx?|ods)$/i, 'lucide-table'],
  [/\.(zip|tar|gz|7z|rar)$/i, 'lucide-file-archive'],
]

const IMAGE = ICONS[0][0]

/**
 * One glyph per kind, for the surfaces that have a kind to draw.
 *
 * The set is the server's `drive/kinds.py` and a value it does not know falls
 * through to the same icon an unknown file gets. Two copies of this list —
 * the Drive's and the storage screen's — is exactly the pair that drifts, and
 * did: the storage screen never learnt what a sheet was.
 */
export const KIND_ICONS = {
  Folder: 'lucide-folder',
  Image: 'lucide-image',
  PDF: 'lucide-file-text',
  Video: 'lucide-video',
  Audio: 'lucide-music',
  Document: 'lucide-file',
  Sheet: 'lucide-table-2',
  Doc: 'lucide-file-signature',
  Other: 'lucide-file-question',
}

export const iconForKind = (kind) => KIND_ICONS[kind] || KIND_ICONS.Other

/**
 * The kind, in the reader's language.
 *
 * A kind is a stored English string because it is a key — it is filtered on,
 * grouped by and matched against `drive/kinds.py`, and a stored value that
 * changed with the reader's language would be a filter that stopped matching.
 * So the value stays and the *word* is looked up here.
 *
 * Written as returns rather than as a map for the reason every other list of
 * `__()` in this app is: a map built at module scope calls `__()` before the
 * catalogue has loaded, and the extractor that builds the catalogue needs to
 * see each string as a literal.
 */
export const labelForKind = (kind) => {
  if (kind === 'Folder') return __('Folder')
  if (kind === 'Image') return __('Image')
  if (kind === 'PDF') return __('PDF')
  if (kind === 'Video') return __('Video')
  if (kind === 'Audio') return __('Audio')
  if (kind === 'Document') return __('Document')
  if (kind === 'Sheet') return __('Sheet')
  if (kind === 'Doc') return __('Doc')
  return __('Other')
}

//: What opens in the text editor rather than the previewer. The server's
//: `docs/text.py` holds the same list; it is short, and a file that is not on
//: it is only ever previewed, so the two drifting costs a preview rather than
//: a broken save.
const TEXT = /\.(txt|md|markdown|csv|log|json|ya?ml)$/i

/**
 * The route that opens this file, or `null` when looking at it is the answer.
 *
 * A sheet is not a thing to preview — its bytes are a CSV and what a person
 * clicking it wants is the grid — and the same goes for a document and for the
 * text files beside them: a `.md` previewed is a `<pre>` of somebody's notes
 * with no way to fix the typo they opened it to fix.
 *
 * One function because two lists drift, and the one that drifted was the
 * record's Files tab: it previewed sheets long after the Drive had learnt not
 * to.
 */
export function routeFor(file) {
  if (!file || file.is_folder) return null
  if (file.custom_kind === 'Sheet') return { name: 'Sheet', params: { name: file.name } }
  if (file.custom_kind === 'Doc' || TEXT.test(file.file_name || '')) {
    return { name: 'Doc', params: { name: file.name } }
  }
  return null
}

export function iconFor(file) {
  const found = ICONS.find(([pattern]) => pattern.test(file?.file_name || file?.file_url || ''))
  return found ? found[1] : 'lucide-file'
}

/**
 * Whether this one can be shown rather than listed. By extension rather than by
 * a stored mime type, because a File row does not carry one — and an `<img>`
 * pointed at a zip renders a broken-image icon.
 */
export function isImage(file) {
  return IMAGE.test(file?.file_name || file?.file_url || '')
}

/**
 * "1.2 MB", in the reader's own locale — the server sends bytes because it does
 * not know what locale that is. Zero is empty rather than "0 B".
 */
export function humanSize(file) {
  const bytes = Number(file?.file_size) || 0
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  const step = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** step
  return `${value.toLocaleString(undefined, { maximumFractionDigits: step ? 1 : 0 })} ${units[step]}`
}

/**
 * A stored file, back in the browser as a `File`. Some things — importing a
 * spreadsheet, reading a CSV — need the bytes in hand rather than on a server.
 *
 * `credentials: 'include'` because the download route is a permission check,
 * and a fetch without the session cookie is an anonymous one.
 */
export async function fetchFile(row) {
  const url = row?.file_url
  if (!url) throw new Error('That file has nowhere to be read from.')

  const answer = await fetch(url, { credentials: 'include' })
  if (!answer.ok) throw new Error(`That file could not be read (${answer.status}).`)

  const blob = await answer.blob()
  return new File([blob], row.file_name || row.name || 'file', { type: blob.type })
}

/**
 * Where a file's bytes are.
 *
 * `r2.download` checks the reader's permission and then redirects to a
 * presigned object, so an `<img>`, a `<video>` and a download link are all the
 * same URL — and none of them needs a key of ours to reach it.
 */
export const downloadUrl = (name) =>
  `/api/method/oneapp.oneapp_core.storage.r2.download?file=${encodeURIComponent(name)}`
