// The diary: every calendar this workspace has, on one grid.
//
// The screen calendar's spec covers the grid itself. What is worth driving a
// browser for here is the merge — that a record from a space's screen and an
// event from somebody's own diary land on the same month, that the rail lists
// both, that switching one off takes its entries with it, and that clicking a
// record goes back to the screen it belongs to.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test('the diary merges every calendar the workspace has', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the rail of calendars is a desktop surface')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/calendar')
  await page.locator('[data-slot="diary"]').waitFor({ timeout: 25_000 })

  // The fixture's events, from MockSpace's own screen.
  await expect(page.getByText('Quarterly review')).toBeVisible()

  // And the rail says what it is made of: the reader's own diary, and every
  // screen that declares a calendar, with the space it belongs to.
  const sources = page.locator('[data-slot="diary-source"]')
  await expect(sources.filter({ hasText: 'Your diary' })).toBeVisible()
  await expect(sources.filter({ hasText: 'Events' })).toBeVisible()
  await expect(sources.filter({ hasText: 'MockSpace' })).toBeVisible()

  expectNoRealErrors(errors)
})

test('one record reaches the grid once, however many calendars hold it', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/calendar')
  await page.locator('[data-slot="diary"]').waitFor({ timeout: 25_000 })

  // The fixture's events are owned by this user *and* on MockSpace's events
  // screen — two sources, one meeting. Drawn twice, a calendar is one nobody
  // trusts about the rest of the week.
  await expect(page.getByText('Quarterly review')).toHaveCount(1)

  expectNoRealErrors(errors)
})

test('switching a calendar off takes its entries with it', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the rail of calendars is a desktop surface')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/calendar')
  await page.locator('[data-slot="diary"]').waitFor({ timeout: 25_000 })
  await expect(page.getByText('Quarterly review')).toBeVisible()

  await page.locator('[data-slot="diary-source"]').filter({ hasText: 'Events' }).click()
  await expect(page.getByText('Quarterly review')).toBeHidden()

  // And the row is still there to switch back on — a filter that removes its
  // own control is a filter nobody can undo.
  await page.locator('[data-slot="diary-source"]').filter({ hasText: 'Events' }).click()
  await expect(page.getByText('Quarterly review')).toBeVisible()

  expectNoRealErrors(errors)
})

test('an entry opens the record it belongs to, on its own screen', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/calendar')
  await page.locator('[data-slot="diary"]').waitFor({ timeout: 25_000 })

  // Nothing on this page is stored here: an entry is a record somewhere else,
  // and clicking it goes there rather than opening a copy.
  await page.getByText('Quarterly review').click()
  await expect(page).toHaveURL(/space\/zzmock/)
  await expect(page).toHaveURL(/record=/)

  expectNoRealErrors(errors)
})
