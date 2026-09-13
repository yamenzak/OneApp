/**
 * Where the reader is, with one root.
 *
 * There were nine `crumbs` computeds and they disagreed about the first thing
 * on the page. The engine's root was the *space*; every other surface's root
 * was itself — Files, Mail, Calendar, Account, Spaces, Add a space, the
 * assistant's own name. So there was no shared first crumb and no answer to
 * "where am I" that held across two screens. OneDoc's was the cleverest and
 * the least consistent: its root was wherever you came from, remembered in a
 * query parameter, so the same document had a different trail depending on
 * how you reached it.
 *
 * **The root is the place, and the place is not a second crumb.** The house
 * goes where the place goes — the space you are in, the Drive, the mailbox —
 * and what follows is where inside it you are:
 *
 *     [ 🏠 space ] / [ screen ]            a screen in a space
 *     [ 🏠 Files ] / [ folder ] / [ … ]    a folder in the Drive
 *     [ 🏠 Files ] + the document          an editor; see `Trail.vue`
 *
 * It used to be `[ 🏠 workspace ] / [ space ] / [ screen ]`, and the space's
 * name was the crumb that earned the least: the switcher in the corner says
 * which space this is and is the only way to another one, so the crumb was a
 * second answer to a question already answered two inches to its left. The
 * workspace is still one press away — the switcher's first entry is the list
 * of spaces — which is what makes this safe to drop.
 *
 * And the subject is not a crumb: what you are *looking at* is the element
 * after the trail, drawn by `components/Trail.vue`, which also collapses the
 * trail to its root when there is one. A crumb is a line of text; a record is
 * a face, a name, an id and two badges.
 *
 * `docs/UNIFICATION.md` §C1.
 */
import { computed, unref } from 'vue'

import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'

//: Where the house goes for a surface that names no place of its own. The list
//: of spaces is the nearest true thing to "the workspace" until a workspace
//: home exists.
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
 * `place` is where in the workspace this is — its first crumb *becomes* the
 * root — and `trail` is where inside that place.
 */
export function useCrumbs(place, trail) {
  return computed(() => {
    const [root, ...beside] = read(place)
    return [
      {
        label: '',
        // Read by `Trail.vue` as both the tooltip and the accessible name. It
        // names where the house goes, which is no longer always the same
        // address — so a fixed "workspace home" would have been a label that
        // lied on every surface but one.
        home: root?.label
          ? __('{0} home', [root.label])
          : __('{0} home', [session.tenant?.name || __('Workspace')]),
        route: root?.route || WORKSPACE,
      },
      ...beside,
      ...read(trail),
    ]
  })
}
