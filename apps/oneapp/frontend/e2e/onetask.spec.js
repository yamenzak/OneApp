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

  // Rolled up on the project as tasks move — the fixture leaves six open (one
  // of them the milestone) and one done. A portfolio of forty projects is one
  // query rather than forty.
  await expect(row).toContainText('6')

  expectNoRealErrors(errors)
})

test('the work is one table, so a task keeps its id when it joins a project', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')

  // The claim `docs/WORK.md` §3 rests on: a task in a project and a task in
  // somebody's own list are one row with and without a project on it, so
  // placing one is a link rather than a migration.
  //
  // The ids say the *other* half of it. A task on a project is named after
  // that project's key — REEM-14, the thing people say to each other — and one
  // on no project falls back to the plain series; both are rows of the same
  // screen, which is what "one table" means.
  await page.goto('/one/space/onetask?screen=inbox')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await expect(page.getByText(/TASK-\d+/).first()).toBeVisible()

  await page.goto('/one/space/onetask?screen=tasks&type=list')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await expect(page.getByText(/REEM-\d+/).first()).toBeVisible()
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

// --- the plan ---------------------------------------------------------------
//
// `docs/WORK.md` stage 5. One direction is stored and the other is the same
// edge read backwards; a loop is refused before it is saved; and a plan slips
// forward and never back.

test('the plan draws what waits for what, and only what is a sequence', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'a Gantt is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto(
    '/one/space/onetask?screen=tasks&type=gantt&narrow=project:zzAl Reem fit-out',
  )
  await page.locator('[data-slot="gantt"] .bar').first().waitFor({ timeout: 25_000 })

  // Four edges in a line, drawn as arrows. `One Task Link` holds a fifth —
  // a "relates to" between the snagging walk and the glazing quote — and the
  // chart must not draw it: a pointer somebody left is not a sequence.
  // One `<path>` per arrow, inside the chart's own `arrow` layer, each naming
  // the two bars it joins.
  await expect(page.locator('[data-slot="gantt"] .arrow path')).toHaveCount(4)

  // And the date the project is measured by is a diamond rather than a bar.
  await expect(page.locator('[data-slot="gantt"] .oneapp-milestone')).toHaveCount(1)

  expectNoRealErrors(errors)
})

test('a task says what it blocks, which is the same rows read backwards', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the record rail is a desktop surface')

  await page.goto('/one/space/onetask?screen=tasks&type=list')
  await page.locator('[data-slot="list-row"]').filter({ hasText: 'zzChase the glazing quote' })
    .first().click({ timeout: 25_000 })
  await page.locator(RAIL).waitFor({ timeout: 25_000 })

  // Sub-tasks and Blocks are both the tasks screen — one reached by
  // `parent_task`, one by the `links` rows pointing back — so they are two
  // tabs and not one. They shared a value once, and the record drew both
  // lists at the same time.
  await page.locator(RAIL).getByRole('tab', { name: 'Blocks' }).click()
  await expect(page.locator('[data-slot="related-door"]')).toHaveCount(1)
  const rows = page.locator('[data-slot="object-pane"], [data-slot="record-page"]')
    .getByRole('table')
  await expect(rows.getByText('zzIssue the revised layout')).toBeVisible()
  // The "relates to" edge is not a block.
  await expect(rows.getByText('zzSnagging walk with the client')).toHaveCount(0)
})

// --- time, and the window a team works in -----------------------------------
//
// `docs/WORK.md` stage 6. A running clock is a row with no end on it, so the
// browser's part is small and the whole of it is here: press Start, see the
// stretch, press Stop.

test('the clock starts and stops, and one person runs one of them', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onetask?screen=tasks&type=list')
  await page.locator('[data-slot="list-row"]').filter({ hasText: 'zzHandover pack' })
    .first().click({ timeout: 25_000 })
  await page.locator(RAIL).waitFor({ timeout: 25_000 })

  // A declared verb — `spaceview/actions.py` — so it is offered on the record
  // and in the selection bar alike, and it is one line of manifest rather than
  // a control of its own.
  await page.locator('[data-slot="screen-actions"]').click()
  // Waited on rather than assumed: the click resolves when the menu closes,
  // and the row this test then looks for is written by the request behind it.
  await Promise.all([
    page.waitForResponse((one) => one.url().includes('run_action')),
    page.getByRole('menuitem', { name: 'Start timing' }).click(),
  ])

  // What is running is a row with no end on it. Nothing to reconcile: this is
  // the timesheet, not a flag beside one.
  await page.goto('/one/space/onetask?screen=my-time&type=list')
  const row = page.locator('[data-slot="list-row"]')
    .filter({ hasText: 'zzHandover pack' })
  await expect(row.first()).toBeVisible({ timeout: 25_000 })

  await page.goto('/one/space/onetask?screen=tasks&type=list')
  await page.locator('[data-slot="list-row"]').filter({ hasText: 'zzHandover pack' })
    .first().click({ timeout: 25_000 })
  await page.locator('[data-slot="screen-actions"]').click()
  await Promise.all([
    page.waitForResponse((one) => one.url().includes('run_action')),
    page.getByRole('menuitem', { name: 'Stop timing' }).click(),
  ])

  // And away again, so the fixture's totals hold for the next run.
  await page.goto('/one/space/onetask?screen=my-time&type=list')
  const made = page.locator('[data-slot="list-row"]').filter({ hasText: 'zzHandover pack' })
  await made.first().waitFor({ timeout: 25_000 })
  await made.first().locator('[data-slot="list-row-checkbox"]').click()
  await page.locator('[data-slot="selection-bar"]')
    .getByRole('button', { name: /^Delete/ })
    .click()
  await page.getByRole('dialog').getByRole('button', { name: 'Delete' }).click()
  await expect(made).toHaveCount(0, { timeout: 25_000 })

  expectNoRealErrors(errors)
})

