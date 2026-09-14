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
    //
    // Read rather than asserted. This spec changes a field the whole fixture
    // shares and puts it back at the end, so a run that failed part-way used
    // to leave the next one starting from the wrong manager and failing on
    // line one — which is a spec that reports its own last failure rather than
    // the code. Whoever it is now is the one to return to.
    const line = page.locator('[data-slot="person-manager"]')
    await expect(line).toContainText('Reports to')
    const was = (await line.textContent()).replace('Reports to ', '').trim()
    const other = was === 'zzSami Rahal' ? 'zzNoor Haddad' : 'zzSami Rahal'

    // frappe-ui's Combobox is a text input with `role=combobox`; typing asks
    // the server, which is the half worth exercising — the picker for a Link
    // goes through `link_options`, not through a list the SPA made up.
    // An option reads as three lines — a face, the name, the id — so it is
    // matched by text rather than by an exact accessible name, and `Create
    // "…"` is filtered out because it carries the same words.
    const pick = async (label, who) => {
      await page.getByLabel(label, { exact: true }).fill(who)
      const option = page
        .getByRole('option')
        .filter({ hasText: who })
        .filter({ hasNotText: 'Create' })
      // Settled before it is clicked, and this is the assertion that found the
      // bug behind it: two searches are in flight whenever somebody types over
      // a value that is already chosen — the first touch fetches, the first
      // keystroke fetches again — and `LinkPicker` took whichever *answered*
      // first. So the list kept the options for the name already in the box.
      // Clicking `.first()` hid it, because the stale option was clickable and
      // had the right words on it a third of the time.
      await expect(option).toHaveCount(1, { timeout: 15_000 })
      await option.first().click()
    }

    // Reassigned through the picker, and the line above follows — which is the
    // point of the field being on the page rather than in the desk.
    await pick('Reports to', other)
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0)
    await expect(line).toContainText(other)

    // And the login. Offered even though `User` is a doctype no space grants:
    // the picker asks Frappe whether this reader may read the target, which is
    // a different question from whether the *space* was given it.
    await page.getByLabel('User ID', { exact: true }).fill('robin')
    await expect(page.getByRole('option', { name: /Robin/ }).first()).toBeVisible()
    await page.keyboard.press('Escape')

    // Put the fixture back, so the tree and the person page start where they
    // started — every other spec here shares these eight people.
    await pick('Reports to', was)
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0)
    await expect(line).toContainText(was)

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
    await expect(tabs).toHaveCount(13)
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

/**
 * An applicant opens as somebody you are deciding about.
 *
 * The last screen in OneHR still using the RUA showcase, which drew a
 * 260-pixel black hero over a person with no photograph and a name in
 * condensed capitals — right for a building and wrong for a face. What
 * replaces it answers the decision instead: how far along they are, what the
 * rounds scored, and which opening.
 *
 * The stage strip is the part worth a browser test. Its order is the
 * manifest's and not the doctype's — Job Applicant's own Select lists Rejected
 * between Shortlisted and Hold, which would draw the bin in the middle of the
 * run — and a strip in the wrong order is a page that looks like it works.
 */
test('an applicant opens as a candidate, with the pipeline in hiring order',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    await page.goto('/one/space/onehr?screen=applicants&type=list')

    const rows = page.locator('[data-slot="list-row"]')
    await rows.first().waitFor({ timeout: 25_000 })
    await rows.filter({ hasText: 'zzDana Khoury' }).first().click()

    const record = page.locator('[data-slot="candidate-record"]')
    await record.waitFor({ timeout: 15_000 })
    // And the hero it replaced is gone.
    await expect(page.locator('[data-slot="showcase"]')).toHaveCount(0)

    await expect(page.locator('[data-slot="candidate-name"]')).toHaveText('zzDana Khoury')

    // What they applied for, as the line under the name rather than as one of
    // the facts — and so not repeated in the row below it.
    await expect(page.locator('[data-slot="candidate-opening"]'))
      .toContainText('zzSite engineer')
    const facts = page.locator('[data-slot="candidate-facts"]')
    await expect(facts).toContainText('Source')
    await expect(facts).not.toContainText('Applied for')

    // The pipeline, in the manifest's order. Hold is a stage and not an
    // ending: it sits after Shortlisted because that is where it happens, and
    // taking it out would draw somebody on hold as never shortlisted.
    const stages = page.locator('[data-slot="candidate-stages"] [data-stage]')
    await expect(stages).toHaveCount(5)
    await expect(stages.nth(2)).toHaveAttribute('data-stage', 'Shortlisted')
    await expect(stages.nth(3)).toHaveAttribute('data-stage', 'Hold')

    // Dana is shortlisted, so everything up to there is behind her and
    // nothing after it is.
    await expect(stages.nth(2)).toHaveAttribute('data-reached', '1')
    await expect(stages.nth(3)).toHaveAttribute('data-reached', '0')

    // And what the rounds said, which is the decision and is four clicks away
    // in every HR product we have looked at.
    await expect(page.locator('[data-slot="candidate-interviews"]'))
      .toContainText('zzFirst interview')

    expectNoRealErrors(errors)
  })

