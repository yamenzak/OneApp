// A record drawn as a place rather than as a form.
//
// The declaration is `view_settings.showcase` in the manifest and the RUA space
// is the only one that carries it today — so this runs where that space is
// seeded and skips where it is not, the same way `rua.spec.js` does.
//
// What is being checked is not construction. It is that a screen saying "a
// record here is a place" gets: the photograph, the numbers, the things hanging
// off it, the other screens that point back at it, and the whole width to draw
// them in.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

async function openFirstProject(page) {
  await page.goto('/one/space/rua?screen=projects')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')

  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="showcase"]').waitFor({ timeout: 25_000 })
}

test('a project opens as a page, not as a pane beside the list', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'every record is a page on a phone')
  const errors = collectConsoleErrors(page)

  await openFirstProject(page)

  // The hero says who this is, at the size a photograph can carry.
  await expect(page.locator('[data-slot="showcase-title"]')).toBeVisible()

  // And the list is not beside it: a hero in a 480-pixel column is a
  // thumbnail. The rows are still mounted — closing comes back to them — so
  // this asks whether they are on screen, not whether they exist.
  await expect(page.locator('[data-slot="list-row"]').first()).toBeHidden()

  // The whole content area, which on this viewport is most of the window.
  const pane = await page.locator('[data-slot="record-pane"]').boundingBox()
  expect(pane.width).toBeGreaterThan(800)

  expectNoRealErrors(errors)
})

test('the numbers worth reading are in the hero, formatted as the list formats them', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for a fact row')
  const errors = collectConsoleErrors(page)

  await openFirstProject(page)

  const facts = page.locator('[data-slot="showcase-fact"]')
  await expect(facts.first()).toBeVisible()

  // Grouped thousands and two decimals, because the contract value is a
  // Currency and this is the same formatter the column it came from uses. A
  // hero that renders `1115646.0` beside a list that renders `1,115,646.00` is
  // two numbers as far as anybody reading is concerned.
  const said = (await facts.allInnerTexts()).join(' ')
  expect(said).toMatch(/\d{1,3}(,\d{3})+\.\d{2}|—/)

  // And a percentage reads to the places it was stored to, not to the site's
  // float precision: `0%`, never `0.000%`.
  expect(said).not.toMatch(/\.\d{3}%/)

  expectNoRealErrors(errors)
})

test('the screens that point back at a project are tabs on it', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the strip scrolls on a phone')
  const errors = collectConsoleErrors(page)

  await openFirstProject(page)

  // The record's own strip, which is the first one on the page: the form
  // under it draws the *doctype's* tabs, and Project's first one is also
  // called Details.
  const strip = page.locator('[data-slot="tab-list"]').first()

  // Declared in the manifest, in the customer's own words — LPOs, not Purchase
  // Orders — beside the record's own four.
  for (const label of ['Details', 'Quotations', 'LPOs', 'Invoices', 'Payments', 'Activity']) {
    await expect(strip.getByRole('tab', { name: label })).toBeVisible()
  }

  // And one of them opens onto that screen's own rows, or says there are none
  // in the words of the thing that is missing.
  await strip.getByRole('tab', { name: 'Payments' }).click()
  // Scoped to the pane: the list behind it is hidden, not unmounted, and its
  // rows still answer a bare `list-row` selector.
  const inside = page.locator('[data-slot="record-pane"] [data-slot="list-row"]').first()
  await expect(
    inside.or(page.getByText('No payments against this yet.')),
  ).toBeVisible({ timeout: 25_000 })

  expectNoRealErrors(errors)
})

test('a variation opens from the strip under the photograph', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for a card row')
  // Longer than the suite's default, because finding a job with variations
  // under it means opening a few that have none. See the scan below.
  test.setTimeout(120_000)
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/rua?screen=projects')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  // Thirteen of their eighty-two jobs have variations under them, and the list
  // is in `modified` order — which puts the *children* first, because the pass
  // that linked each variation to its parent touched the child. So this scans
  // from the far end, where the jobs nobody has touched since the first import
  // are, and stops at the first one with cards under its photograph.
  //
  // Opened and closed rather than reloaded per candidate: on a showcase screen
  // the open record takes the page, so there is no row to click while one is
  // open — and twenty full page loads against a single-threaded dev server is
  // a test that times out for a reason that has nothing to do with the card.
  const rows = page.locator('[data-slot="list-row"]')
  const last = await rows.count()
  let found = null
  for (let at = last - 1; at >= Math.max(0, last - 20) && !found; at -= 1) {
    await rows.nth(at).scrollIntoViewIfNeeded()
    await rows.nth(at).click()
    await page.locator('[data-slot="showcase"]').waitFor({ timeout: 25_000 })
    const cards = page.locator('[data-slot="showcase-child"]')
    await cards.first().waitFor({ timeout: 4_000 }).catch(() => {})
    if (await cards.count()) found = cards.first()
    else await page.getByRole('button', { name: 'Close the record' }).click()
  }
  test.skip(!found, 'none of the last twenty jobs on this list has a variation under it')

  const was = new URL(page.url()).searchParams.get('record')
  await found.click()
  await expect
    .poll(() => new URL(page.url()).searchParams.get('record'), { timeout: 15_000 })
    .not.toBe(was)

  // The variation is a project too, so it is drawn the same way.
  await expect(page.locator('[data-slot="showcase-title"]')).toBeVisible()

  expectNoRealErrors(errors)
})
