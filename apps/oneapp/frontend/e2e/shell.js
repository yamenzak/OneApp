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
    await account.click()
    await page.locator('[data-slot="item"]', { hasText: 'Settings' }).click()
    return
  }
  await more.click()
  await page.locator('[data-slot="settings-link"]').click()
}
