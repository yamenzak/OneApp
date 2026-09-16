// The diary: every calendar this workspace has, on one grid.
//
// The screen calendar's spec covers the grid itself. What is worth driving a
// browser for here is the merge — that a record from a space's screen and an
// event from somebody's own diary land on the same month, that the rail lists
// both, that switching one off takes its entries with it, and that clicking a
// record goes back to the screen it belongs to.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * Open the diary on the company's month rather than the reader's own.
 *
 * A calendar is a question and Mine is the one it opens with — `docs/WORK.md`
 * §6 — so a test about *the merge* has to say which lens it means. The
 * fixture's events belong to MockSpace's own screen, which cannot say whose a
 * row is and is therefore not in anybody's personal week.
 */
async function everyone(page) {
  await page.locator('[data-slot="diary"]').waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="diary-lens-everyone"]').click()
  await page.locator('[data-slot="diary-source"]')
    .filter({ hasText: 'Events' })
    .waitFor({ timeout: 20_000 })
}

test('the diary merges every calendar the workspace has', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the rail of calendars is a desktop surface')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/calendar')
  await everyone(page)

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
  await everyone(page)

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
  await everyone(page)
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
  await everyone(page)

  // An entry that is not the reader's own is a record somewhere else, and
  // clicking it goes there rather than opening a copy. The fixture's second
  // event belongs to the workspace rather than to this person.
  await page.getByText('Van collection').click()
  await expect(page).toHaveURL(/space\/zzmock/)
  await expect(page).toHaveURL(/at=record:/)

  expectNoRealErrors(errors)
})

test('the diary opens on your own week, and one press shows the company\'s', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the rail of calendars is a desktop surface')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/calendar')
  await page.locator('[data-slot="diary"]').waitFor({ timeout: 25_000 })

  // Mine is what it opens with: a calendar opened on a Tuesday morning is a
  // question about your Tuesday — `docs/WORK.md` §6. MockSpace's events screen
  // cannot say whose a row is, so it is not one of your sources.
  const sources = page.locator('[data-slot="diary-source"]')
  await expect(sources.filter({ hasText: 'Your diary' })).toBeVisible()
  await expect(sources.filter({ hasText: 'Events' })).toHaveCount(0)

  // And the other question is one press away, with that source in it.
  await page.locator('[data-slot="diary-lens-everyone"]').click()
  await expect(sources.filter({ hasText: 'Events' })).toBeVisible({ timeout: 20_000 })

  // Back again, and it is a question asked of the server rather than a filter
  // over what arrived: Everyone reads sources Mine never fetched.
  await page.locator('[data-slot="diary-lens-mine"]').click()
  await expect(sources.filter({ hasText: 'Events' })).toHaveCount(0, { timeout: 20_000 })

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

  await page.getByRole('dialog').getByRole('button', { name: 'Delete for ever' }).click()
  await expect(page.getByText(subject)).toBeHidden({ timeout: 15_000 })

  expectNoRealErrors(errors)
})

// The diary on the desk — `docs/DESKTOP.md` stage 6. The week is the thing you
// check *against* what you are doing, so the interesting claim is not that a
// window opens but that the page under it stays where it was.
const diaryTile = (page) => page.locator('[data-slot="dock-tile"][data-app="calendar"]')

test('the diary opens in a window, with its one verb in the bar', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'a window is a sheet on a phone')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/onehr?screen=people')
  await diaryTile(page).waitFor({ timeout: 25_000 })

  const here = page.url()
  await diaryTile(page).click()

  const window = page.locator('[data-window="onecalendar"]')
  await expect(window).toBeVisible({ timeout: 20_000 })
  await expect(window.locator('[data-slot="diary"]')).toBeVisible({ timeout: 20_000 })

  // New event is in the title bar rather than in a band of its own under it:
  // one button under a name is the row OneCloud spent a stage removing.
  await expect(window.locator('[data-slot="window-handle"] [data-slot="diary-new"]')).toBeVisible()

  // And the quotation, or the people screen, is where it was.
  expect(page.url()).toBe(here)
  await expect(page.locator('[data-slot="space-switcher"]')).toContainText('OnePeople')

  expectNoRealErrors(errors)
})
