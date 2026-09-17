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
