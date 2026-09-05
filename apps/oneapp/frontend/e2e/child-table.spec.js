// A child table, driven.
//
// The grid inside a record is the one surface that had shipped and never once
// been opened by a test — the dev fixture was two doctypes with no rows inside
// them. Frappe's Event is the fixture now, because it asks every question a
// child grid raises at once: two child tables on tabs of their own, a required
// column in one (`reference_doctype`), an Int column in the other (`before`),
// and a status Select on the parent.
//
// It is also the only doctype on a bare bench with real Tab Breaks, so it is
// where the derived tab icons can be seen rather than reasoned about.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// The Event with rows in both of its child tables.
const EVENT = 'Quarterly review'

// The record's own tab strip is nested inside the pane's, so both have a
// "Details". The inner one is the doctype's.
const openEvent = async (page, tab) => {
  // `type=list` because the fixture's events screen opens on its calendar,
  // and this is a test about a record rather than about a list — the list is
  // only how it gets there.
  await page.goto('/one/space/zzmock?screen=events&type=list')
  const row = page.locator('[data-slot="list-row"]').filter({ hasText: EVENT })
  await row.first().waitFor({ timeout: 15_000 })
  await row.first().locator('[data-slot="list-cell"]').nth(1).click()
  await page.getByRole('tab', { name: tab }).waitFor({ timeout: 15_000 })
  await page.getByRole('tab', { name: tab }).click()
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a child table draws the rows the record holds', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  const errors = collectConsoleErrors(page)
  await openEvent(page, 'Notifications')

  // Three notification rows, numbered from one — Frappe orders a child table
  // by `idx`, so the number is the row's position and it is worth showing.
  await expect(page.getByText('3 rows')).toBeVisible()
  const panel = page.getByRole('tabpanel', { name: 'Notifications' })
  await expect(panel.locator('[data-slot="list-row"]')).toHaveCount(3)
  expectNoRealErrors(errors)
})

test("the doctype's own tabs carry a glyph", async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await openEvent(page, 'Notifications')

  // Frappe has no icon property on a Tab Break, so these are derived from the
  // labels: Participants earns the people glyph, Links the chain, Notifications
  // the bell. Event is the only doctype on a bare bench that has any.
  for (const [tab, icon] of [
    ['Participants', 'lucide-users'],
    ['Links', 'lucide-link'],
    ['Notifications', 'lucide-bell'],
  ]) {
    await expect(
      page.getByRole('tab', { name: tab }).locator(`.${icon}`),
    ).toBeVisible()
  }
})

test('a required child column says so in its header', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await openEvent(page, 'Participants')

  // `Event Participants.reference_doctype` is `reqd`. A grid cell has no room
  // for a label, so without the marker in the header the only warning that a
  // column may not be left blank is the save failing.
  const header = page.getByRole('columnheader').filter({ hasText: 'Reference Document Type' }).first()
  await expect(header).toContainText('*')
})

test('a numeric child column sits against the right edge', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await openEvent(page, 'Notifications')

  // `Event Notifications.before` is an Int. Which cells are numbers is
  // `NUMERIC_CELLS`, generated from the same fieldtype map that decides how
  // the value is drawn, so this and the list cannot disagree about it.
  const header = page.getByRole('columnheader').filter({ hasText: 'Before' }).first()
  await expect(header).toHaveClass(/justify-end/)
})

test('rows can be ticked and removed together', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await openEvent(page, 'Notifications')

  await expect(page.getByText('3 rows')).toBeVisible()
  // The tick boxes are frappe-ui's own now, in the row's own padding rather
  // than in a column of ours — the same ones, and the same selector, the list
  // is ticked with.
  const rows = page.getByRole('tabpanel', { name: 'Notifications' })
    .locator('[data-slot="list-row"]')
  await rows.nth(0).locator('[data-slot="list-row-checkbox"]').click()
  await rows.nth(1).locator('[data-slot="list-row-checkbox"]').click()

  await page.getByRole('button', { name: 'Remove 2' }).click()
  await expect(page.getByText('1 row', { exact: true })).toBeVisible()

  // Not saved: this is the draft. Leaving the record without saving puts the
  // fixture back where it was, which is why nothing here presses Save.
  await expect(page.getByRole('button', { name: 'Save' })).toBeVisible()
})

test('select-all ticks every row of the grid it is in', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await openEvent(page, 'Notifications')

  const all = page.getByRole('tabpanel', { name: 'Notifications' })
    .getByRole('checkbox', { name: 'Select all' })
  await all.check()
  await expect(page.getByRole('button', { name: 'Remove 3' })).toBeVisible()

  // And untick puts it back rather than leaving the header ticked over an
  // empty selection.
  await all.uncheck()
  // `Remove <n>` and not `Remove` — every row carries its own "Remove this
  // row", which is three more buttons whose name starts with the same word.
  await expect(page.getByRole('button', { name: /^Remove \d+$/ })).toHaveCount(0)
})

test('a row can be dragged to a new position', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a touch screen cannot drag')
  await openEvent(page, 'Notifications')

  // Scoped to the tab's own panel: `[data-slot="list-row"]` is the list behind
  // the pane as well as both child grids, and the first one on the page is a
  // row of the Events list.
  const panel = page.getByRole('tabpanel', { name: 'Notifications' })
  const rows = panel.locator('[data-slot="list-row"]')
  const before = (at) => rows.nth(at).getByRole('spinbutton')

  await expect(before(0)).toHaveValue('30')

  // The number is the handle: the number *is* the position, so the thing you
  // drag to change it is the thing that says what it is.
  //
  // Dropped near the row's left edge rather than its centre: the centre of a
  // row of controls is inside a text input, and an input handles a drop itself
  // — the browser's own "drop text here" behaviour — so the drag ended with
  // nothing moved and no error.
  await rows
    .nth(2)
    .getByText('3', { exact: true })
    .dragTo(rows.first(), { targetPosition: { x: 20, y: 10 } })

  // Third row first, and the other two pushed down.
  await expect(before(0)).toHaveValue('1')
  await expect(before(1)).toHaveValue('30')
  await expect(before(2)).toHaveValue('2')
})
