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

/**
 * An employee is a person in the org chart and a person with a login, and both
 * of those are Links on the record — `reports_to` and `user_id`.
 *
 * Worth a browser test rather than a unit one, because what could break is not
 * the fields: it is the *path*. `user_id` points at `User`, which is on
 * `registry.NEVER_GRANTED` — no space may ever grant it — so a picker that
 * asked the space's own grants would offer nothing and linking somebody to
 * their login would be impossible from inside the product. And the save has to
 * go through the real document, or HRMS's own rules never run.
 */
test('an employee can be given a manager and a login, and HRMS still has its say',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a form')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/onehr?screen=people&type=list')
    const rows = page.locator('[data-slot="list-row"]')
    await rows.first().waitFor({ timeout: 25_000 })
    await rows.filter({ hasText: 'zzRania Sabbagh' }).first().click()
    await page.locator('[data-slot="person-record"]').waitFor({ timeout: 15_000 })

    // The band says who somebody answers to, off the same field the form edits.
    const line = page.locator('[data-slot="person-manager"]')
    await expect(line).toContainText('zzNoor Haddad')

    // frappe-ui's Combobox is a text input with `role=combobox`; typing asks
    // the server, which is the half worth exercising — the picker for a Link
    // goes through `link_options`, not through a list the SPA made up.
    // An option reads as three lines — a face, the name, the id — so it is
    // matched by text rather than by an exact accessible name, and `Create
    // "…"` is filtered out because it carries the same words.
    const pick = async (label, who) => {
      await page.getByLabel(label, { exact: true }).fill(who)
      await page
        .getByRole('option')
        .filter({ hasText: who })
        .filter({ hasNotText: 'Create' })
        .first()
        .click()
    }

    // Reassigned through the picker, and the line above follows — which is the
    // point of the field being on the page rather than in the desk.
    await pick('Reports to', 'zzSami Rahal')
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0)
    await expect(line).toContainText('zzSami Rahal')

    // And the login. Offered even though `User` is a doctype no space grants:
    // the picker asks Frappe whether this reader may read the target, which is
    // a different question from whether the *space* was given it.
    await page.getByLabel('User ID', { exact: true }).fill('robin')
    await expect(page.getByRole('option', { name: /Robin/ }).first()).toBeVisible()
    await page.keyboard.press('Escape')

    // Put the fixture back, so the tree and the person page start where they
    // started — every other spec here shares these eight people.
    await pick('Reports to', 'zzNoor Haddad')
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0)
    await expect(line).toContainText('zzNoor Haddad')

    expectNoRealErrors(errors)
  })

/**
 * The tables a space is maintained by, on one page.
 *
 * Sixteen of OneHR's screens are `hide_in_nav` — leave types, grades, claim
 * types, the six that had no screen at all until this page existed — and what
 * replaces them in the rail is one entry. Worth a browser test because the
 * failure mode is quiet in both directions: a tab whose name is not a screen of
 * this space is dropped rather than drawn, and a screen declaration that loses
 * its `component` on the way to the tenant renders as "this screen has nothing
 * to show yet", which is what the dev fixture did for as long as it took to
 * look at it.
 */
test('the tables a space is maintained by are one page, not sixteen rail entries',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/onehr?screen=configuration')

    // Every one of the twelve, in the manifest's order rather than the
    // alphabet's — a Configuration page groups by what the reader is doing.
    const tabs = page.getByRole('tab')
    await tabs.first().waitFor({ timeout: 25_000 })
    await expect(tabs).toHaveCount(12)
    await expect(tabs.first()).toHaveText(/Departments/)

    // And none of them is in the rail. `Grievance types` is the one to ask
    // about: `Grievances` *is* a rail entry, so an exact match is the test.
    await expect(
      page.getByRole('link', { name: 'Grievance types', exact: true }),
    ).toHaveCount(0)

    // A tab is a screen, so what opens inside it is that screen's own list —
    // its columns, its count, its New button — and not a query this page made
    // up. `Leave Type Name` is a column nothing else here has.
    await page.getByRole('tab', { name: 'Leave types' }).click()
    const table = page.locator('[data-slot="list-row"]')
    await table.first().waitFor({ timeout: 15_000 })
    await expect(page.getByText(/\d+ leave types/)).toBeVisible()
    await expect(page.getByRole('button', { name: /New Leave type/ })).toBeVisible()

    // And a row opens where that screen's records live. The screen is hidden
    // from the rail, not absent, which is the whole reason the manifest hides
    // these rather than dropping them: the route still resolves.
    await table.first().click()
    await expect(page).toHaveURL(/screen=leave-types/)
    await expect(page).toHaveURL(/at=record/)

    expectNoRealErrors(errors)
  })

