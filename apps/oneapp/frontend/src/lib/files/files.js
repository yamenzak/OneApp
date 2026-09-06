/**
 * What a File row is, and how to say it.
 *
 * Shared by the attachment list and the gallery, because the two disagreeing
 * about which files are pictures is exactly the bug that would go unnoticed.
 */

// The extension is all a File row says about what it is, and it is enough for
// an icon. Anything unrecognised is a file, which is true.
const ICONS = [
  [/\.(png|jpe?g|gif|webp|svg|avif)$/i, 'lucide-image'],
  [/\.(pdf)$/i, 'lucide-file-text'],
  [/\.(csv|xlsx?|ods)$/i, 'lucide-table'],
  [/\.(zip|tar|gz|7z|rar)$/i, 'lucide-file-archive'],
]

const IMAGE = ICONS[0][0]

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
