// The list, opened as a worksheet.
//
// A report is the list plus two things: cells you can type into and a row of
// totals under them. Both are worth a browser — the first because the write
// goes through the record's own rules and has to come back, and the second
// because a total over the page instead of over the filter is the failure
// nobody would notice.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const APPROVALS = '/one/space/zzmock?screen=approvals&type=report'

/** The row for one approval, by the title in it. */
const rowFor = (page, title) =>
  page.locator('[data-slot="list-row"]').filter({ hasText: title })

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a report totals the money over every row that matches', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for a sum')
  const errors = collectConsoleErrors(page)

  await page.goto(APPROVALS)
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })

  // The fixture's three, and whatever else is in the register. Read off the
  // screen rather than hard-coded, so this is asserting the arithmetic and not
  // the fixture: a total that summed the page would still match here, which is
  // what the filter half below is for.
  const amounts = await page
    .locator('[data-slot="list-row"] [data-slot="list-cell"]')
    .filter({ hasText: /^[\d,]+\.\d\d$/ })
    .allInnerTexts()
  const adds = amounts.reduce((sum, one) => sum + Number(one.replace(/,/g, '')), 0)

  const totals = page.locator('[data-slot="list-header"]').last()
  await expect(totals).toContainText('Total')
  await expect(totals).toContainText(adds.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }))

  expectNoRealErrors(errors)
})

test('the total follows the filter, not the page', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the quick filters are behind a control on a phone')
  const errors = collectConsoleErrors(page)

  await page.goto(APPROVALS)
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })
  const totals = page.locator('[data-slot="list-header"]').last()
  await expect(totals).toContainText('Total', { timeout: 15_000 })

  // Narrow to one record and the total is that record's amount. This is the
  // assertion the whole design turns on: the sum is an aggregate over the
  // filter, taken separately from the rows, rather than an addition of what
  // happens to be loaded.
  await page.getByPlaceholder('Title').fill('Server renewal')
  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(1, { timeout: 15_000 })
  await expect(totals).toContainText('4,800.00', { timeout: 15_000 })

  expectNoRealErrors(errors)
})

test('a cell can be typed into, and the record keeps it', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a table cell is not a phone control')
  const errors = collectConsoleErrors(page)

  await page.goto(APPROVALS)
  const row = rowFor(page, 'Office chairs')
  await row.first().waitFor({ timeout: 20_000 })

  // A click takes the cursor rather than opening the record: that difference is
  // the whole reason a report is its own view type.
  await row.first().locator('[data-slot="editable"]').first().click()
  await expect(page.locator('[data-slot="record-controls"]')).toHaveCount(0)

  const box = row.first().locator('input').first()
  await box.fill('Office chairs (revised)')
  await box.press('Enter')

  // Back from the server, not from the browser: the list re-reads after a
  // write, so a title that stays is one the record kept.
  await expect(rowFor(page, 'Office chairs (revised)')).toHaveCount(1, { timeout: 15_000 })
  await page.reload()
  await expect(rowFor(page, 'Office chairs (revised)')).toHaveCount(1, { timeout: 20_000 })

  // Put it back, so the next run starts where this one did.
  await rowFor(page, 'Office chairs (revised)')
    .first()
    .locator('[data-slot="editable"]')
    .first()
    .click()
  const again = rowFor(page, 'Office chairs (revised)').first().locator('input').first()
  await again.fill('Office chairs')
  await again.press('Enter')
  await expect(rowFor(page, 'Office chairs (revised)')).toHaveCount(0, { timeout: 15_000 })

  expectNoRealErrors(errors)
})

test('a list is still a list: its rows open and its cells do not', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the record opens as a page on a phone')
  const errors = collectConsoleErrors(page)

  // The same screen as a plain list. Nothing is editable and a click opens the
  // record — which is what makes one click able to mean two things.
  await page.goto('/one/space/zzmock?screen=approvals&type=list')
  const row = rowFor(page, 'Server renewal')
  await row.first().waitFor({ timeout: 20_000 })
  await expect(page.locator('[data-slot="editable"]')).toHaveCount(0)

  await row.first().locator('[data-slot="list-cell"]').nth(1).click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 15_000 })
  await expect(page).toHaveURL(/record=/)

  expectNoRealErrors(errors)
})
