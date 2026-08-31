/**
 * The workspace an account screen is about.
 *
 * Loaded once and shared, so switching on the overview is still switched when
 * you open billing — the alternative is a picker per screen that each forget
 * what the last one chose.
 *
 * Returns a ref rather than the reactive object, because every screen wants the
 * same one thing and `toRef(props, 'workspace')` is the shape the ported
 * resources already take.
 */

import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { workspaces } from './customer'

export function useWorkspace() {
  const route = useRoute()

  onMounted(() => {
    // Once per session rather than per screen. `load` refuses to be useful
    // twice and the account has three or four screens somebody clicks through.
    //
    // `?workspace=` is how a link from outside says which one it meant — a
    // Stripe redirect back from checkout, or a billing email. Preferred rather
    // than forced: `load` keeps it only if the account actually owns it, so a
    // stale or guessed link falls back to the first workspace instead of
    // showing an empty account.
    if (!workspaces.list.length) workspaces.load(route.query.workspace || null)
  })

  return computed(() => workspaces.current)
}