test('a week of somebody’s time adds up, and says what each stretch was on', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onetask?screen=my-time&type=dashboard')
  // 645 minutes on the fit-out and 75 on the relaunch — the stretches the
  // fixture writes, summed rather than counted: a bar of how many *stretches*
  // went on a project is not the question a timesheet is opened with.
  await expect(page.getByText('720')).toBeVisible({ timeout: 25_000 })

  await page.goto('/one/space/onetask?screen=my-time&type=calendar')
  // Each stretch is drawn by the task it was against, not by the id of the
  // link that holds it — `lib/screen/identity.js`.
  await expect(page.getByText(/zzIssue the revised/).first())
    .toBeVisible({ timeout: 25_000 })
  await expect(page.getByText(/^TIME-\d+/)).toHaveCount(0)

  expectNoRealErrors(errors)
})

test('a cycle is a window, and the work says which one it is in', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')

  await page.goto('/one/space/onetask?screen=cycles&type=list')
  await page.locator('[data-slot="list-row"]').filter({ hasText: 'zzSprint 21' })
    .first().click({ timeout: 25_000 })
  await page.locator(RAIL).waitFor({ timeout: 25_000 })

  // A cycle holds no tasks of its own — `docs/WORK.md` §4, one container — so
  // its work is the tasks that name it, which is a declared tab like any
  // other.
  await page.locator(RAIL).getByRole('tab', { name: 'Work' }).click()
  await expect(page.getByText('zzIssue the revised layout').first()).toBeVisible()
})

// --- automations ------------------------------------------------------------
//
// `docs/WORK.md` stage 7. Frappe's own Assignment Rule, wearing the sentence
// somebody would say: when a task reaches In review, hand it to the reviewer.
// The assignment itself is a ToDo, like every other assignment in the product.

test('a handover rule reads as a sentence, and can be paused', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onetask?screen=configuration')
  await page.getByRole('tab', { name: 'Handovers' }).click({ timeout: 25_000 })

  const rule = page.locator('[data-slot="routing-rule"]')
    .filter({ hasText: 'zzIn review goes to the reviewer' })
  await expect(rule).toBeVisible({ timeout: 25_000 })
  // The row says what the rule does in the words it was written in, rather
  // than `state == "In review"` — which is what is stored and what Frappe
  // evaluates, and not what anybody wrote.
  await expect(rule).toContainText('State is In review')
  await expect(rule).toContainText('one after another')

  // Pausing is the control people reach for: a rule that is wrong at month
  // end is one to stop, not one to rewrite from memory.
  const paused = page.waitForResponse((one) => one.url().includes('set_routing_enabled'))
  await rule.getByRole('switch').click()
  await paused
  await expect(rule.getByText('Off', { exact: true })).toBeVisible()

  const started = page.waitForResponse((one) => one.url().includes('set_routing_enabled'))
  await rule.getByRole('switch').click()
  await started
  await expect(rule.getByText('On', { exact: true })).toBeVisible()

  expectNoRealErrors(errors)
})

test('a task that reaches review lands on somebody', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a board is a desktop surface')

  // The whole claim, end to end and through the surface a team uses: move a
  // card into In review and the rule hands it to the reviewer.
  await page.goto('/one/space/onetask?screen=tasks&type=board')
  await page.locator(COLUMN).first().waitFor({ timeout: 25_000 })
  const card = page.locator('[data-oneapp-column="Backlog"] article', {
    hasText: 'zzHandover pack',
  })
  await expect(card).toBeVisible()
  await card.dragTo(page.locator('[data-oneapp-column="In review"]'))

  // And it is on somebody's list now, which the card says because the owner
  // column is mirrored from the assignment — `onetask/assignment.py`. The
  // assignment itself is Frappe's ToDo, written by the rule through
  // `assign_to.add`: one store, `docs/WORK.md` §2.
  await expect(
    page.locator('[data-oneapp-column="In review"] article', { hasText: 'zzHandover pack' }),
  ).toContainText('Administrator', { timeout: 25_000 })

  // Put the fixture back: the column it came from, and nobody on it.
  // Un-assigning is a thing you do to a record rather than a field you clear —
  // `assign.spec.js` — and the column follows it, which is the other half of
  // the mirror.
  await page.locator('[data-oneapp-column="In review"] article', {
    hasText: 'zzHandover pack',
  }).dragTo(page.locator('[data-oneapp-column="Backlog"]'))
  await expect(
    page.locator('[data-oneapp-column="Backlog"] article', { hasText: 'zzHandover pack' }),
  ).toBeVisible({ timeout: 25_000 })

  await page.goto('/one/space/onetask?screen=tasks&type=list')
  await page.locator('[data-slot="list-row"]').filter({ hasText: 'zzHandover pack' })
    .first().click({ timeout: 25_000 })
  await page.locator('[data-slot="record-about"]').click()
  await page.locator('[data-slot="assign"]').click()
  await page.getByRole('option', { name: /Administrator/ }).click()
  await page.keyboard.press('Escape')

  await page.goto('/one/space/onetask?screen=tasks&type=list')
  await expect(
    page.locator('[data-slot="list-row"]').filter({ hasText: 'zzHandover pack' }),
  ).not.toContainText('Administrator', { timeout: 25_000 })
})
