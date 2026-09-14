// The three spaces over ERPNext, and the five things that were silently wrong.
//
// Every screen in OneProject, OneCRM and OneHR is a declaration in
// `apps/oneapp_control/oneapp_control/spaces/` over a doctype somebody else
// ships, and `scripts/check_screens.py` already opens all sixty-four of them
// server-side. What it cannot see is what they *look like*, and every one of
// the bugs below rendered as a screen that was merely thinner than intended:
//
//   * a board with no columns, because its column field sat above permission
//     level zero and our DocPerms only ever spoke about level zero;
//   * a five-day absence drawn as one chip on the Monday, because frappe-ui's
//     Calendar places an event by its start and nothing else;
//   * a pipeline in alphabetical order, because a Link has no order of its own;
//   * a four-star candidate drawn with one star, because Frappe stores a Rating
//     as a fraction and the component counts stars;
//   * a hero saying HR-EMP-00002 where the list beside it said the person.
//
// None of them threw. That is why this file exists.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * Whether this site carries the apps these spaces are over.
 *
 * The fixture says "skipped, no ERPNext" and carries on, so a bench without it
 * is a normal thing to run the suite against rather than a broken one — and a
 * spec that failed there would be a spec everybody learns to ignore.
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

test('a leave board has the columns its status field makes', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onehr?screen=leave&type=board')

  // `Leave Application.status` is at permission level 1 in HRMS. Our DocPerms
  // used to speak only about level zero, and Frappe reads a doctype's own
  // permissions *only while it has no custom ones* — so the field was
  // unreadable, `_offerable` dropped it, `_view_types` dropped the board, and
  // the screen opened as a list with no explanation anywhere.
  const columns = page.locator('[data-oneapp-column]')
  await columns.first().waitFor({ timeout: 25_000 })
  await expect(page.locator('[data-oneapp-column="Open"]')).toBeVisible()
  await expect(page.locator('[data-oneapp-column="Approved"]')).toBeVisible()
  await expect(page.locator('[data-oneapp-column="Rejected"]')).toBeVisible()

  expectNoRealErrors(errors)
})

test('an absence covers every day it covers', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onehr?screen=leave&type=calendar')

  const grid = page.locator('[data-slot="calendar"]')
  await grid.waitFor({ timeout: 25_000 })

  // The fixture's five-day absence. frappe-ui's Calendar reads `fromDate` and
  // groups the month by it, so a span used to be one chip on its first day —
  // which on a leave screen is the month being wrong about who is in.
  await expect(grid.getByText('zzOmar Fadel')).toHaveCount(5)

  expectNoRealErrors(errors)
})

test('a pipeline is in pipeline order', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onecrm?screen=deals&type=board')

  const columns = page.locator('[data-oneapp-column]')
  await columns.first().waitFor({ timeout: 25_000 })

  // A Select carries its own order and `Sales Stage` is a Link, which has
  // none: the board came out Negotiation, Prospecting, Proposal. The order is
  // a decision, so `onecrm.STAGES` declares it and `board.arrangement` carries
  // it — see `onespace/board.py`.
  const shown = await columns.evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute('data-oneapp-column')),
  )
  expect(shown.indexOf('Prospecting')).toBeLessThan(shown.indexOf('Qualification'))
  expect(shown.indexOf('Qualification')).toBeLessThan(shown.indexOf('Needs Analysis'))
  expect(shown.indexOf('Needs Analysis')).toBeLessThan(shown.indexOf('Negotiation/Review'))

  expectNoRealErrors(errors)
})

test('a rating is the stars it is worth', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onehr?screen=applicants&type=list')

  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 25_000 })

  // Frappe stores a Rating as a fraction of one; frappe-ui's Rating counts
  // whole stars. Unconverted, the fixture's 0.8 drew a single star — and
  // clicking the fourth star wrote four hundred per cent.
  const row = rows.filter({ hasText: 'zzDana Khoury' }).first()
  // frappe-ui marks a filled star `data-state="filled"`. The fixture rates her
  // 0.8, which is four of five.
  await expect(row.locator('[data-slot="star"][data-state="filled"]')).toHaveCount(4)

  expectNoRealErrors(errors)
})

test('a person opens as a person rather than as a form', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onehr?screen=people&type=list')

  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 25_000 })
  await rows.filter({ hasText: 'zzKarim Nassar' }).first().click()

  // Not the showcase a project gets. `view_settings.record.as` names one out of
  // the engine's library — `lib/screen/recordViews.js` — and a person's is a
  // portrait, a job title and the line they report along rather than a
  // photograph the size of the screen with numbers laid over it.
  const page_ = page.locator('[data-slot="person-record"]')
  await page_.waitFor({ timeout: 15_000 })
  await expect(page.locator('[data-slot="showcase"]')).toHaveCount(0)
  await expect(page_.locator('[data-slot="person-eyebrow"]')).toHaveText(/Engineer/i)

  // Who they answer to, as a relationship rather than as one of the facts —
  // and by name. `_links` holds `{value, label}`, and reading the object itself
  // put "Reports to [object Object]" under somebody's name.
  await expect(page_.locator('[data-slot="person-manager"]')).toContainText('zzSami Rahal')
  // And not twice: the manifest lists `reports_to` among its four facts,
  // because over on a showcase a manager is just another number on a card.
  await expect(page_.locator('[data-slot="person-facts"]')).not.toContainText('zzSami Rahal')

  // And the tabs are the screens that point back at a person. `exact`,
  // because the doctype's own form has a tab called "Attendance & Leaves" and
  // these are the showcase's, which are screens in this space.
  await expect(page.getByRole('tab', { name: 'Leave', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Attendance', exact: true })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Claims', exact: true })).toBeVisible()

  expectNoRealErrors(errors)
})
