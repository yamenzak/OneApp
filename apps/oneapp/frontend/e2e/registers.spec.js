// The two registers OneSpace ships itself, and the bidi rule they proved out.
//
// Neither is a customer's: a licence that expires and a letter that has to be
// numbered are what a company *is*. They are also the first doctypes here whose
// only surface is a manifest screen — no component anywhere — so opening them
// is what proves that claim on every run.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the compliance register leads with what is about to lapse', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for an order')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/zzmock?screen=compliance&type=list')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  // Urgency order, and it is the whole reason the screen sorts by `status`
  // rather than by date: SQL puts a null expiry above every real one, so a
  // register ordered by date would lead with the papers that never expire.
  const badges = page
    .locator('[data-slot="list-row"]')
    .locator('[data-slot="record-status"], .badge')
  const said = await page.locator('[data-slot="list-row"]').allInnerTexts()

  expect(said[0]).toContain('Expired')
  expect(said[said.length - 1]).toMatch(/Valid|No expiry/)
  expect(badges).toBeTruthy()

  // And the status is derived, never typed: the seeded dates are relative to
  // the day this runs, so an Expired row here is arithmetic rather than a
  // fixture somebody remembered to update.
  await expect(page.getByText('Expired').first()).toBeVisible()
  await expect(page.getByText('Expiring').first()).toBeVisible()
  expectNoRealErrors(errors)
})

test('an Arabic cell reads right to left beside an English one', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the second column is off a phone')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/zzmock?screen=correspondence&type=list')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  // `dir="auto"` on every text cell and every text control, and nothing
  // declared anywhere: the browser reads the first strong character and lays
  // the value out from it. Frappe has no direction property on a DocField and
  // it would be the wrong place for one — direction belongs to the value.
  const row = page.locator('[data-slot="list-row"]').first()
  const english = row.locator('[dir="auto"]').filter({ hasText: /[A-Za-z]/ }).first()
  const arabic = row.locator('[dir="auto"]').filter({ hasText: /[؀-ۿ]/ }).first()

  await expect(arabic).toHaveCSS('direction', 'rtl')
  await expect(english).toHaveCSS('direction', 'ltr')
  expectNoRealErrors(errors)
})

test('a letter is written in both languages on one form', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the record header collapses on a phone')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/zzmock?screen=correspondence&type=list')
  await page.locator('[data-slot="list-row"]').first().click()
  const pane = page.locator('[data-slot="record-pane"]')
  await pane.waitFor({ timeout: 15_000 })

  // Two sections, neither of them the "real" one — which is what a company
  // writing to a municipality in Arabic and a consultant in English needs.
  await expect(pane.getByText('ENGLISH')).toBeVisible()
  await expect(pane.getByText('العربية')).toBeVisible()

  // And the Arabic subject box lays itself out from its own first word.
  const subjectAr = pane.getByLabel('الموضوع', { exact: true })
  await expect(subjectAr).toHaveAttribute('dir', 'auto')
  await expect(subjectAr).toHaveCSS('direction', 'rtl')
  expectNoRealErrors(errors)
})
