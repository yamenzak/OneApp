// OneProject: ERPNext's Projects module, with the five things it cannot say.
//
// `docs/WORK.md` §12 is the argument. The record is ERPNext's `Project`, the
// unit of work is ERPNext's `Task` and the hours are ERPNext's `Timesheet`;
// what this space adds is the views and a handful of custom fields, exactly
// the way OnePeople adds to Frappe HR. Four claims are worth a browser, and
// every one of them is a thing that would render as merely *thinner* rather
// than throw:
//
//   * a board whose columns are rows a workspace named, over a doctype whose
//     own status is seven fixed words;
//   * a clock whose stretch lands on a Timesheet — the row an invoice reads —
//     rather than in a store of ours;
//   * a handover rule written as a sentence about a Task;
//   * and the assignment it makes, mirrored into the column a board can
//     actually group by.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const COLUMN = '[data-oneapp-column]'

/**
 * Whether this site carries ERPNext. The fixture says so and carries on, so a
 * bench without it is a normal thing to run the suite against.
 */
async function hasErp(page, baseURL) {
  const response = await page.request.get(
    `${baseURL}/api/method/frappe.client.get_count?doctype=Project`,
  )
  return response.ok()
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  test.skip(!(await hasErp(page, baseURL)), 'no ERPNext on this site')
})

test('the board draws the columns a workspace declared, over ERPNext’s tasks',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'a board is a desktop surface')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/oneproject?screen=tasks&type=board')
    await page.locator(COLUMN).first().waitFor({ timeout: 25_000 })

    // Four columns a team named, in the order the manifest declares — and not
    // ERPNext's seven, three of which are machinery. `custom_state` is a Link
    // to `One Task State` and `status` is written from its category, so a
    // rename here never reaches their controller.
    await expect(page.locator(COLUMN)).toHaveCount(4)
    await expect(page.locator(COLUMN).nth(0)).toContainText('Backlog')
    await expect(page.locator(COLUMN).nth(3)).toContainText('Done')
    await expect(page.getByText('Pending Review')).toHaveCount(0)

    expectNoRealErrors(errors)
  })

test('the clock writes a stretch onto a timesheet, which is what bills',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'covered on desktop')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/oneproject?screen=tasks&type=list')
    await page.locator('[data-slot="list-row"]')
      .filter({ hasText: 'zzGlazing package' })
      .first().click({ timeout: 25_000 })

    // A declared verb — `spaceview/actions.py` — so it is offered on the open
    // record and in the selection bar alike, and it is one line of manifest
    // rather than a control of its own.
    await page.locator('[data-slot="screen-actions"]').click()
    // Waited on rather than assumed: the click resolves when the menu closes,
    // and the sheet this test then looks for is written by the request behind
    // it.
    await Promise.all([
      page.waitForResponse((one) => one.url().includes('run_action')),
      page.getByRole('menuitem', { name: 'Start timing' }).click(),
    ])

    // And it is a Timesheet, not a store of ours: today's draft, with the row
    // the clock opened on it against the task's own project. Nothing to
    // reconcile — the thing that is running *is* the timesheet row, and it is
    // the row a Sales Invoice reads.
    await page.goto('/one/space/oneproject?screen=time&type=list')
    const draft = page.locator('[data-slot="list-row"]').filter({ hasText: 'Draft' })
    await expect(draft.first()).toBeVisible({ timeout: 25_000 })
    await draft.first().click()
    const logs = page
      .locator('[data-slot="object-pane"], [data-slot="record-page"]')
      .getByRole('table')
    // The project cell is a link picker rather than a label, so the value is
    // on the input — the same shape `erp-spaces.spec.js` reads a pre-filled
    // dialog through.
    await expect(logs.locator('input[value="zzCivic Library atrium"]').first())
      .toBeVisible({ timeout: 25_000 })

    await page.goto('/one/space/oneproject?screen=tasks&type=list')
    await page.locator('[data-slot="list-row"]')
      .filter({ hasText: 'zzGlazing package' })
      .first().click({ timeout: 25_000 })
    await page.locator('[data-slot="screen-actions"]').click()
    await Promise.all([
      page.waitForResponse((one) => one.url().includes('run_action')),
      page.getByRole('menuitem', { name: 'Stop timing' }).click(),
    ])

    // And away again, so the fixture's totals hold for the next run.
    await page.goto('/one/space/oneproject?screen=time&type=list')
    const made = page.locator('[data-slot="list-row"]').filter({ hasText: 'Draft' })
    await made.first().waitFor({ timeout: 25_000 })
    await made.first().locator('[data-slot="list-row-checkbox"]').click()
    await page.locator('[data-slot="selection-bar"]')
      .getByRole('button', { name: /^Delete/ })
      .click()
    await page.getByRole('dialog').getByRole('button', { name: 'Delete' }).click()
    await expect(made).toHaveCount(0, { timeout: 25_000 })

    expectNoRealErrors(errors)
  })

