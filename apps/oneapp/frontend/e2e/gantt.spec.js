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
  await expect(page).toHaveURL(/at=record:/)

  expectNoRealErrors(errors)
})

test('a bar that waits on another has an arrow to it', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the chart is a desktop surface')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)

  // The compliance register, which is a register of *lengths*: a licence runs
  // from its issue date to its expiry, and the renewal that replaces it is the
  // bar after it. `renews` is the tree's parent and the chart's dependency —
  // the same statement drawn two ways, under it and after it.
  await page.goto('/one/space/zzmock?screen=compliance&type=gantt')
  await page.locator('[data-slot="gantt"] svg').waitFor({ timeout: 20_000 })

  // Two renewals in the fixture, so at least one arrow. Drawn by the chart
  // from `dependencies`, which is the whole of what this had to hand it.
  const arrows = page.locator('[data-slot="gantt"] g.arrow path')
  await expect(arrows.first()).toBeVisible({ timeout: 20_000 })

  expectNoRealErrors(errors)
})
