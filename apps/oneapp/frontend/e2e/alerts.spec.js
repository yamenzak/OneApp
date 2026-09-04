import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * Rules that tell somebody when something happens to a record.
 *
 * The condition is the reason this is worth a browser pass rather than only a
 * unit test: it is three controls that the server compiles into the expression
 * Frappe evaluates, and the thing that must never appear here is a box you can
 * type code into.
 */

const rules = (page) => page.locator('[data-slot="alert-rule"]')

async function openAlerts(page, baseURL) {
  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: 'Alerts' }).click()
}

test('an alert is one sentence, and it is saved as a rule', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'settings tabs scroll on a phone; covered on desktop')
  const errors = collectConsoleErrors(page)

  await openAlerts(page, baseURL)

  const subject = `Tell me about this ${Date.now()}`
  await page.getByRole('button', { name: 'New alert' }).first().click()

  const dialog = page.getByRole('dialog').filter({ hasText: 'New alert' })
  // frappe-ui's Select is a combobox with a popover, not a native `<select>`,
  // so it is opened and an option is clicked.
  await dialog.getByRole('combobox', { name: 'Tell this role' }).click()
  await page.getByRole('option').nth(1).click()
  await dialog.getByLabel('Subject').fill(subject)
  await dialog.getByRole('button', { name: 'Save' }).click()

  const rule = rules(page).filter({ hasText: subject })
  await expect(rule).toBeVisible({ timeout: 15_000 })
  // The list reads the rule back as the sentence it was written as, so
  // somebody scanning ten of them can see what each one does.
  await expect(rule).toContainText('When')
  await expect(rule).toContainText('tell')

  expectNoRealErrors(errors)
})

test('a condition is three controls, never a box you can type code into', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'settings tabs scroll on a phone; covered on desktop')

  await openAlerts(page, baseURL)
  await page.getByRole('button', { name: 'New alert' }).first().click()

  const dialog = page.getByRole('dialog').filter({ hasText: 'New alert' })

  // Off until asked for: most rules have no condition at all.
  await expect(dialog.getByRole('combobox', { name: 'Test' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Add a test' }).click()

  // A field, an operator and a value — all three chosen, none of them typed as
  // an expression. Frappe evaluates `condition` as code, so a free text box
  // here would be a text box that runs code.
  await expect(dialog.getByRole('combobox', { name: 'Field' })).toBeVisible()
  await expect(dialog.getByRole('combobox', { name: 'Test' })).toBeVisible()
  await expect(dialog.getByLabel('Value')).toBeVisible()

  // The operators offered are the ones a person can read back out of the
  // sentence they wrote. There is no "matches" and no expression.
  const tests = dialog.getByRole('combobox', { name: 'Test' })
  await tests.click()
  const offered = await page.getByRole('option').allInnerTexts()
  expect(offered).toContain('is')
  expect(offered).toContain('is filled in')

  // And the value goes away for the two tests that have no value to give.
  await page.getByRole('option', { name: 'is filled in', exact: true }).click()
  await expect(dialog.getByLabel('Value')).toHaveCount(0)
})