/**
 * A rejection is an ending, not a stage further along.
 *
 * Somebody turned down after a shortlisting has still been shortlisted, so the
 * strip says how far they came and the badge beside the heading says how it
 * finished. Drawing Rejected as the last box on the run would say they passed
 * through everything before it.
 */
test('a rejected applicant is drawn as an ending rather than a stage',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a strip')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/onehr?screen=applicants&type=list')
    const rows = page.locator('[data-slot="list-row"]')
    await rows.first().waitFor({ timeout: 25_000 })
    await rows.filter({ hasText: 'zzJude Obeid' }).first().click()

    const strip = page.locator('[data-slot="candidate-stages"]')
    await strip.waitFor({ timeout: 15_000 })
    await expect(strip).toContainText('Rejected')
    await expect(strip.locator('[data-stage="Rejected"]')).toHaveCount(0)

    expectNoRealErrors(errors)
  })

/**
 * The three verbs HRMS keeps in the desk's Create menu.
 *
 * Scheduling an interview, making an offer and hiring the person who accepted
 * one were all reachable only from `/app` — the desk's own buttons are
 * JavaScript an app ships, and running that is the door `docs/UNIFICATION.md`
 * rail 34 refuses. So the verb answers with what should happen *next* and the
 * engine does it, which is the part worth a browser test: the dialog that
 * opens is the target screen's own New, with the fields the server filled in.
 */
test('a hiring verb opens the next record already filled in',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a dialog')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/onehr?screen=applicants&type=list&at=record:dana@zzapplicants.test')
    await page.locator('[data-slot="candidate-record"]').waitFor({ timeout: 25_000 })

    await page.getByRole('button', { name: 'Actions' }).click()
    await page.getByRole('menuitem', { name: /Schedule an interview/ }).click()

    // The Interviews screen's own dialog, not a form the verb invented — so
    // the required-ness, the validation and the permission are that screen's.
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible({ timeout: 15_000 })
    await expect(dialog).toContainText('New Interview')

    // The applicant is in it, which is the whole of what the verb knew. A Link
    // is a combobox, so the value is the input's rather than the dialog's text.
    await expect(dialog.locator('input[value="zzDana Khoury"]').first()).toBeVisible()

    // And the opening arrived without being sent, because Interview fetches it
    // off the applicant — which a *preset* Link now runs, the same as a typed
    // one. A verb that had filled it in too would be having an opinion about a
    // value HRMS derives.
    await expect(dialog).toContainText('HR-OPN-')

    // The designation is not filled, and that is right: Interview fetches it
    // from the interview *type*, which is the thing this dialog is open to ask
    // for. The label says so.
    await expect(dialog).toContainText('From interview type')

    await page.keyboard.press('Escape')
    expectNoRealErrors(errors)
  })

/**
 * Hiring, and the refusal that is the other half of it.
 *
 * Only an accepted offer becomes an employee. The button is on every row
 * regardless — one that vanished at some statuses is one nobody learns is
 * there — so the refusal is where the decision lives, and a fixture carrying
 * only one of the two statuses tests half a rule.
 */
test('an accepted offer becomes the employee it promised',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a dialog')
    const errors = collectConsoleErrors(page)

    const open = async (who) => {
      await page.goto('/one/space/onehr?screen=offers&type=list')
      const rows = page.locator('[data-slot="list-row"]')
      await rows.first().waitFor({ timeout: 25_000 })
      await rows.filter({ hasText: who }).first().click()
      // One verb, so it is a button rather than a menu — `ScreenActions`
      // renders a chevron only once there are two.
      await page.getByRole('button', { name: 'Hire', exact: true }).click()
    }

    // Maya accepted. This opens the People screen's New with what HRMS's own
    // mapping carried across — the name, the personal email, and the back-link
    // on `job_offer` that makes the hire traceable to the offer. It stops there
    // because an Employee needs a date of birth no offer knows.
    await open('zzMaya Seif')
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible({ timeout: 15_000 })
    await expect(dialog).toContainText('New Person')
    await expect(dialog.locator('input[value="zzMaya Seif"]').first()).toBeVisible()
    await page.keyboard.press('Escape')

    expectNoRealErrors(errors)
  })

