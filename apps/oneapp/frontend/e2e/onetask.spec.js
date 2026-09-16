// OneTask: the work, on a board that is a project.
//
// `docs/WORK.md` is the argument and three of its claims are worth a browser.
//
// That the **board's columns are data** — `One Task State` rows rather than a
// Select on the doctype, which is what lets a workspace rename one. The engine
// still knows which column means finished, because the state's category is
// copied down onto the task as it saves.
//
// That **a task with no project is the inbox**, which is one filter over the
// same rows rather than a second store.
//
// And that a **project counts its own work**, rolled up as tasks move rather
// than counted on every read.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const COLUMN = '[data-oneapp-column]'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the board draws the columns a workspace declared, in their order', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'a board is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onetask?screen=tasks&type=board')
  const columns = page.locator(COLUMN)
  await columns.first().waitFor({ timeout: 25_000 })

  // Four rows in `One Task State`, in the order the manifest declares — a Link
  // column has no order of its own, which is why the order is declared and the
  // set is not.
  await expect(columns).toHaveCount(4)
  for (const value of ['Backlog', 'In progress', 'In review', 'Done']) {
    await expect(page.locator(`[data-oneapp-column="${value}"]`)).toBeVisible()
  }

  // And the work is in them.
  await expect(
    page.locator('[data-oneapp-column="In progress"] article').first(),
  ).toBeVisible()

  expectNoRealErrors(errors)
})

test('a task with no project is in the inbox, and one with a project is not', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onetask?screen=inbox')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  // Unplaced is not a flag: `project is not set` is the whole of the screen.
  await expect(page.getByText('zzRing the landlord back')).toBeVisible()
  await expect(page.getByText('zzChase the glazing quote')).toHaveCount(0)

  expectNoRealErrors(errors)
})

test('a project says how much of its work is left, without counting it', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onetask?screen=projects&type=list')
  const row = page.locator('[data-slot="list-row"]').filter({ hasText: 'zzAl Reem' })
  await expect(row).toBeVisible({ timeout: 25_000 })

  // Rolled up on the project as tasks move — the fixture leaves five open and
  // one done. A portfolio of forty projects is one query rather than forty.
  await expect(row).toContainText('5')

  expectNoRealErrors(errors)
})

test('the work is one table, so a task keeps its id when it joins a project', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')

  // The claim `docs/WORK.md` §3 rests on: a task in a project and a task in
  // somebody's own list are one row with and without a project on it, so
  // placing one is a link rather than a migration. Read off the ids: the
  // inbox's tasks and the board's come from the same series.
  await page.goto('/one/space/onetask?screen=inbox')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await expect(page.getByText(/TASK-\d+/).first()).toBeVisible()

  await page.goto('/one/space/onetask?screen=tasks&type=list')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await expect(page.getByText(/TASK-\d+/).first()).toBeVisible()
})

// --- the project ------------------------------------------------------------
//
// `docs/WORK.md` stage 4: a project record where the work, the files and the
// mail about it are tabs of one thing — and where "this project's work, as a
// board" is the real screen narrowed rather than a second board drawn inside a
// tab. `lib/screen/narrowing.js`.

const RAIL = '[data-slot="record-tabs-rail"]'
const REEM = '/one/space/onetask?screen=projects&at=record:zzAl%20Reem%20fit-out'

test('a project is where its work, its files and its mail meet', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the record rail is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto(REEM)
  await page.locator(RAIL).waitFor({ timeout: 25_000 })

  // The work, the month it happens in, what was said here and what was sent —
  // four tabs, plus the door to the one file manager this product has.
  for (const tab of ['Details', 'Tasks', 'Calendar', 'Activity', 'Mail']) {
    await expect(page.locator(RAIL).getByRole('tab', { name: tab, exact: true }))
      .toBeVisible()
  }
  await expect(page.locator('[data-slot="record-files-door"]')).toBeVisible()

  // And exactly one way into the tasks. Three screens in this space are over
  // `One Task` and all three point back through `project`; two of them are
  // lenses on the space — this person's half of it, the ones on no project —
  // and narrowing either to a project asks a question nobody asked.
  await expect(page.locator(RAIL).getByRole('tab', { name: 'My tasks' })).toHaveCount(0)
  await expect(page.locator(RAIL).getByRole('tab', { name: 'Inbox' })).toHaveCount(0)

  expectNoRealErrors(errors)
})