test('a handover rule reads as a sentence, and can be paused',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'covered on desktop')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/oneproject?screen=configuration')
    await page.getByRole('tab', { name: 'Handovers' }).click({ timeout: 25_000 })

    const rule = page.locator('[data-slot="routing-rule"]')
      .filter({ hasText: 'zzIn review goes to the reviewer' })
    await expect(rule).toBeVisible({ timeout: 25_000 })
    // The row says what the rule does in the words it was written in, rather
    // than `custom_state == "In review"` — which is what is stored and what
    // Frappe evaluates, and not what anybody wrote.
    await expect(rule).toContainText('State is In review')
    await expect(rule).toContainText('one after another')

    // Pausing is the control people reach for: a rule that is wrong at month
    // end is one to stop, not one to rewrite from memory.
    const paused = page.waitForResponse((one) =>
      one.url().includes('set_routing_enabled'))
    await rule.getByRole('switch').click()
    await paused
    await expect(rule.getByText('Off', { exact: true })).toBeVisible()

    const started = page.waitForResponse((one) =>
      one.url().includes('set_routing_enabled'))
    await rule.getByRole('switch').click()
    await started
    await expect(rule.getByText('On', { exact: true })).toBeVisible()

    expectNoRealErrors(errors)
  })

test('a task that reaches review lands on somebody', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a board is a desktop surface')

  // The whole claim, end to end and through the surface a team uses: move a
  // card into In review and the rule hands it to the reviewer.
  await page.goto('/one/space/oneproject?screen=tasks&type=board')
  await page.locator(COLUMN).first().waitFor({ timeout: 25_000 })
  const card = page.locator('[data-oneapp-column="Backlog"] article', {
    hasText: 'zzGlazing package',
  })
  await expect(card).toBeVisible()
  await card.dragTo(page.locator('[data-oneapp-column="In review"]'))

  // And it is on somebody's list now, which the card says because the owner
  // column is mirrored from the assignment — `onetask/assignment.py`. The
  // assignment itself is Frappe's ToDo, written by the rule through
  // `assign_to.add`: one store, `docs/WORK.md` §2.
  await expect(
    page.locator('[data-oneapp-column="In review"] article',
      { hasText: 'zzGlazing package' }),
  ).toContainText('Administrator', { timeout: 25_000 })

  // Put the fixture back: the column it came from, and nobody on it.
  // Un-assigning is a thing you do to a record rather than a field you clear —
  // `assign.spec.js` — and the column follows it, which is the other half of
  // the mirror.
  await page.locator('[data-oneapp-column="In review"] article', {
    hasText: 'zzGlazing package',
  }).dragTo(page.locator('[data-oneapp-column="Backlog"]'))
  await expect(
    page.locator('[data-oneapp-column="Backlog"] article',
      { hasText: 'zzGlazing package' }),
  ).toBeVisible({ timeout: 25_000 })

  await page.goto('/one/space/oneproject?screen=tasks&type=list')
  await page.locator('[data-slot="list-row"]')
    .filter({ hasText: 'zzGlazing package' })
    .first().click({ timeout: 25_000 })
  await page.locator('[data-slot="record-about"]').click()
  await page.locator('[data-slot="assign"]').click()
  await page.getByRole('option', { name: /Administrator/ }).click()
  await page.keyboard.press('Escape')

  await page.goto('/one/space/oneproject?screen=tasks&type=list')
  await expect(
    page.locator('[data-slot="list-row"]').filter({ hasText: 'zzGlazing package' }),
  ).not.toContainText('Administrator', { timeout: 25_000 })
})
