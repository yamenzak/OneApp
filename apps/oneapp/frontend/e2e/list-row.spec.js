// What a click on a row does.
//
// frappe-ui's List documents `selectable` as switching "row click from navigate
// to toggle", and `ListRow.onClick` returns before the app's own handler ever
// runs. So for a while the only thing that opened a record was the title text,
// and clicking anywhere else in the row silently ticked a checkbox — which is
// not what a list of records does anywhere else, and not what Frappe's desk
// does either.
//
// `ListBody.openRow` takes the click back on the cell, where it can still be
// caught. That is a workaround over a documented upstream behaviour, so it is
// worth a test that drives the real thing: the day frappe-ui changes its mind
// about row clicks, this says so rather than the list quietly going back to
// selecting.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const ROW = '[data-slot="list-row"]'
const CELL = '[data-slot="list-cell"]'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a click anywhere on a row opens the record', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  const rows = page.locator(ROW)
  await rows.first().waitFor({ timeout: 15_000 })

  // A plain value cell: not the title button, not the like heart. This is the
  // part of the row that used to do nothing but tick a box.
  await rows.first().locator(CELL).nth(2).click()

  await expect(page).toHaveURL(/[?&]record=/)
  await expect(page.locator('[data-slot="record-pane"]')).toBeVisible()
  // ...and opening is not selecting. Both happening would put the selection bar
  // over the record that just opened.
  await expect(rows.first()).not.toHaveAttribute('data-state', 'selected')
  expectNoRealErrors(errors)
})

test('the checkbox still selects, and selecting opens nothing', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await page.goto('/one/space/zzmock')
  const rows = page.locator(ROW)
  await rows.first().waitFor({ timeout: 15_000 })

  const before = page.url()
  await rows.first().locator('[data-slot="list-row-checkbox"]').click()

  await expect(rows.first()).toHaveAttribute('data-state', 'selected')
  expect(page.url()).toBe(before)
})

test('a control inside a cell keeps its own click', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await page.goto('/one/space/zzmock')
  const rows = page.locator(ROW)
  await rows.first().waitFor({ timeout: 15_000 })

  // The like heart lives in a cell. Without `openRow`'s guard, liking a row
  // would also open it — which is the failure that makes a row-wide click
  // handler a bad idea when it is written carelessly.
  const heart = rows.first().getByRole('button', { name: /like/i }).first()
  if (!(await heart.count())) test.skip(true, 'no like control on this screen')
  const before = page.url()
  await heart.click()
  await page.waitForTimeout(400)
  expect(page.url()).toBe(before)
})
