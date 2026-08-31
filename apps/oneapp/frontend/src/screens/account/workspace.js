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

import { workspaces } from './customer'

export function useWorkspace() {
  onMounted(() => {
    // Once per session rather than per screen. `load` refuses to be useful
    // twice and the account has three or four screens somebody clicks through.
    if (!workspaces.list.length) workspaces.load()
  })

  return computed(() => workspaces.current)
}
