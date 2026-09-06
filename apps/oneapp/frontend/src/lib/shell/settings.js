import { reactive } from 'vue'

/**
 * The settings dialog's open state, held outside the component tree.
 *
 * Settings overlay whatever you were doing rather than navigating away from it,
 * so the dialog lives at the top of the app and anything can ask for it — the
 * user menu, an empty state, a link from an app.
 */
const state = reactive({ open: false, tab: 'branding' })

export const settings = state

export function openSettings(tab) {
  if (tab) state.tab = tab
  state.open = true
}
