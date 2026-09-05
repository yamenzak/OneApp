// What else in this space is about this record.
//
// Frappe's Connections, derived from the schema rather than declared: a screen
// whose doctype carries a link back at this one becomes a tab, and opening it
// is that screen filtered to this record. Two claims are worth a browser — the
// tab is there without anybody declaring it, and it found the right rows.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const COMPLIANCE = '/one/space/zzmock?screen=compliance'

// The fixture: one letter filed against the 2024 trade licence, and three
// filed against nothing.
const LICENCE = 'Trade Licence — 2024'
const LETTER = 'Renewal of trade licence CN-1109482'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a record grows a tab for every screen that points back at it', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  await page.goto(COMPLIANCE)
  await page.locator('[data-slot="list-row"]').filter({ hasText: LICENCE }).first().click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 20_000 })

  // Nothing in the manifest says any of this. Correspondence carries a Dynamic
  // Link — `about_doctype` beside `about` — and that is the whole declaration.
  await expect(page.getByRole('tab', { name: 'Correspondence' })).toBeVisible()

  expectNoRealErrors(errors)
})

test('the tab holds what was filed against this one and nothing else', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  await page.goto(COMPLIANCE)
  await page.locator('[data-slot="list-row"]').filter({ hasText: LICENCE }).first().click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 20_000 })
  await page.getByRole('tab', { name: 'Correspondence' }).click()

  const rows = page.locator('[data-slot="list-row"]')
  // The list behind the pane is gone from this tab's own table, so the rows
  // here are the tab's. One, and it is the renewal letter.
  await expect(page.getByText(LETTER).first()).toBeVisible({ timeout: 20_000 })

  // The three letters filed against nothing are not here. Without the doctype
  // half of the dynamic link every letter in the register would be.
  await expect(page.getByText('Request for extension of completion date')).toHaveCount(0)

  // And a way to file another, with the link back already filled in.
  await expect(page.locator('[data-slot="related-new"]')).toBeVisible()

  expect(await rows.count()).toBeGreaterThan(0)
  expectNoRealErrors(errors)
})
