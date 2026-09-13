/**
 * The coloured mark for a kind of file.
 *
 * Taken from frappe/suite — see `../art/README.md` for the licence and for why
 * these rather than the lucide glyphs already in the bundle. The short version
 * is that a grid of files is a wall of icons, and a reader recognises a red PDF
 * and a green spreadsheet without reading anything.
 *
 * As URLs rather than as markup, which is `onemobility/lib/art.js`'s answer to
 * the same question and is right for the same two reasons: an `<img>` needs no
 * `v-html`, and every one of these files is under Vite's inline ceiling, so
 * the build turns each into a `data:` URL and the whole set costs no requests
 * at all. Eleven files, 9.8 kB before gzip.
 */

import { downloadUrl } from '@/modules/onestorage/lib/files'

/** `{ Image: 'data:image/svg+xml,…' }`, keyed by the kind each file is named for. */
export const ART = Object.fromEntries(
  Object.entries(
    import.meta.glob('../art/*.svg', { eager: true, import: 'default' }),
  ).map(([path, url]) => [path.split('/').pop().replace('.svg', ''), url]),
)

/**
 * The mark for one file.
 *
 * A folder somebody else owns gets the shared one: in the Shared place every
 * row is somebody else's, and a wall of identical folders there says nothing
 * about the one thing that place is *for*. It is the only mark here that is
 * not a `custom_kind`, which is why it is decided from the row rather than
 * looked up from the kind.
 *
 * Anything this map has not been taught falls to `Other`, which is the same
 * answer `kinds.py` gives for a file it cannot place — the two ends of one
 * question, and they have to agree.
 */
export function artFor(file, { shared = false } = {}) {
  if (file?.is_folder || file?.custom_kind === 'Folder') {
    return shared ? ART['Folder-shared'] : ART.Folder
  }
  return ART[file?.custom_kind] || ART.Other
}

/** The mark for a bare kind, where there is no row to ask. */
export const artForKind = (kind) => ART[kind] || ART.Other

/**
 * The kinds a thumbnail can ever exist for.
 *
 * Asked on the browser side so a card for a `.zip` never makes a request the
 * server would answer with an empty string. The server holds the same list —
 * `onestorage/thumbnails.py` — and `tests/test_thumbnails.py` reads the two
 * back against each other.
 */
export const THUMBNAILED = ['Image', 'Video', 'PDF']

/**
 * Where a file's thumbnail is, or empty for a file that has none.
 *
 * A URL and not a fetch: an `<img>` with a `src` is a request the browser
 * schedules, caches, and cancels when the card scrolls away, and none of those
 * three is worth writing again.
 */
export function thumbnailUrl(file) {
  if (!file || file.is_folder || file.remote) return ''
  if (!THUMBNAILED.includes(file.custom_kind)) return ''
  // An SVG is already the picture, at every size. Pillow cannot open one — so
  // the endpoint answers empty for it and always would — and rasterising a
  // drawing to 400px to show it at 170 would be the worse of the two answers
  // anyway. The download door is the same permission check the thumbnail
  // endpoint makes, so this is not a way round anything.
  if (/\.svgz?$/i.test(file.file_name || '')) return downloadUrl(file.name)
  return `/api/method/oneapp.onestorage.thumbnails.thumbnail?file=${encodeURIComponent(file.name)}`
}
