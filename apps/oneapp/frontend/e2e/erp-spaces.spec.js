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

/**
 * Where somebody is, now — `oneapp/onehr/presence.py`.
 *
 * Four HRMS doctypes that disagree with each other all day, ranked once. What a
 * browser is for here is that the ranking survives the trip: the fixture puts
 * one of each state on today on purpose, so a run that drew the wrong one for
 * any of them fails on the word rather than on an assertion about a query.
 */
test('a person says where they are, and the four sources are ranked', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  const pill = page.locator('[data-slot="person-presence"]')
  const open = async (name) => {
    await page.goto('/one/space/onehr?screen=people&type=list')
    const rows = page.locator('[data-slot="list-row"]')
    await rows.first().waitFor({ timeout: 25_000 })
    await rows.filter({ hasText: name }).first().click()
    await page.locator('[data-slot="person-record"]').waitFor({ timeout: 15_000 })
  }

  // Arrived after the shift began. `late` is a fact about an `in` rather than a
  // state of its own, and the pill is the only place that distinction shows.
  await open('zzOmar Fadel')
  await expect(pill).toContainText('late')

  // Approved leave over today, and a log would not have changed it.
  await open('zzHala Zayed')
  await expect(pill).toContainText('On leave')

  // Marked absent by the attendance job, with nothing above it to say otherwise.
  await open('zzTarek Jaber')
  await expect(pill).toContainText('Absent')

  // Came and went. The last log by *time* decides, not the newest row.
  await open('zzKarim Nassar')
  await expect(pill).toContainText('Checked out')

  expectNoRealErrors(errors)
})

/**
 * Their last eight weeks, and the leave they have left.
 *
 * On the record rather than on the screen's dashboard — `docs/ONESPACE.md`,
 * "Where the numbers go". A dashboard over one row is a number with nothing to
 * compare it to.
 */
test('a person carries their own numbers, and a weekend is not an absence', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onehr?screen=people&type=list')

  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 25_000 })
  await rows.filter({ hasText: 'zzTarek Jaber' }).first().click()

  const band = page.locator('[data-slot="person-year"]')
  await band.waitFor({ timeout: 15_000 })

  // Eight weeks of days, built from the calendar rather than from the rows: a
  // strip of only the days Attendance knows about has holes that line up with
  // nothing, and the point of a strip is that the seventh cell is a weekday.
  const days = band.locator('[data-slot="person-days"] [data-state]')
  await expect(days.first()).toBeVisible()
  expect(await days.count()).toBeGreaterThan(50)

  // The fixture's holiday list calls Friday a weekly off, so there are five of
  // them in the window — and none of them is drawn as an absence, which is the
  // distinction the whole strip stands on.
  await expect(band.locator('[data-state="holiday"]').first()).toBeVisible()
  await expect(band.locator('[data-state="absent"]').first()).toBeVisible()

  // And what is left, per type, from the allocation minus what was approved.
  await expect(band.locator('[data-slot="person-balance"]')).toContainText('zzAnnual leave')

  expectNoRealErrors(errors)
})

/**
 * Fifteen tabs was never too many destinations. It was too many for a row.
 *
 * An Employee is pointed at by ten screens in this space and every one of them
 * is a place worth going, so the answer is an axis with room for them: a column
 * beside the content on a desktop page, where the doctype's own tabs inside
 * Details then read as a level down instead of as a second strip competing with
 * the first. A pane is 480 pixels and a phone is narrower, and both keep the
 * row — and the row keeps the overflow, because a row is the thing that runs
 * out of room.
 */
test('the tabs are a column where there is room for one', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onehr?screen=people&type=list')

  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 25_000 })
  await rows.first().click()
  await page.locator('[data-slot="person-record"]').waitFor({ timeout: 15_000 })

  const rail = page.locator('[data-slot="record-tabs-rail"]')
  const more = page.locator('[data-slot="record-more-tabs"]')

  if (info.project.name === 'mobile') {
    // No room for a 12rem rail, so the row — and the four a manifest declared
    // stay while the rest go behind one control, because burying a declared tab
    // to make room for a derived one is the derivation overruling the manifest.
    await expect(rail).toHaveCount(0)
    await expect(more).toContainText('more')
    await expect(page.getByRole('tab', { name: 'Leave', exact: true })).toBeVisible()
    expectNoRealErrors(errors)
    return
  }

  await expect(rail).toBeVisible()
  // All of them, declared and derived alike, and no menu — there is nothing
  // left for one to hold.
  for (const one of ['Leave', 'Attendance', 'Claims', 'Goals', 'Grievances', 'Check-ins']) {
    await expect(page.getByRole('tab', { name: one, exact: true })).toBeVisible()
  }
  await expect(more).toHaveCount(0)

  // And a derived one opens, which is the whole reason it is a tab and not a
  // menu entry that resolves to nothing.
  await page.getByRole('tab', { name: 'Grievances', exact: true }).click()
  await expect(page.getByRole('tab', { name: 'Grievances', exact: true }))
    .toHaveAttribute('aria-selected', 'true')

  expectNoRealErrors(errors)
})

/**
 * The face is the subject of the page, and it can be changed from there.
 *
 * `Avatar` tops out at 46 pixels because an avatar is an identity marker in a
 * row. A portrait is not that, and the control for it belongs *on* the face
 * rather than three screens away in the Meta tab — which is where it was, and
 * which is where you go when you did not find it here.
 */
test('the portrait is the size of a face, and offers what can be done to it', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onehr?screen=people&type=list')

  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 25_000 })
  await rows.first().click()

  const portrait = page.locator('[data-slot="person-portrait"]')
  await portrait.waitFor({ timeout: 15_000 })
  const box = await portrait.boundingBox()
  expect(box.width).toBeGreaterThan(80)

  // Nothing filed yet, so the offer is to add rather than to replace, and there
  // is nothing to remove.
  await portrait.locator('[data-slot="person-portrait-edit"]').click()
  await expect(page.getByRole('menuitem', { name: 'Add a photograph' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Remove it' })).toHaveCount(0)

  // And it opens the picker every attach surface uses, so a photograph can come
  // off the workspace's own files as easily as off a device.
  await page.getByRole('menuitem', { name: 'Add a photograph' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()

  expectNoRealErrors(errors)
})

/**
 * Four facts, drawn as four facts.
 *
 * A row of label-over-value floating in space reads as a table that lost its
 * rules. The dividers are what make them facts; the glyph is the derivation the
 * form uses for the same field, so a date looks like a date in both places.
 */
test('a fact carries its glyph, and an empty one is quieter than an answer', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onehr?screen=people&type=list')

  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 25_000 })
  await rows.filter({ hasText: 'zzOmar Fadel' }).first().click()

  const facts = page.locator('[data-slot="person-facts"]')
  await facts.waitFor({ timeout: 15_000 })

  // Three, not four: the manifest lists `reports_to` among its facts and the
  // line under the name already says it, and the row follows the count rather
  // than leaving an empty cell with a rule down one side.
  const cells = facts.locator('> div')
  await expect(cells).toHaveCount(3)
  await expect(cells.first().locator('svg, [class*="lucide"]').first()).toBeVisible()
  await expect(facts).toContainText('Department')

  expectNoRealErrors(errors)
})
