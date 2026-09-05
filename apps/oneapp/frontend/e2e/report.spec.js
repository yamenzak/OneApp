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
  // Enter, because a quick-filter box applies on Enter or a blur rather than
  // on every keystroke.
  await page.getByPlaceholder('Title').fill('Server renewal')
  await page.getByPlaceholder('Title').press('Enter')
  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(1, { timeout: 15_000 })
  await expect(totals).toContainText('4,800.00', { timeout: 15_000 })

  expectNoRealErrors(errors)
})

/** Type `amount` into a row and commit it. */
const setAmount = async (page, title, value) => {
  const row = rowFor(page, title).first()
  await row.locator('[data-slot="editable"]').first().click()
  const box = row.locator('input[type=number]').first()
  await box.fill(String(value))
  await box.press('Enter')
}

test('a cell can be typed into, and the total follows it', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a table cell is not a phone control')
  const errors = collectConsoleErrors(page)

  await page.goto(APPROVALS)
  await rowFor(page, 'Server renewal').first().waitFor({ timeout: 20_000 })
  const totals = page.locator('[data-slot="list-header"]').last()
  await expect(totals).toContainText('Total', { timeout: 15_000 })

  // Read the total rather than hard-code it: what else is in this register is
  // the fixture's business, and the claim being tested is that the sum *moves
  // by the difference*.
  const asNumber = async () =>
    Number((await totals.innerText()).replace(/[^\d.]/g, ''))
  const before = await asNumber()
  expect(before).toBeGreaterThan(0)

  await setAmount(page, 'Server renewal', 5100)

  // Two things at once, and both are the point. The row shows what the record
  // kept — the list re-reads after a write, so a figure that stays is the
  // server's and not the browser's — and the total is an aggregate taken again,
  // so it moves by exactly the three hundred.
  await expect(rowFor(page, 'Server renewal').first()).toContainText('5,100.00', {
    timeout: 15_000,
  })
  await expect(async () => expect(await asNumber()).toBe(before + 300)).toPass({
    timeout: 15_000,
  })

  // And it survives a reload, which is the only proof it reached the database.
  await page.reload()
  await expect(rowFor(page, 'Server renewal').first()).toContainText('5,100.00', {
    timeout: 20_000,
  })

  // A click takes the cursor rather than opening the record, which is the whole
  // reason a report is its own view type.
  await expect(page.locator('[data-slot="record-controls"]')).toHaveCount(0)

  // And a submitted record has no editable cell at all. Office chairs is
  // approved, which on this fixture's workflow is a docstatus of 1: Frappe
  // refuses the write, and a table that offered it anyway would be offering an
  // edit that can only ever fail. It cost this test one round to find out.
  await expect(
    rowFor(page, 'Office chairs').first().locator('[data-slot="editable"]'),
  ).toHaveCount(0)

  // Put it back, so the next run starts where this one did.
  await setAmount(page, 'Server renewal', 4800)
  await expect(rowFor(page, 'Server renewal').first()).toContainText('4,800.00', {
    timeout: 15_000,
  })
  await expect(async () => expect(await asNumber()).toBe(before)).toPass({ timeout: 15_000 })

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
