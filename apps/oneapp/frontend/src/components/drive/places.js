/**
 * The places a file can be.
 *
 * One list, rendered twice: the rail on a desktop, and a dropdown beside the
 * breadcrumb on a phone — which has no rail, and without which Recents,
 * Favourites and the bin have no route to them at all.
 *
 * Every one of them is the same query with a different `where`; there is no
 * second store behind any. That is why the rail is cheap and why a sixth would
 * be a filter rather than a feature. `oneapp_core/drive/query.py` holds the
 * other half of this list, and a test keeps them in step.
 */
export const PLACES = [
  { value: 'home', label: 'All files', icon: 'lucide-folder' },
  { value: 'recents', label: 'Recent', icon: 'lucide-clock' },
  { value: 'favourites', label: 'Favourites', icon: 'lucide-heart' },
  { value: 'shared', label: 'Shared with me', icon: 'lucide-users' },
  { value: 'trash', label: 'Bin', icon: 'lucide-trash-2' },
]

/** What to call the place somebody is looking at. */
export const labelOf = (place) =>
  PLACES.find((one) => one.value === place)?.label || 'Files'
