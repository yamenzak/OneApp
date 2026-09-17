// OneCRM: a pipeline whose columns a workspace owns.
//
// `docs/ONECRM.md` stage 1. ERPNext's `Sales Stage` is a row with a name and
// nothing else — no order, so a board drawn from it came out Negotiation,
// Prospecting, Proposal; no colour; and no way for the engine to ask which
// column means won. `One Deal Stage` is a row that carries all three, and
// `onecrm/deal.py` writes ERPNext's own `status` and `probability` from it.
//
// Two claims, and both would render as merely *thinner* rather than throw:
// the columns are the stages a team declared, in their order and including the
// empty ones — a stage you cannot drop a card into is a stage that never gets
// its first deal — and moving a card rewrites ERPNext's status underneath.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const COLUMN = '[data-oneapp-column]'

/** One row of the deals list. A list is a table here, so a row is a row. */
const deal = (page, title) => page.getByRole('row').filter({ hasText: title })

/** Whether this site carries ERPNext, whose Opportunity is the deal. */
async function hasErp(page, baseURL) {
  const response = await page.request.get(
    `${baseURL}/api/method/frappe.client.get_count?doctype=Opportunity`,
  )
  return response.ok()
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  test.skip(!(await hasErp(page, baseURL)), 'no ERPNext on this site')
})

test('the pipeline is the stages a workspace declared, empty ones included',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'a board is a desktop surface')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/onecrm?screen=deals&type=board')
    await page.locator(COLUMN).first().waitFor({ timeout: 25_000 })

    // Seven columns, in the order `One Deal Stage.position` puts them —
    // read off the rows rather than declared in the manifest, which is what
    // makes moving a stage one drag instead of a release.
    await expect(page.locator(COLUMN)).toHaveCount(7)
    for (const [at, name] of [
      [0, 'New'], [1, 'Qualifying'], [2, 'Proposal'], [3, 'Negotiation'],
      [4, 'On hold'], [5, 'Won'], [6, 'Lost'],
    ]) {
      await expect(page.locator(COLUMN).nth(at)).toContainText(name)
    }

    // And the empty one is drawn. A Link board used to show only the values on
    // the page, so a stage nothing was in did not exist — and the whole use of
    // a board is moving a card into a column.
    const idle = page.locator('[data-oneapp-column="On hold"]')
    await expect(idle).toBeVisible()
    await expect(idle.locator('article')).toHaveCount(0)

    // None of ERPNext's own eight, which is the other half: their stages are
    // the stages of an enterprise software sale and this product opens for a
    // plumber too.
    await expect(page.getByText('Perception Analysis')).toHaveCount(0)

    expectNoRealErrors(errors)
  })

test('a stage carries what the desk assumes, and ERPNext agrees', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'a board is a desktop surface')

  await page.goto('/one/space/onecrm?screen=deals&type=board')
  await page.locator(COLUMN).first().waitFor({ timeout: 25_000 })

  // An adjacent column on purpose. Playwright scrolls a drag target into view,
  // and on a seven-column board that moves the card out from under the pointer
  // before the drop — which picks up whichever card the scroll left there.
  const card = page.locator('[data-oneapp-column="New"] article', {
    hasText: 'zzHarbour Point signage',
  })
  await expect(card).toBeVisible()
  await card.dragTo(page.locator('[data-oneapp-column="Qualifying"]'))
  await expect(
    page.locator('[data-oneapp-column="Qualifying"] article',
      { hasText: 'zzHarbour Point signage' }),
  ).toBeVisible({ timeout: 25_000 })

  // The probability a deal arrives with is the column's, written on the way in
  // — `onecrm/deal.py`. It was 10 in New and Qualifying assumes 25.
  await page.goto('/one/space/onecrm?screen=deals&type=list')
  await expect(
    deal(page, 'zzHarbour Point signage'),
  ).toContainText('25', { timeout: 25_000 })

  // And back, so the fixture holds for the next run.
  await page.goto('/one/space/onecrm?screen=deals&type=board')
  await page.locator('[data-oneapp-column="Qualifying"] article', {
    hasText: 'zzHarbour Point signage',
  }).dragTo(page.locator('[data-oneapp-column="New"]'))
  await expect(
    page.locator('[data-oneapp-column="New"] article',
      { hasText: 'zzHarbour Point signage' }),
  ).toBeVisible({ timeout: 25_000 })
})

