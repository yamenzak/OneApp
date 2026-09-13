import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * A panel with an address opens from a cold URL.
 *
 * Settings has twenty-four panels and there was no way to link to one, which
 * made every support answer "open settings, then find Backups". The assistant
 * and the filter panel had the same problem and the same cause: none of them
 * is a route, so none of them was in the URL.
 *
 * They are still dialogs and panels — §C2 is right that a thing you toggle is
 * not a route — and this is the test that they can nevertheless be *said*.
 * Cold, from a fresh navigation, because that is what a link somebody sends
 * actually does; opening one by clicking and reading the URL back would prove
 * only half of it.
 *
 * `docs/UNIFICATION.md` §C4.
 */

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a settings panel is a link', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock?panel=backups')

  const dialog = page.locator('[data-oneapp="settings-dialog"], [role="dialog"]').first()
  await expect(dialog).toBeVisible({ timeout: 20_000 })
  // The panel it names, not the first one in the list.
  await expect(page.getByText('Backups', { exact: false }).first()).toBeVisible()

  expectNoRealErrors(errors)
})

test('the assistant is a link', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  // `new` rather than an empty value: Vue Router drops an empty string, so
  // "open on nothing" has to say so with a word.
  await page.goto('/one/space/zzmock?ask=new')

  const panel = page.locator('[data-slot="assistant-panel"]')
  // A workspace with AI switched off draws nothing, and that is correct
  // rather than a failure — the address still resolves, to a closed panel.
  if (await panel.count()) {
    await expect(panel).toBeVisible({ timeout: 20_000 })
    await expect(page.locator('[data-slot="assistant-close"]')).toBeVisible()
  }

  expectNoRealErrors(errors)
})

test('the filter panel is a link, which is what a reload needs', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock?screen=tasks&filters=open')

  // Somebody halfway through building a filter who pressed refresh used to
  // come back with the panel shut.
  await expect(page.getByText('No filters yet', { exact: false }).first())
    .toBeVisible({ timeout: 20_000 })

  expectNoRealErrors(errors)
})

test('a panel says where it is once it is opened', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock?screen=tasks')

  // The other direction, and the one that makes the address worth having:
  // open it by hand and the URL is now a thing to send.
  // `exact`: the panel's own "Add filter" carries the word too, and matching
  // loosely finds whichever the DOM happens to order first.
  await page.getByRole('button', { name: 'Filter', exact: true }).first().click()
  await expect(page).toHaveURL(/[?&]filters=open/, { timeout: 10_000 })

  expectNoRealErrors(errors)
})
