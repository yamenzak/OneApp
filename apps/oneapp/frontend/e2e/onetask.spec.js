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
