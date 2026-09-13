/**
 * The places a file can be.
 *
 * One list, rendered twice: the rail on a desktop, and a dropdown beside the
 * breadcrumb on a phone — which has no rail, and without which Recents,
 * Favourites and the bin have no route to them at all.
 *
 * Every one of them is the same query with a different `where`; there is no
 * second store behind any. That is why the rail is cheap, and why Templates
 * is a `where` on the flag rather than a folder somebody has to be taught to
 * file things into. `onestorage/query.py` holds the other half of this list,
 * and a test keeps them in step.
 *
 * Records is the one that is a *tree* rather than a filter — a directory per
 * kind of record and one per record inside it — and it is still no second
 * store: the levels are made out of the attachment rows at the moment they are
 * asked for. It is the same tree a mounted `doctype:Quotation` presents over
 * WebDAV, out of the same resolver, because a rail place and a mount that
 * disagreed about what a record has on it would be two answers to one
 * question. `onestorage/scopes.py`, and `docs/UNIFICATION.md` §E1.
 */
import { __ } from '@/shared/lib/runtime/translate'

export const PLACES = [
  { value: 'home', label: __('All files'), icon: 'lucide-folder' },
  { value: 'recents', label: __('Recent'), icon: 'lucide-clock' },
  { value: 'favourites', label: __('Favourites'), icon: 'lucide-heart' },
  { value: 'shared', label: __('Shared with me'), icon: 'lucide-users' },
  { value: 'templates', label: __('Templates'), icon: 'lucide-bookmark' },
  { value: 'records', label: __('Records'), icon: 'lucide-boxes' },
  { value: 'trash', label: __('Bin'), icon: 'lucide-trash-2' },
]

/** What to call the place somebody is looking at. */
export const labelOf = (place) =>
  PLACES.find((one) => one.value === place)?.label || __('Files')