/**
 * The tab strip is a column where there is room for one.
 *
 * The same rule a record follows — twelve tables do not fit across the top of
 * a page and do fit down the side of one — and the same reason it is asserted:
 * `md:` and not `sm:`, so a phone gets the scrolling row it can actually use.
 */
test('the configuration tabs are a column on a desktop and a row on a phone',
  async ({ page }, info) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/oneproject?screen=configuration')
    await page.getByRole('tab').first().waitFor({ timeout: 25_000 })

    const rail = page.locator('[data-slot="configuration-rail"]')
    await expect(rail).toHaveCount(info.project.name === 'mobile' ? 0 : 1)

    expectNoRealErrors(errors)
  })

/**
 * The employee's own page, which is the first screen in this product written
 * for the person a record is *about* rather than for whoever administers them.
 *
 * Worth a browser test for the reason the rest of this file exists: every way
 * of getting it wrong is quiet. The page finds its reader by `user_id` and by
 * nothing else, so an unlinked fixture renders one sentence and eight missing
 * blocks rather than an error — and `own.may_read` is what lets a person see
 * their own attendance and pay without the doctype grant, which is exactly the
 * sort of rule that fails silently in the safe direction and is never noticed.
 */
test('the employee opens on their own page, with every block on it',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/onehr?screen=home')

    const band = page.locator('[data-slot="me-band"]')
    await band.waitFor({ timeout: 25_000 })
    // The fixture seats `Administrator` on one of its eight people — the one
    // with a manager above, peers beside and three reports below, which is the
    // only arrangement where the team block has all three kinds in it.
    await expect(page.locator('[data-slot="me-name"]')).toHaveText('zzSami Rahal')

    // Attendance and the leave balance, neither of which the Employee seat is
    // granted the doctype for. They are here because they are *this reader's*.
    await expect(page.locator('[data-slot="person-days"] [data-state="present"]').first())
      .toBeVisible()
    await expect(page.locator('[data-slot="person-balance"]')).toContainText('zzAnnual leave')

    // A payslip, which is the block that was impossible before the same rule:
    // pay is a seat of its own here and a person's own slip is not a breach of
    // it. The amount is the workspace's currency, formatted by the one clock.
    await expect(page.locator('[data-slot="me-payslips"]')).toContainText('AED')

    // What is coming up is the named holiday and not the weekly off. A block
    // whose every line says "Friday" is a block people stop reading.
    const upcoming = page.locator('[data-slot="me-upcoming"]')
    await expect(upcoming).toContainText("zzFounders' day")
    await expect(upcoming).not.toContainText('Friday')

    // The four doors a person files at, as one list — and an Expense Claim has
    // no subject of its own, so it says what it is rather than repeating its
    // own status in both columns, which is what it did at first.
    await expect(page.locator('[data-slot="me-requests"]')).toContainText('Expense claim')

    await expect(page.locator('[data-slot="me-goals"]')).toContainText('zzHarbour Point')

    // And the one thing this page is opened to *do*. The form opens here
    // rather than on the Leave screen — somebody who has just read that they
    // have days left is somebody about to ask for one — and it is the Leave
    // screen's own spec behind it, so `can_create` is the server's answer to
    // whether this reader may file one at all.
    await page.locator('[data-slot="me-ask"]').click()
    await expect(page.getByRole('dialog')).toContainText('Leave')
    await page.keyboard.press('Escape')

    // And their people, each with where they are now beside them — the one
    // thing anybody opens an HR product for every morning.
    const team = page.locator('[data-slot="me-team"]')
    await expect(team).toContainText('zzNoor Haddad')
    await expect(team).toContainText('Your manager')
    await expect(team).toContainText('Reports to you')

    expectNoRealErrors(errors)
  })

