// A list, as a file somebody can open somewhere else.
//
// The claim worth testing end to end is not that a download happens — it is
// that the file is *this* list: the reader's own columns, narrowed by the
// filters above them, quoted so that a subject with a comma in it stays one
// cell. So this reads the bytes back rather than checking a toast.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/** Click Export and hand back the file's text. */
const exported = async (page, click) => {
  const waiting = page.waitForEvent('download')
  await click()
  const download = await waiting
  const stream = await download.createReadStream()
  const chunks = []
  for await (const chunk of stream) chunks.push(chunk)
  return { name: download.suggestedFilename(), text: Buffer.concat(chunks).toString('utf8') }
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a list exports as the columns on screen, quoted properly', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for a file')
  const errors = collectConsoleErrors(page)

  // The correspondence register, because it is the one with commas and Arabic
  // in it — the two things a hand-rolled CSV gets wrong.
  await page.goto('/one/space/zzmock?screen=correspondence&type=list')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })

  const file = await exported(page, () => page.locator('[data-slot="export"]').click())

  // Named for the screen and the day, so a downloads folder with four of these
  // in it is a folder with four usable files.
  expect(file.name).toMatch(/^Correspondence \d{4}-\d{2}-\d{2}\.csv$/)

  // The byte-order mark, without which Excel on Windows reads this as the
  // system codepage and every Arabic subject arrives as mojibake.
  expect(file.text.startsWith('﻿')).toBe(true)

  // The header is the column labels the screen is showing, and the rows are
  // under it. `\r\n`, which is what a spreadsheet expects.
  const [header, ...lines] = file.text.slice(1).split('\r\n').filter(Boolean)
  expect(header).toContain('Subject')
  expect(lines.length).toBeGreaterThanOrEqual(3)

  // The comma inside a subject stayed inside one cell, quoted — the failure
  // that would otherwise take every row after it out of true.
  expect(file.text).toContain('"Submission of revised shop drawings, revisions A to C"')
  // And the Arabic came through as Arabic.
  expect(file.text).toContain('تقديم مخططات التنفيذ المعدلة')

  expectNoRealErrors(errors)
})

test('a filter narrows the file the same way it narrows the list', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the quick filters are behind a control on a phone')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/zzmock?screen=correspondence&type=list')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })
  const before = await page.locator('[data-slot="list-row"]').count()

  // An unsaved filter, typed into the quick filter row. The export goes through
  // the same `overrides` the rows do, which is the whole point: a file that
  // ignored the filter above it would be a file that disagrees with the screen
  // it came from.
  // Enter, because a quick-filter box applies on Enter or a blur — a request
  // per keystroke is not a quick filter.
  await page.getByPlaceholder('Subject').fill('shop drawings')
  await page.getByPlaceholder('Subject').press('Enter')
  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(1, { timeout: 15_000 })
  expect(before).toBeGreaterThan(1)

  const file = await exported(page, () => page.locator('[data-slot="export"]').click())
  const lines = file.text.slice(1).split('\r\n').filter(Boolean)
  expect(lines).toHaveLength(2) // the header and the one row
  expect(file.text).toContain('Submission of revised shop drawings')

  expectNoRealErrors(errors)
})

test('a selection exports exactly what was ticked', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the row checkboxes are a desktop affordance')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/zzmock?screen=compliance&type=list')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })

  // The wrapper is the control; the input inside it is presentational and
  // `pointer-events-none`. See frappe-ui's `ListRowBase`.
  const tick = page.locator('[data-slot="list-row-checkbox"]')
  await tick.nth(0).click()
  await tick.nth(1).click()

  const bar = page.locator('[data-slot="selection-bar"]')
  const file = await exported(page, () =>
    bar.getByRole('button', { name: 'Export', exact: true }).click(),
  )

  // Two rows and a header, and not the eight the register holds.
  const lines = file.text.slice(1).split('\r\n').filter(Boolean)
  expect(lines).toHaveLength(3)

  expectNoRealErrors(errors)
})
