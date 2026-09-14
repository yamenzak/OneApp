/**
 * Where settings are, now that they are somewhere.
 *
 * They were a dialog: twenty-two panels behind a gear, opening over whatever
 * you happened to be looking at, with no address until §C4 bolted one on as a
 * query parameter of the page underneath. Everything wrong with that — no
 * route, no back button, no way to link to Backups, a member finding a column
 * of doors that would not open — is what the Configuration page already got
 * right for a space's tables. So the panels went there.
 *
 * `openSettings('branding')` still says the same thing it always said. What
 * changed is that it navigates, which means the browser's own back button now
 * answers "how do I get out of here" and a support answer can be a link.
 */
//: The space that hosts them — `oneapp/onespace/one.py`. Every workspace has
//: it, so this is the one space code a caller may assume.
const ONE = 'one'

//: Its Configuration screen, and the key a tab is addressed by.
const SCREEN = 'configuration'
export const TAB = 'tab'

/**
 * Where a panel is, as a route.
 *
 * `tab` is a `tabs.py` key — `branding`, `mailbox`, `connections`. A key this
 * reader may not open resolves to the first one they can, which the page does
 * rather than this: the audience is the server's answer and asking for it here
 * would be a second copy of it.
 */
export function settingsRoute(tab) {
  return {
    name: 'Screen',
    params: { spaceCode: ONE },
    query: { screen: SCREEN, ...(tab ? { [TAB]: tab } : {}) },
  }
}

/**
 * Open settings, for the callers that are a menu row rather than a link.
 *
 * The router is imported *inside* the call and not at the top of the module.
 * `router.js` builds a `createWebHistory` the moment it is imported, which
 * needs `window` — so a module-scope import here would make every unit test of
 * anything that eventually reaches this file need a DOM. It reached a long way:
 * the app catalogue imports this for the settings surface.
 */
export function openSettings(tab) {
  const to = settingsRoute(tab)
  return import('@/router').then(({ default: router }) => router.push(to))
}
