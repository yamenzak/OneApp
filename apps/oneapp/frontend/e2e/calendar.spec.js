// A screen read as a grid of days.
//
// The grid is frappe-ui's; what is ours is the mapping — which field is the
// start, which is the end, and the fact that the visible range is the request
// rather than a page. So this asserts the two things that could be wrong
// without anybody noticing: that the records land on their own days, and that
// moving to a month with nothing in it draws an empty month rather than the
// same events again.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test('a screen can be read as a calendar, and the records land on their days', async ({
  page,
  baseURL,
}) => {
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=events&type=calendar')

  const grid = page.locator('[data-slot="calendar"]')
  await grid.waitFor({ timeout: 25_000 })

  // The fixture's two, on the 10th and the 12th of whichever month this is.
  // Not a fixed date: the calendar opens on today's month, so a fixture pinned
  // to one would be on screen until that month passed. See `_this_month`.
  await expect(grid.getByText('Quarterly review')).toBeVisible()
  await expect(grid.getByText('Van collection')).toBeVisible()

  // And the month it is showing is this one.
  const month = new Date().toLocaleString('en', { month: 'long', year: 'numeric' })
  await expect(page.getByText(month)).toBeVisible()

  expectNoRealErrors(errors)
})

test('moving the calendar asks for the days it is showing', async ({ page, baseURL }) => {
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=events&type=calendar')
  const grid = page.locator('[data-slot="calendar"]')
  await grid.waitFor({ timeout: 25_000 })
  await expect(grid.getByText('Quarterly review')).toBeVisible()

  // The month before this one has nothing in it. If the calendar were drawing
  // whichever page of rows the list had fetched, the same two events would
  // still be on the grid — which is the bug this is here for.
  //
  // By position, because the grid's own chevrons carry an icon and no
  // accessible name — frappe-ui's markup, not ours. Today is the one button in
  // that row with a label, so back is the one before it.
  await page.getByRole('button', { name: 'Today' })
    .locator('xpath=preceding-sibling::button[1]')
    .click()
  await expect(grid.getByText('Quarterly review')).toBeHidden()

  // And coming back brings them with it, from a second request rather than
  // from anything kept.
  await page.getByRole('button', { name: 'Today' }).click()
  await expect(grid.getByText('Quarterly review')).toBeVisible()

  expectNoRealErrors(errors)
})

test('an event on the calendar opens the record it is', async ({ page, baseURL }) => {
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=events&type=calendar')
  const grid = page.locator('[data-slot="calendar"]')
  await grid.waitFor({ timeout: 25_000 })

  // Clicking an event is opening the record, not opening the grid's own
  // popover: a calendar here is a way of reading a screen's records, and the
  // record is the same one the list opens — same surface, same URL.
  await grid.getByText('Quarterly review').click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 15_000 })
  await expect(page).toHaveURL(/record=/)

  expectNoRealErrors(errors)
})
