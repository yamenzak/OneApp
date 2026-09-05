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

  // An entry that is not the reader's own is a record somewhere else, and
  // clicking it goes there rather than opening a copy. The fixture's second
  // event belongs to the workspace rather than to this person.
  await page.getByText('Van collection').click()
  await expect(page).toHaveURL(/space\/zzmock/)
  await expect(page).toHaveURL(/record=/)

  expectNoRealErrors(errors)
})

test('an event of your own is written, edited and taken away again', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)
  // `ZZ ` because that is what the fixture's sweep looks for: a run that fails
  // between writing this and removing it leaves a row behind, and the next
  // seed is what takes it away.
  const subject = `ZZ Site visit ${Date.now()}`

  await signIn(page, baseURL)
  await page.goto('/one/calendar')
  await page.locator('[data-slot="diary"]').waitFor({ timeout: 25_000 })

  // The one thing this surface stores rather than merges. A whole day, because
  // that is the shape with no time picker in it — the pickers are frappe-ui's
  // and driving one is not what this test is about.
  await page.locator('[data-slot="diary-new"]').click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name').fill(subject)
  await dialog.getByLabel('All day').click()
  await dialog.getByLabel('Starts').click()
  await page.getByRole('button', { name: 'Today' }).last().click()
  await dialog.getByRole('button', { name: 'Save' }).click()

  // On the grid, in the reader's own diary rather than under any screen.
  await expect(page.getByText(subject)).toBeVisible({ timeout: 15_000 })

  // And it opens here rather than navigating away: an entry with no screen
  // behind it has nowhere else to be edited.
  await page.getByText(subject).click()
  await expect(page.getByRole('dialog').getByText('Edit event')).toBeVisible()

  await page.getByRole('dialog').getByRole('button', { name: 'Delete' }).click()
  await expect(page.getByText(subject)).toBeHidden({ timeout: 15_000 })

  expectNoRealErrors(errors)
})
