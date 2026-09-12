/**
 * Where the reader is, with one root.
 *
 * There were nine `crumbs` computeds and they disagreed about the first thing
 * on the page. The engine's root was the *space*; every other surface's root
 * was itself — Files, Mail, Calendar, Account, Spaces, Add a space, the
 * assistant's own name. So there was no shared first crumb, no way from Mail
 * back to the workspace in one click, and no answer to "where am I" that held
 * across two screens. OneDoc's was the cleverest and the least consistent:
 * its root was wherever you came from, remembered in a query parameter, so
 * the same document had a different trail depending on how you reached it.
 *
 * The root is the workspace, always. What follows is the *place* — a space,
 * or one of the workspace-level places — and then whatever that place has to
 * say about where inside it you are.
 *
 *     [ 🏠 workspace ] / [ space or place ] / [ screen or folder ] / …
 *
 * And the subject is not a crumb: what you are *looking at* is the element
 * after the trail, drawn by `components/Trail.vue`. A crumb is a line of
 * text; a record is a face, a name, an id and two badges.
 *
 * `docs/UNIFICATION.md` §C1.
 */
import { computed, unref } from 'vue'

import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'

//: Where the house goes. The list of spaces is the nearest true thing to
//: "the workspace" until a workspace home exists.
export const WORKSPACE = { name: 'Launcher' }

//: A crumb, a list of them, a ref holding either, or a getter. Half the
//: callers know their place at import time and half work it out per render,
//: and a composable that took only one of those shapes would be a composable
//: half of them wrapped.
const read = (value) => {
  const now = typeof value === 'function' ? value() : unref(value)
  return [now || []].flat().filter(Boolean)
}

/**
 * `place` is where in the workspace this is — one crumb, or several — and
 * `trail` is where inside that place.
 */
export function useCrumbs(place, trail) {
  return computed(() => {
    const here = read(place)
    const inside = read(trail)
    return [
      {
        label: '',
        // Read by `Trail.vue` as both the tooltip and the accessible name.
        home: __('{0} home', [session.tenant?.name || __('Workspace')]),
        route: WORKSPACE,
      },
      ...here,
      ...inside,
    ]
  })
}
