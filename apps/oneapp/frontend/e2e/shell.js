/**
 * Reaching the shell's own controls from a spec.
 *
 * The chrome moves. Settings was a button in the rail's footer, then a row in
 * the column's foot, and is now a row in the account menu — and each of those
 * moves broke a dozen specs that knew where it used to be. One place that
 * knows, so the next move is one edit.
 */
import { expect } from '@playwright/test'

/**
 * Open the settings dialog the way a person does.
 *
 * Two shells, and no longer one slot over both: a desktop has an account menu
 * in the foot of the column and settings is a row inside it, while a phone has
 * no column at all and reaches it through the More sheet. Which one is on
 * screen is asked rather than passed in, so a spec that runs on both projects
 * does not have to know.
 *
 * The wait comes first and covers both, because the foot is drawn from the
 * session: on a cold start a bare `count()` would find neither and take the
 * phone's path on a desktop.
 */
export async function openSettings(page) {
  const account = page.locator('[data-slot="account-menu"]')
  const more = page.getByRole('button', { name: 'More' })
  await expect(account.or(more).first()).toBeVisible({ timeout: 15_000 })

  if (await account.count()) {
    // Opened, and re-opened only if it is not already open.
    //
    // Two failure shapes, one cause: the foot is drawn from the session, so
    // for about a second after a page arrives the surfaces recompute as the
    // mail count and the assistant's availability land. The menu either never
    // opens — the popover mounts onto a trigger that has already been replaced
    // — or opens and is then torn down with the rows under the click.
    //
    // So: only press when the row is not on screen, which keeps a retry from
    // pressing a *toggle* shut, and let the click itself be retried, because
    // the row it detached is a row that comes straight back.
    const row = page.getByRole('menuitem', { name: 'Settings' })
    for (let go = 0; go < 4; go += 1) {
      // A third shape, and the loop is where it has to be caught rather than
      // above it. Since §C4 the dialog has an address — `?panel=mailbox` — so
      // a reload mid-spec comes back with settings *already open*, and the
      // account menu is then under the dialog's own overlay with every click
      // on it intercepted. It cannot be asked before the loop because the
      // shell renders first and the dialog a tick later, so a check up there
      // races the thing it is looking for.
      if (await alreadyOpen(page)) return
      if (!(await row.isVisible().catch(() => false))) {
        // Swallowed so an intercepted click cannot spend the whole budget in
        // one pass: the next turn of the loop is what notices the dialog.
        await account.click({ timeout: 4_000 }).catch(() => {})
        await row.waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {})
      }
      try {
        await row.click({ timeout: 4_000 })
        return
      } catch {
        await page.waitForTimeout(300)
      }
    }
    if (await alreadyOpen(page)) return
    throw new Error('the account menu would not stay open long enough to press Settings')
  }
  await more.click()
  await page.locator('[data-slot="settings-link"]').click()
}

/** Whether the settings dialog is on screen: its own tab strip, and nothing
 *  else in the product draws one. */
const alreadyOpen = (page) =>
  page.locator('[data-slot^="settings-tab-"]').first().isVisible().catch(() => false)
