// A screen read as bars down time.
//
// The chart is `frappe-gantt`, so what is worth asserting is the mapping and
// not the drawing: that a record with both dates becomes a bar, that one with
// only a start does not become anything, and that a bar is still the record it
// came from when you click it.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test('a screen can be read as a Gantt, and only spans become bars', async ({
  page,
  baseURL,
}) => {
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=events&type=gantt')

  const chart = page.locator('[data-slot="gantt"]')
  await chart.waitFor({ timeout: 25_000 })

  // The fixture's quarterly review has both a start and an end.
  await expect(chart.getByText('Quarterly review')).toBeVisible({ timeout: 15_000 })

  // The van collection has a start and no end, and a record with one date is a
  // moment rather than a bar of some invented length. It is on the same
  // screen's calendar, which is the whole point of the two being separate
  // types over the same rows.
  await expect(chart.getByText('Van collection')).toBeHidden()

  expectNoRealErrors(errors)
})

test('a bar opens the record it is', async ({ page, baseURL }) => {
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=events&type=gantt')
  const chart = page.locator('[data-slot="gantt"]')
  await chart.waitFor({ timeout: 25_000 })
  await expect(chart.getByText('Quarterly review')).toBeVisible({ timeout: 15_000 })

  // Same surface and same URL as the list's row and the calendar's event: a
  // view type is a way of reading a screen, never a separate place.
  await chart.getByText('Quarterly review').click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 15_000 })
  await expect(page).toHaveURL(/record=/)

  expectNoRealErrors(errors)
})
