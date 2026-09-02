// The import console — the panel a customer's first day runs through.
//
// The engine behind it has unit tests; what those cannot say is whether the
// panel renders at all. It is reached through the user menu, two clicks from
// anything, and it was written before it was ever opened — which in this
// codebase is the reliable predictor of a feature that does not work.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// Seeded by `scripts/seed_dev_space.py`. Fictional: the address is a name
// nobody owns, so nothing here can reach anything.
const PLAN = 'Everything, from the old system'

async function openImport(page, baseURL) {
  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: 'Import' }).click()
}

test('the plan reads as the order it will run in', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'settings tabs scroll on a phone; covered on desktop')
  const errors = collectConsoleErrors(page)

  await openImport(page, baseURL)

  const plan = page.locator('[data-slot="import-plan"]').filter({ hasText: PLAN })
  await expect(plan).toBeVisible()
  await expect(plan).toContainText('2 steps')

  // The steps in their declared order, which is the dependency order: the step
  // whose links resolve against another has to come after it, and the panel
  // showing them sorted or grouped would hide the one thing worth reading.
  const said = await plan.innerText()
  expect(said.indexOf('Old Party')).toBeLessThan(said.indexOf('Old Job'))

  // Nothing has run, so every step says so rather than showing a blank.
  await expect(plan).toContainText('not yet')

  // First time and every time after are different sentences, and the button
  // says which — this workspace has carried nothing across.
  await expect(plan.getByRole('button', { name: 'Bring everything across' })).toBeVisible()
  await expect(plan.getByRole('button', { name: 'Rehearse' })).toBeVisible()
  await expect(plan.getByRole('button', { name: 'Check the plan' })).toBeVisible()

  expectNoRealErrors(errors)
})

test('the saved secret is never sent back to the box', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'settings tabs scroll on a phone; covered on desktop')
  const errors = collectConsoleErrors(page)

  await openImport(page, baseURL)

  // The address and the key come back — they are not credentials and a box
  // that forgot them would ask the customer to retype what it already knows.
  await expect(page.getByRole('textbox', { name: 'Address' }).first()).toHaveValue(
    /^https:\/\//,
  )

  // The secret does not, and this is the assertion: Frappe keeps it in its own
  // encrypted store, the console never reads it back, and a box rendered with
  // dots in it would be lying about what it holds.
  const secret = page.getByLabel('API secret').first()
  await expect(secret).toHaveValue('')

  expectNoRealErrors(errors)
})
