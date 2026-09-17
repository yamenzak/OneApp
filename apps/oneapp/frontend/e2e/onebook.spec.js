// OneBook's five component screens, which no other spec reaches.
//
// Every list in this space is the engine's, checked where every list is
// checked. What is not is the five screens that ask ERPNext a question and draw
// the answer — the three statements, the reconciliation and the two ageings —
// and each of them is a payload shape rather than a list of records:
//
//   * a statement is an indented chart of accounts with a column per period,
//     and rows that are section gaps and rows that are totals;
//   * a reconciliation is two lists where the right-hand one is a function of
//     the row selected in the left;
//   * an ageing is a party against six buckets with a row of sums under it.
//
// None of those renders as a thinner list when it goes wrong. It renders as an
// empty panel, which is what a workspace with no data looks like — so a server
// change that quietly stops answering is invisible from the browser and from
// `check_screens.py` alike. That is why this file exists.
//
// The endpoints these five drive, named so that `scripts/affected.py` picks
// this file up when one of them changes. It attributes a Python change by the
// whitelisted dotted names in it, and a spec that drives an endpoint through a
// route rather than by name is a spec it cannot see the change reaching:
//
//   oneapp.onebook.statements.statement
//   oneapp.onebook.reconcile.accounts
//   oneapp.onebook.reconcile.feed
//   oneapp.onebook.reconcile.matches
//   oneapp.onebook.owing.owing
//
// `docs/ONEBOOK.md` §6.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/** Whether this site carries the app the whole space is over. */
async function hasErp(page, baseURL) {
  const response = await page.request.get(
    `${baseURL}/api/method/frappe.client.get_count?doctype=GL Entry`,
  )
  return response.ok()
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  test.skip(!(await hasErp(page, baseURL)), 'no ERPNext on this site')
})

test('a balance sheet balances', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onebook?screen=balance-sheet')

  const rows = page.locator('[data-slot="statement-row"]')
  await rows.first().waitFor({ timeout: 25_000 })

  // The totals ERPNext appends, which arrive with no parent and no indent and
  // are marked rather than dropped: a statement without them is a list of
  // accounts. Their labels are quoted in the report and unquoted here.
  const totals = page.locator('[data-slot="statement-total"]')
  await expect(totals.first()).toBeVisible()

  // The one assertion a balance sheet exists to make. Read off the rendered
  // cells rather than from the payload, because a sign convention applied in
  // the server and dropped in the component is exactly the failure this spec
  // is for.
  const named = async (label) => {
    const row = page.locator('[data-slot="statement-total"]', { hasText: label })
    const cell = row.locator('[data-slot="statement-value"]').last()
    const text = (await cell.innerText()).replace(/[^0-9.-]/g, '')
    return Number(text)
  }
  const assets = await named('Total Asset')
  const liabilities = await named('Total Liability')
  const equity = await named('Provisional Profit / Loss')
  expect(assets).toBeGreaterThan(0)
  expect(Math.abs(assets - (liabilities + equity))).toBeLessThan(1)

  expectNoRealErrors(errors)
})

test('a profit and loss is cut into periods and a trial balance is not',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)

    // A P&L's columns are a fiscal year cut by a periodicity, so it offers the
    // picker. A trial balance's are opening, movement and closing — cutting it
    // monthly would be a different report, and ERPNext's own does not offer it
    // either.
    await page.goto('/one/space/onebook?screen=profit-and-loss')
    await page.locator('[data-slot="statement-row"]').first()
      .waitFor({ timeout: 25_000 })
    await expect(page.locator('[data-slot="statement-periodicity"]')).toBeVisible()

    await page.goto('/one/space/onebook?screen=trial-balance')
    await page.locator('[data-slot="statement-row"]').first()
      .waitFor({ timeout: 25_000 })
    await expect(page.locator('[data-slot="statement-periodicity"]')).toHaveCount(0)

    expectNoRealErrors(errors)
  })

test('a bank line offers the documents it could be, best first',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/onebook?screen=reconcile')

    // The statement. The account picker answers itself where there is one
    // account, which is the only reason this screen has anything on it without
    // a click.
    const lines = page.locator('[data-slot="reconcile-line"]')
    await lines.first().waitFor({ timeout: 25_000 })

    // Nothing on the right until a line is chosen: the candidates are a
    // function of the selection and asking for them before there is one would
    // be a query with no question in it.
    await expect(page.locator('[data-slot="reconcile-candidate"]')).toHaveCount(0)

    await lines.first().click()
    const candidates = page.locator('[data-slot="reconcile-candidate"]')
    await candidates.first().waitFor({ timeout: 25_000 })

    // Ranked, and the fixture's first line carries the amount *and* the
    // reference of a payment it mirrors — `scripts/seed_erp_spaces.py`,
    // `STATEMENT`. So the top row is the four-of-four case and says so.
    await expect(candidates.first()).toContainText('Amount and reference agree')

    // And the verb is offered only once something is ticked, because matching
    // nothing is not a thing to let somebody press.
    await expect(page.locator('[data-slot="reconcile-match"]')).toBeDisabled()

    expectNoRealErrors(errors)
  })

test('an ageing puts the late before the large', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onebook?screen=owed-by-us')

  const parties = page.locator('[data-slot="owing-party"]')
  await parties.first().waitFor({ timeout: 25_000 })

  // The whole point of the screen. On the fixture the biggest balance is a
  // payroll accrual fifty-odd days old and the supplier owed less is inside
  // terms, so "worst first" and "biggest first" disagree — which is the only
  // arrangement in which this assertion means anything.
  const totals = page.locator('[data-slot="owing-totals"]')
  await expect(totals).toContainText('Past due')

  // Six buckets and a row of sums under them. `<0` is the one people forget:
  // everything not yet due, which is the difference between "we owe this" and
  // "we owe this and it is late".
  const header = page.locator('[data-slot="owing"] thead th')
  await expect(header).toHaveCount(8)
  await expect(header.nth(1)).toContainText('<0')

  // The documents behind a party, already in the payload — an ageing is read
  // by opening the one row somebody is about to ring about.
  await expect(page.locator('[data-slot="owing-documents"]')).toHaveCount(0)
  await parties.first().click()
  await expect(page.locator('[data-slot="owing-documents"]')).toBeVisible()

  expectNoRealErrors(errors)
})

test('an order says how much of itself is still to bill', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onebook?screen=orders')

  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 25_000 })

  // `per_billed` is the column this screen exists for, and the fixture's one
  // order is deliberately part-billed — two stages, one of them invoiced — so
  // the cell is a fraction rather than nought or a hundred, which is the only
  // state that proves the number is ERPNext's rather than a default.
  await expect(rows.first()).toContainText('65');

  expectNoRealErrors(errors)
})