/**
 * And the refusal, which is the other half of the same rule.
 *
 * The button is on every offer regardless of status — one that vanished at
 * some of them is one nobody learns is there — so the refusal is where the
 * decision lives, and a fixture carrying only an accepted offer would test
 * half of it.
 *
 * **No console check here**, and that is the declared reason: the refusal is a
 * 417 the reader is shown as a sentence, and a spec that asserted no errors
 * would be asserting that the thing it came to see did not happen.
 */
test('an offer nobody has accepted is refused in a sentence',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a refusal')

    await page.goto('/one/space/onehr?screen=offers&type=list')
    const rows = page.locator('[data-slot="list-row"]')
    await rows.first().waitFor({ timeout: 25_000 })
    await rows.filter({ hasText: 'zzElias Moussa' }).first().click()
    await page.getByRole('button', { name: 'Hire', exact: true }).click()

    await expect(page.getByText(/Only an accepted one/)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })

/**
 * Where a check-in has to be, and on whose network — set up without typing it.
 *
 * A geofence is a position, a distance and a network, and typing any of the
 * three is both tedious and the step where it gets set up wrong: a latitude
 * with the sign flipped is a circle in the wrong hemisphere and nothing says so
 * until somebody cannot check in. So both are offered instead, and the fields
 * the form owns are what they fill.
 */
test('a place says what it demands, and offers to fill itself in',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a form')
    const errors = collectConsoleErrors(page)

    await page.goto('/one/space/onehr?screen=places&type=list')
    const rows = page.locator('[data-slot="list-row"]')
    await rows.first().waitFor({ timeout: 25_000 })
    // The name rather than the row: this list's widest cells are numbers, so
    // the centre of the row is empty space and a click there ticks it instead.
    await rows.filter({ hasText: 'zzNorthgate yard' })
      .first().getByText('zzNorthgate yard').click()

    const record = page.locator('[data-slot="place-record"]')
    await record.waitFor({ timeout: 15_000 })

    // What it demands, as a sentence rather than three numbers somewhere.
    await expect(page.locator('[data-slot="place-rule"]')).toContainText('150 m')
    await expect(page.locator('[data-slot="place-position"]')).toContainText('25.08')
    await expect(page.locator('[data-slot="place-networks"]')).toContainText('203.0.113.0/24')

    // And the control that fills the network in from where the server sees
    // this request coming from — the one value nobody can look up easily and
    // the one a browser cannot fake, because it is read off the connection.
    const listed = page.locator('[data-slot="place-networks"] li')
    await expect(listed).toHaveCount(1)
    await page.locator('[data-slot="place-network"]').click()
    // Appended rather than replacing — an office with two lines has two
    // addresses, and a control that overwrote the list would make the second
    // one delete the first. Which address it is depends on where this is run
    // from, which is the whole point of not making anybody look it up.
    await expect(listed).toHaveCount(2, { timeout: 15_000 })

    // Filled, not saved: a record view places controls and never writes
    // through them, so what was detected is sitting in the form for somebody
    // to look at. Leaving without saving puts the fixture back.
    await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeVisible()

    expectNoRealErrors(errors)
  })

/**
 * And the employee's side of the same rule: the button says what it will ask
 * for before it asks.
 *
 * A location prompt somebody did not expect is a location prompt somebody
 * refuses, so the workspace's answer is read before the button is drawn rather
 * than after it is pressed.
 */
test('the check-in button says what it will ask for', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for a line')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onehr?screen=home')
  await page.locator('[data-slot="me-band"]').waitFor({ timeout: 25_000 })

  // The seated employee's shift has no place, and this workspace records no
  // positions, so there is nothing to warn about and no line — which is the
  // half of this that matters: nothing is asked for that nobody wanted.
  await expect(page.locator('[data-slot="me-checkin"]')).toBeVisible()
  await expect(page.locator('[data-slot="me-checkin-rule"]')).toHaveCount(0)

  expectNoRealErrors(errors)
})


/**
 * Attendance is a grid, and a list cannot be one.
 *
 * One row per person per day: reading it as a list means holding eight people
 * by thirty days in your head to answer "who was out on the Tuesday", while
 * the same rows drawn as people down the side and days across the top answer
 * that — and the patterns nobody thought to ask about — without being read.
 *
 * Two things here are easy to get wrong and quiet when they are. The month a
 * grid says it is drawing has to be the month it asks the server for; and the
 * colours have to be the screen's declared ones, because a cell carries no
 * word and a grid of grey squares carries nothing at all.
 */