test('a project opens its own board, and the board says whose it is', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'a board is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto(REEM)
  await page.locator(RAIL).getByRole('tab', { name: 'Tasks', exact: true })
    .click({ timeout: 25_000 })

  // The tab is a table, and a project is looked at as a board — so the tab
  // opens the tasks screen rather than growing a board of its own.
  await page.locator('[data-slot="related-door"]').click()
  await expect(page).toHaveURL(/[?&]narrow=project(%3A|:)zzAl/)
  await page.locator(COLUMN).first().waitFor({ timeout: 25_000 })

  // Narrowed, and saying so where somebody is looking rather than only inside
  // the filter panel.
  await expect(page.locator('[data-slot="narrowed-to"]')).toContainText('zzAl Reem')
  await expect(page.locator('article').filter({ hasText: 'zzAgree the sitemap' }))
    .toHaveCount(0)
  await expect(page.locator('article').filter({ hasText: 'zzChase the glazing quote' }))
    .toBeVisible()

  // It survives a change of view — the same question drawn another way — and
  // it is a filter underneath, so taking it off widens the screen.
  await page.getByRole('link', { name: 'Calendar' }).first().click()
  await expect(page).toHaveURL(/[?&]narrow=project(%3A|:)zzAl/)

  await page.goto(`/one/space/onetask?screen=tasks&type=board&narrow=project:zzAl Reem fit-out`)
  await page.locator('[data-slot="narrowed-to"]').click({ timeout: 25_000 })
  await expect(page).not.toHaveURL(/narrow=/)
  await expect(
    page.locator('article').filter({ hasText: 'zzAgree the sitemap' }),
  ).toBeVisible({ timeout: 25_000 })

  expectNoRealErrors(errors)
})

test('a task made from a project belongs to it without being told twice', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')

  await page.goto(REEM)
  await page.locator(RAIL).getByRole('tab', { name: 'Tasks', exact: true })
    .click({ timeout: 25_000 })

  const MADE = `zzFrom the project ${Date.now()}`
  await page.locator('[data-slot="related-new"]').click()
  const dialog = page.locator('[data-oneapp="form-dialog"]')
  await expect(dialog).toBeVisible()
  // The link the tab filtered on arrives filled in, which is the whole reason
  // to make a task from here rather than from the screen.
  await expect(dialog.getByRole('combobox', { name: /^Project/ }))
    .toHaveValue('zzAl Reem fit-out')
  await dialog.getByRole('textbox', { name: /^Title/ }).fill(MADE)
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()

  // The tab it was made on is the link, so the project arrives filled in and
  // the row comes back to the tab that made it.
  await expect(page.getByText(MADE).first()).toBeVisible({ timeout: 25_000 })

  // And away again through the list, because a fixture that grows by one task
  // a run is a fixture whose counts nobody can assert.
  await page.goto('/one/space/onetask?screen=tasks&type=list')
  const row = page.locator('[data-slot="list-row"]').filter({ hasText: MADE })
  await row.first().waitFor({ timeout: 25_000 })
  await row.first().locator('[data-slot="list-row-checkbox"]').click()
  await page.locator('[data-slot="selection-bar"]')
    .getByRole('button', { name: /^Delete/ })
    .click()
  await page.getByRole('dialog').getByRole('button', { name: 'Delete' }).click()
  await expect(page.locator('[data-slot="list-row"]').filter({ hasText: MADE }))
    .toHaveCount(0, { timeout: 25_000 })
})
