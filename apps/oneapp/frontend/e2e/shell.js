/**
 * Reaching the shell's own controls from a spec.
 *
 * The chrome moves. Settings was a button in the rail's footer, then a row in
 * the column's foot, and is now a row in the account menu — and each of those
 * moves broke a dozen specs that knew where it used to be. One place that
 * knows, so the next move is one edit.
 */

/** Open the settings dialog the way a person does: account menu, then the row. */
export async function openSettings(page) {
  await page.locator('[data-slot="account-menu"]').click()
  await page.locator('[data-slot="item"]', { hasText: 'Settings' }).click()
}