/**
 * Checking in, which is the one thing in OneHR that writes.
 *
 * The direction is the server's answer rather than the button's, so this reads
 * whichever way it points and asserts it turned round — which also makes the
 * spec re-runnable, because a fixture that was checked in by the last run is
 * offered a check *out* by this one.
 */
test('a person can check themselves in, and the control turns round',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a button')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/onehr?screen=home')
    const control = page.locator('[data-slot="me-checkin"]')
    await control.waitFor({ timeout: 25_000 })

    const before = (await control.textContent())?.trim()
    expect(['Check in', 'Check out']).toContain(before)

    await control.click()

    // The presence above it is read *after* the write, so the pill and the
    // button cannot disagree for as long as a second request would take — the
    // window in which somebody presses Check in twice.
    await expect(control).not.toHaveText(before, { timeout: 15_000 })
    await expect(page.locator('[data-slot="me-presence"]')).toContainText(
      before === 'Check in' ? 'In' : 'Checked out',
    )

    expectNoRealErrors(errors)
  })

/**
 * A screen that has two readers says so, and the narrowing is real.
 *
 * `My leave` is the Leave screen with one filter naming the reader —
 * `oneapp/onespace/mine.py` — and the thing worth asserting in a browser is
 * that the two screens disagree about how many rows there are. A filter that
 * silently did nothing would render as a working screen under a label saying
 * it is yours, which is the one failure here nobody notices.
 */
test('a screen narrowed to its reader shows fewer rows than its parent',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)

    const counted = async (screen) => {
      await page.goto(`/one/space/onehr?screen=${screen}&type=list`)
      const rows = page.locator('[data-slot="list-row"]')
      await rows.first().waitFor({ timeout: 25_000 })
      return rows.count()
    }

    // The fixture seats `Administrator` on zzSami Rahal, who has one of the
    // seven applications on this site.
    const mine = await counted('my-leave')
    const all = await counted('leave')
    expect(mine).toBeGreaterThan(0)
    expect(mine).toBeLessThan(all)

    // Where the twin *sits* — above its parent, under the parent's own
    // heading — is decided in the manifest and read back there, by
    // `test_space_screens.test_a_twin_is_declared_above_the_screen_it_narrows`.
    // A phone's rail is four entries and a More, so a browser could only ever
    // check it on one viewport.

    expectNoRealErrors(errors)
  })

/**
 * And the same mechanism in a space that has never heard of an Employee.
 *
 * `@me` with no kind after it is the session's user, which needs no app to
 * register anything — which is the point: a screen narrowed to its reader is
 * not an HR feature, and if it only ever worked in OneHR it would belong in
 * OneHR.
 */
test('the same narrowing works off the session user, with no app to ask',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a count')
    const errors = collectConsoleErrors(page)

    const counted = async (screen) => {
      await page.goto(`/one/space/onecrm?screen=${screen}&type=list`)
      const rows = page.locator('[data-slot="list-row"]')
      await rows.first().waitFor({ timeout: 25_000 })
      return rows.count()
    }

    // Every third deal in the fixture belongs to the colleague, so the two
    // screens cannot agree unless the filter was dropped.
    const mine = await counted('my-deals')
    const all = await counted('deals')
    expect(mine).toBeGreaterThan(0)
    expect(mine).toBeLessThan(all)

    expectNoRealErrors(errors)
  })
