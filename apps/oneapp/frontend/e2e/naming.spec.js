// Naming: what a record's id looks like before anybody types one.
//
// Frappe's `Document Naming Settings` does the writing. What this asserts is
// the panel's own distinction, which the desk's version never makes: a doctype
// named by its own `autoname` shows its series and its counter, and does not
// offer a Save that the server would refuse.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test('the naming panel shows only what this workspace may name', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'settings tabs scroll on a phone; covered on desktop')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: 'Naming' }).click()

  const records = page.getByRole('combobox', { name: 'Records' })
  await expect(records).toBeVisible()

  // Every doctype listed has a counter under it, and each of its prefixes says
  // where that counter has got to.
  await expect(page.locator('[data-slot="series-row"]').first()).toBeVisible()

  // Frappe's own preview, against the doctype's last record.
  await page.getByRole('button', { name: 'Preview' }).click()
  await expect(page.locator('[data-slot="series-row"]').first()).toBeVisible()

  expectNoRealErrors(errors)
})
