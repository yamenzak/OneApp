/**
 * Reaching the shell's own controls from a spec.
 *
 * The chrome moves. Settings was a button in the rail's footer, then a row in
 * the column's foot, then a row in the account menu, and is now a *page* — and
 * each of those moves broke a dozen specs that knew where it used to be. One
 * place that knows, so the next move is one edit.
 */
import { expect } from '@playwright/test'

//: The space that hosts the workspace's own settings and your own —
//: `oneapp/onespace/one.py`.
const ONE = 'one'

/**
 * Open settings.
 *
 * It used to be a dialog, so this used to be the account menu, a row in it,
 * and three paragraphs about a popover that tore itself down while the session
 * was still settling. It is a screen now, so it is an address — which is the
 * whole point of the move and is why this function is four lines.
 *
 * `space` is which Configuration page: One's by default, which is where the
 * workspace's settings and your own are. A space's own — alerts, naming, print
 * formats, and its tables — is that space's code.
 */
export async function openSettings(page, { space = ONE, tab = '' } = {}) {
  const at = `/one/space/${space}?screen=configuration${tab ? `&tab=${tab}` : ''}`
  await page.goto(at)
  await expect(page.locator('[data-slot="configuration-rail"], [role="tab"]').first())
    .toBeVisible({ timeout: 25_000 })
}