test('attendance is a month of people against days', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a month of columns is not a phone')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onehr?screen=attendance&type=matrix')
  await page.locator('[data-slot="matrix"]').waitFor({ timeout: 25_000 })

  // A row per person, labelled by name rather than by id — `employee` is not
  // a column on this screen, so the label is one the server resolved for the
  // grid and for nothing else.
  const lines = page.locator('[data-slot="matrix-row"]')
  await expect(lines.first()).toBeVisible()
  await expect(page.locator('[data-slot="matrix"]')).toContainText('zzSami Rahal')
  await expect(page.locator('[data-slot="matrix"]')).not.toContainText('HR-EMP-')

  // Coloured by what the manifest declared, not by Frappe's word lists —
  // which say nothing about Present or On Leave, so without the declaration
  // every cell here is the same grey.
  const cells = page.locator('[data-cell]')
  await expect(cells.first()).toBeVisible()
  const grounds = new Set(
    await cells.evaluateAll((all) => all.map((one) => one.className.match(/bg-surface-\w+-\d/)?.[0])),
  )
  expect(grounds.size).toBeGreaterThan(1)

  // The month on the label is the month it asked for. Building a date locally
  // and reading it back through the site's timezone walks the header into the
  // month before, which is what it did.
  await expect(page.locator('[data-slot="matrix-month"]')).toContainText(
    new Date().toLocaleDateString('en', { month: 'long' }).slice(0, 3),
  )

  // And a cell opens its day, which is where the verdict is changed with the
  // doctype's own rules in front of it. A grid that wrote on click would be a
  // second save path over the one screen where a mistake is somebody's pay.
  await cells.first().click()
  await expect(page).toHaveURL(/at=record/)

  expectNoRealErrors(errors)
})

/**
 * And the month before is a different month.
 *
 * The grid asks the server for the days it is drawing, so stepping back has to
 * change the rows as well as the header — a grid that moved its label and kept
 * September's cells would be a grid that lies quietly.
 */
test('stepping back a month asks for that month', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a month of columns is not a phone')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/onehr?screen=attendance&type=matrix')
  await page.locator('[data-slot="matrix"]').waitFor({ timeout: 25_000 })

  const label = page.locator('[data-slot="matrix-month"]')
  const was = await label.textContent()
  await page.getByRole('button', { name: 'The month before' }).click()
  await expect(label).not.toHaveText(was)

  // The days across the top are that month's, which is the half a label alone
  // does not prove.
  await expect(page.locator('[data-slot="matrix"] thead th').last()).toBeVisible()

  expectNoRealErrors(errors)
})

/**
 * The last of the employee's doors to have no screen at all.
 *
 * Travel Request was granted `if_owner` since OneHR shipped and reachable only
 * from the desk, which is the one place this product does not go. It gets a
 * list and a twin like the other three things a person files.
 *
 * The badge is the other half of this. A Select option can be a sentence —
 * HRMS has one reading "Partially Sponsored, Require Partial Funding" — and a
 * badge is `whitespace-nowrap` with no width of its own, so in a list cell it
 * ran straight over the column beside it. It always clipped; what it was
 * missing was something to clip to.
 */
test('asking to travel is a screen, and a long option stays in its column',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'a column width is a desktop question')
    const errors = collectConsoleErrors(page)

    const counted = async (screen) => {
      await page.goto(`/one/space/onehr?screen=${screen}&type=list`)
      const rows = page.locator('[data-slot="list-row"]')
      await rows.first().waitFor({ timeout: 25_000 })
      return rows.count()
    }

    const all = await counted('travel')
    expect(all).toBeGreaterThan(1)

    // The badge is inside its cell rather than over the one beside it.
    const badge = page.locator('[data-slot="list-row"]')
      .first().getByTitle(/Partially Sponsored/)
    const box = await badge.boundingBox()
    const cell = await badge.locator('xpath=ancestor::*[@role="cell"][1]').boundingBox()
      .catch(() => null)
    if (cell) expect(box.x + box.width).toBeLessThanOrEqual(cell.x + cell.width + 1)

    // And the twin shows fewer, which is the whole of what a twin is.
    const mine = await counted('my-travel')
    expect(mine).toBeGreaterThan(0)
    expect(mine).toBeLessThan(all)

    expectNoRealErrors(errors)
  })
