/**
 * What a File row is, and how to say it.
 *
 * Shared by the attachment list and the gallery, because the two disagreeing
 * about which files are pictures is exactly the bug that would go unnoticed.
 */

import { __ } from '@/shared/lib/runtime/translate'
import { isCode, resolveLanguage } from '@/modules/onestorage/lib/languages'
import { sizeText } from '@/shared/lib/files/size'

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
  Code: 'lucide-file-code',
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
  if (kind === 'Code') return __('Code')
  return __('Other')
}

/**
 * What opens in an editor rather than the previewer.
 *
 * The three plain kinds `make_text` creates plus a log, and then every language
 * OneCode knows — which is the same union `docs/text.py` builds, and
 * `tests/test_docs.py` reads the two back against each other. It used to be a
 * regular expression written out here, and that was the drift: a file the
 * browser routed to the editor and the server called "not text" is a page that
 * loads and then says the file cannot be opened.
 */
const PLAIN = ['txt', 'csv', 'log']

const extensionOf = (fileName) => {
  const name = String(fileName || '').split('?')[0]
  return name.includes('.') ? name.split('.').pop().toLowerCase() : ''
}

/**
 * The most bytes a text editor will open, which is the server's answer read
 * before the question is asked.
 *
 * `onedoc/text.py` refuses anything larger — rightly: an editor holds the
 * whole file in memory, in a Y.Doc, and sends it back on every save. What was
 * wrong was *where* the refusal landed. The Drive decided a 3 MB `.log` was a
 * text file, mounted the editor, and the editor put "That document did not
 * open" in the pane. A file too big to edit is not a file too big to know
 * anything about: it has a name, a kind, a size and a download.
 *
 * So the ceiling is checked here, where the Drive chooses. Over it there is no
 * editor, which makes it an ordinary unpreviewable file and sends it to
 * `FileSurface` — which says what it is and offers the download.
 *
 * `tests/test_file_limits.py` holds the two numbers to each other.
 */
export const TEXT_CEILING = 2 * 1024 * 1024

const bytes = (file) => Number(file?.file_size) || 0

export const isEditableText = (fileName) => {
  const extension = extensionOf(fileName)
  return !!extension && (PLAIN.includes(extension) || !!resolveLanguage(extension))
}

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
  const editor = editorFor(file)
  if (!editor) return null
  return editor === 'sheet'
    ? { name: 'Sheet', params: { name: file.name } }
    : { name: 'Doc', params: { name: file.name } }
}

/**
 * Which editor this file is, or null when looking at it is the answer.
 *
 * Three now rather than two, and they do not map one-to-one onto routes: a
 * document and a `.py` are both `/one/docs/…` because both are one `File` and
 * the server decides which editor the page mounts. The Drive's pane needs the
 * distinction that the route does not carry — it renders the editor itself,
 * beside the list — so this is what it asks rather than re-deriving a kind for
 * itself, which is exactly the drift `routeFor` exists to prevent.
 */
export function editorFor(file) {
  if (!file || file.is_folder) return null
  // A sheet and a document are rows in our own tables and are read by their
  // own endpoints, so the ceiling below is not theirs.
  if (file.custom_kind === 'Sheet') return 'sheet'
  if (file.custom_kind === 'Doc') return 'doc'
  if (bytes(file) > TEXT_CEILING) return null
  if (isCode(file.file_name)) return 'code'
  return isEditableText(file.file_name) ? 'text' : null
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
 * A row's size, or an empty cell where there is none. The arithmetic is
 * `shared/lib/files/size.js`, which is also what a quota bar and an attach
 * control's ceiling read — §D3.
 */
export const humanSize = (file) => sizeText(file?.file_size)

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
/**
 * What a file on a mounted host is called: `remote://<mount>/<path>`.
 *
 * The prefix is the server's and is written out once here, because four
 * surfaces ask the same question — the row hides its heart, the pane offers
 * Copy instead of Share, the sidebar marks the mount you are in, and the
 * uploader refuses. See `onestorage/remote.py`.
 */
export const REMOTE = 'remote://'

export const isRemote = (name) => typeof name === 'string' && name.startsWith(REMOTE)

/** Which mount a remote name belongs to, or empty for one of ours. */
export const mountOf = (name) =>
  isRemote(name) ? name.slice(REMOTE.length).split('/')[0] : ''

export const downloadUrl = (name) =>
  `/api/method/oneapp.onestorage.r2.download?file=${encodeURIComponent(name)}`
