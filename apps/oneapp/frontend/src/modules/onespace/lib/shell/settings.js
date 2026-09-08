import { reactive } from 'vue'

/**
 * The settings dialog's open state, held outside the component tree.
 *
 * Settings overlay whatever you were doing rather than navigating away from it,
 * so the dialog lives at the top of the app and anything can ask for it — the
 * user menu, an empty state, a link from an app.
 */
// No tab to begin with, deliberately. `branding` was the default from when
// this was an admin's dialog and every tab in it was the workspace's; now the
// gear is offered to everybody, and opening a member on a workspace tab — or
// an admin on one, rather than on their own profile — is opening on somebody
// else's business. The shell fills this in with the first tab the server said
// this reader may open. `openSettings('branding')` still goes straight there.
const state = reactive({ open: false, tab: '' })

export const settings = state

export function openSettings(tab) {
  if (tab) state.tab = tab
  state.open = true
}
