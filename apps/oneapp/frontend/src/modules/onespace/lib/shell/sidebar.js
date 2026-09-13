/**
 * How wide the sidebar is, and whether it is open.
 *
 * There is one sidebar. Which component fills it depends on where you are —
 * the space rail, the mail rail, the Drive's places — but it is the same
 * column in the same slot, so its width and its collapsed state belong here
 * rather than three times over. They had drifted already: two of the three
 * carried their own copy of this and disagreed about the minimum and the
 * maximum, which a reader only notices as the page jumping when they open
 * mail.
 *
 * Module-level rather than per-component: the refs outlive a route change, so
 * collapsing the rail on a space and then opening the Drive finds it still
 * collapsed without a round trip through storage.
 */
import { ref, watch } from 'vue'

import { recall, remember } from '@/shared/lib/url/remember'

/** Narrow enough that a screen name still fits, wide enough that
 *  "Provisioning queue" is not three lines. */
export const MIN = 176
export const DEFAULT = 224
export const MAX = 420

// Open is a fine answer when nothing was remembered — a private window, site
// data turned off, a first visit.
const stored = () => recall('rail.shut') === '1'

// Explicitly boolean rather than left null: unset, frappe-ui's Sidebar
// collapses itself below the `sm` breakpoint, and below that breakpoint none
// of these components is rendered at all — the shell has switched to the
// phone's bar.
const collapsed = ref(stored())

watch(collapsed, (shut) => remember('rail.shut', shut ? '1' : '0'))

const width = ref(DEFAULT)

/** The shared state, for whichever rail is currently in the slot. */
export function useSidebar() {
  return { collapsed, width }
}