test('the status ERPNext reads is written from the stage', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  // Nothing seeds a status: `onecrm/deal.py` writes it from the stage's
  // category on save, which is the whole claim and would be untestable if the
  // fixture asserted both. So the badge on a deal in a Won column is ERPNext's
  // own word for won, and the one in a Lost column is theirs for lost.
  await page.goto('/one/space/onecrm?screen=deals&type=list')
  await expect(deal(page, 'zzMeridian studio fit-out'))
    .toContainText('Converted', { timeout: 25_000 })
  await expect(deal(page, 'zzAlmond Court roof terrace')).toContainText('Lost')
  // And a deal on hold is not a loss: their status is still Open, which is why
  // the category is a word of its own rather than folded into one of theirs.
  await expect(deal(page, 'zzAlmond warehouse mezzanine')).toContainText('Open')

  expectNoRealErrors(errors)
})

// `docs/ONECRM.md` stage 5 — a call is a record, and the timeline is where it
// earns its keep. Two claims: the deal's column carries the call beside the
// comment and the change, and the verb opens a New dialog already about this
// deal rather than writing anything.
test('a call is on the deal it was about', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onecrm?screen=deals&type=list')
  await deal(page, 'zzHarbour Point cafe').click()

  const pane = page.locator('[data-slot="object-pane"]')
  await pane.getByRole('tab', { name: /^Activity/ }).click()
  await expect(pane.locator('[data-activity="call"]').first())
    .toBeVisible({ timeout: 25_000 })

  // Both of them, and that is the point of the outcome field: a pair of
  // attempts before a conversation is what tells you somebody is avoiding you.
  await expect(pane.locator('[data-activity="call"]')).toHaveCount(2)
  await expect(pane.getByText('No answer')).toBeVisible()

  // Merged rather than in a tab of its own — the filter exists because the
  // column has calls in it, not because a manifest declared one.
  await pane.getByRole('radio', { name: 'Calls', exact: true }).click()
  await expect(pane.locator('[data-activity="comment"]')).toHaveCount(0)
  await expect(pane.locator('[data-activity="call"]')).toHaveCount(2)

  expectNoRealErrors(errors)
})

test('logging a call opens a dialog already about this deal', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onecrm?screen=deals&type=list')
  await deal(page, 'zzCity depot offices').click()

  const pane = page.locator('[data-slot="object-pane"]')
  await pane.getByRole('button', { name: 'Log a call' }).click()

  // The verb wrote nothing: what arrives is the Calls screen's own New dialog,
  // with the record filled in. Escape leaves the fixture as it was, which is
  // also the proof — a verb that had inserted would leave a row behind.
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible({ timeout: 25_000 })
  await expect(dialog.getByText('About', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')

  expectNoRealErrors(errors)
})

// And the week: the Calls screen opens as a calendar, because "how much of
// Tuesday was on the phone" is the question a list does not answer.
test('the calls screen opens as a week', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onecrm?screen=calls')
  await expect(page.locator('[data-slot="calendar"]'))
    .toBeVisible({ timeout: 25_000 })

  expectNoRealErrors(errors)
})

// `docs/ONECRM.md` stage 6 — answering, measured. The claim the browser can
// check is that the state is a *column*: a rep opening the leads list sees
// which of them nobody has come back to, without opening one.
test('the leads list says which have gone unanswered', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'covered on desktop')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onecrm?screen=leads&type=list')
  await expect(page.getByRole('columnheader', { name: 'Answering' }))
    .toBeVisible({ timeout: 25_000 })
  // The fixture's leads were seeded past their four working hours, so the
  // word on the page is the one the sweep and the save both write.
  await expect(page.getByText('Late').first()).toBeVisible()

  expectNoRealErrors(errors)
})

// And the row a manager argues with, rather than a number in a deployment.
test('the response targets are a table somebody can edit', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a settings page is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onecrm?screen=targets')
  await expect(page.getByText('Answer a lead').first())
    .toBeVisible({ timeout: 25_000 })
  await expect(page.getByText('Come back on a deal').first()).toBeVisible()
  // The narrow one, which is the whole point of a rule list: a lead off the
  // website is answered in an hour and one off a trade show in four, and that
  // is a row above the catch-all rather than a second product.
  await expect(page.getByText('Answer a web lead').first()).toBeVisible()

  expectNoRealErrors(errors)
})

// And what is promised, which is a grid inside the row — priorities with their
// own two clocks. `docs/ONECRM.md` stage 6.
test('a target says what is promised at each priority', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a settings page is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onecrm?screen=targets')
  await page.getByText('Come back on a deal').first().click()

  const pane = page.locator('[data-slot="object-pane"]')
  await expect(pane).toBeVisible({ timeout: 25_000 })
  // Three levels, keyed on the deal's own stage: Negotiation is answered in
  // two working hours and everything else in eight.
  await expect(pane.getByText('Negotiation').first()).toBeVisible()
  await expect(pane.getByText('Proposal').first()).toBeVisible()
  await expect(pane.getByText('Standard').first()).toBeVisible()

  expectNoRealErrors(errors)
})
