/**
 * The places a file can be.
 *
 * Every one of them is the same query with a different `where`; there is no
 * second store behind any. That is why the rail is cheap, and why Templates
 * is a `where` on the flag rather than a folder somebody has to be taught to
 * file things into. `onestorage/query.py` holds the other half of this list,
 * and a test keeps them in step.
 *
 * Documents and Workbooks are what somebody *made* here rather than uploaded,
 * which is `custom_kind` and therefore one `where` each. The server derives
 * both from `kinds.PLACE_FOR`, so a third editor gets its place by declaring
 * the kind.
 *
 * Records is the one that is a *tree* rather than a filter — a directory per
 * kind of record and one per record inside it — and it is still no second
 * store: the levels are made out of the attachment rows at the moment they are
 * asked for. It is the same tree a mounted `doctype:Quotation` presents over
 * WebDAV, out of the same resolver, because a rail place and a mount that
 * disagreed about what a record has on it would be two answers to one
 * question. `onestorage/scopes.py`, and `docs/UNIFICATION.md` §E1.
 *
 * **`PLACES` is the endpoint's vocabulary; `RAIL` is the rail.** They were one
 * list, and a list that is both grows to whatever the server can answer: ten
 * flat entries, three of which — Documents, Workbooks, Code — are the same
 * filter as three of the kind pills an inch to the right, and one of which
 * (Templates) is a thing you pick from the New menu rather than a room you go
 * and stand in. A place is a question the server can answer and stays
 * answerable, so `/one/drive?place=workbooks` is still a link that works. A
 * rail entry is a claim that this is somewhere you go often enough to deserve
 * a permanent seat, and there are five of those.
 */
import { __ } from '@/shared/lib/runtime/translate'

export const PLACES = [
  { value: 'home', label: __('All files'), icon: 'lucide-folder' },
  { value: 'recents', label: __('Recent'), icon: 'lucide-clock' },
  { value: 'favourites', label: __('Favourites'), icon: 'lucide-heart' },
  { value: 'shared', label: __('Shared with me'), icon: 'lucide-users' },
  { value: 'documents', label: __('Documents'), icon: 'lucide-file-text' },
  { value: 'workbooks', label: __('Workbooks'), icon: 'lucide-table' },
  { value: 'code', label: __('Code'), icon: 'lucide-code-xml' },
  { value: 'templates', label: __('Templates'), icon: 'lucide-bookmark' },
  { value: 'records', label: __('Records'), icon: 'lucide-boxes' },
  { value: 'trash', label: __('Bin'), icon: 'lucide-trash-2' },
]

/** One place by its value, or nothing. */
const at = (value) => PLACES.find((one) => one.value === value)

/**
 * The rail, in the three bands a file manager has always had.
 *
 * The first is where you are — the four that answer "what have I got", with
 * All files at the top of them. The second is the tree, which the rail draws
 * itself and which is why `records` sits alone: it is the only place whose
 * children are folders you can walk into. The third is the foot, which is the
 * bin, and a bin belongs at the bottom in every file manager anybody has used.
 *
 * Folders and Connected are not here. They are not places — they are the
 * drive's own shape and other people's servers — and `DriveSidebar` draws each
 * from its own fetch, between the second band and the foot.
 */
export const RAIL = [
  { key: 'yours', places: ['home', 'recents', 'favourites', 'shared'].map(at) },
  { key: 'records', places: [at('records')] },
]

/** The bin, which is a band of its own at the foot. */
export const BIN = at('trash')

/** What to call the place somebody is looking at. */
export const labelOf = (place) => at(place)?.label || __('Files')
