// Following a document.
//
// The store is Frappe's `Document Follow`; the delivery is ours, because the
// framework reads that table from exactly one place — an Hourly/Daily/Weekly
// digest email — and writes no in-app notification at all. So this spec is
// mostly about the half that did not exist: press the bell as one person, edit
// the record as another, and watch the row arrive in the panel.
//
// **This spec needs a worker.** `enqueue_create_notification` enqueues — see
// DEVLOOP, and `scripts/dev.sh worker`.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const COLLEAGUE = { user: 'robin@zzmock.test', password: 'Dev-Loop-2026!x' }

// The public note. Frappe's Note has a permission controller of its own — a
// note is readable by its owner or when `public` — so this is the one in the
// fixture that two people can both open, which is what following is about.
const NOTE = 'Van hire terms'

/**
 * The follow switch, which is a menu item behind the three dots.
 *
 * It was a bell in the header, beside a heart, a printer, an assignment
 * control and the document's own steps. Following a record is a standing
 * statement you make once — the wrong kind of thing to spend a permanent
 * button on.
 */
const more = (page) => page.locator('[data-slot="record-more"]')
const bell = (page) => page.getByRole('menuitem', { name: /^(Follow|Stop following)$/ })

/** What the switch says right now, with the menu opened and closed around it. */
const followState = async (page) => {
  await more(page).click()
  const said = (await bell(page).innerText()).trim()
  await page.keyboard.press('Escape')
  return said
}

/** Open the notes screen and click through to one record. */
const openNote = async (page, baseURL, who) => {
  await signIn(page, baseURL, who)
  await page.goto('/one/space/zzmock?screen=notes')
  await page.getByText(NOTE).first().click()
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })
}

test('the bell subscribes, and an edit by somebody else turns up', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the panel is behind the rail')
  const errors = collectConsoleErrors(page)

  // Robin follows the note.
  await openNote(page, baseURL, COLLEAGUE)
  // Idempotent rather than a blind toggle: this fixture is shared, and a spec
  // that assumed "off" would unfollow on the second run and then wait out its
  // timeout for a notification nobody was subscribed to.
  if ((await followState(page)) !== 'Stop following') {
    await more(page).click()
    await bell(page).click()
  }
  expect(await followState(page)).toBe('Stop following')

  // It is stored, not remembered.
  await page.reload()
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })
  expect(await followState(page)).toBe('Stop following')
  expectNoRealErrors(errors)

  // Somebody else edits it. `Content` by label, and never the title: the title
  // is this fixture's identity — every other spec finds the note by it — and
  // the first run of this one renamed it and broke itself.
  await openNote(page, baseURL)
  const pane = page.locator('[data-slot="record-pane"]')
  await pane.getByLabel('Content').fill(`Ring ahead. ${Date.now()}`)
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  // Save is offered only while there is something to save, so it going away is
  // how the header says the write landed.
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0)

  // And Robin is told — by name, and about which field.
  await signIn(page, baseURL, COLLEAGUE)
  await page.goto('/one/space/zzmock?screen=notes')
  await page.getByRole('button', { name: /Notifications/ }).click()
  await expect(
    page.getByText(/updated Note/).first(),
    'no notification arrived. `scripts/dev.sh worker` has to be running: the ' +
      'framework enqueues these, so a bench with only a web server writes none.',
  ).toBeVisible({ timeout: 25_000 })

  // Put the fixture back, so the next run starts from "not following".
  await page.keyboard.press('Escape')
  await openNote(page, baseURL, COLLEAGUE)
  await more(page).click()
  await bell(page).click()
  expect(await followState(page)).toBe('Follow')
})

test('a doctype that does not track its changes has no bell', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the record header is the same one')

  // Contact declares no `track_changes`, so a follow on it could never report
  // anything. A switch that cannot work is not drawn — the server says so, and
  // this asserts the front end believes it rather than guessing from a
  // fieldtype.
  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=people&type=list')
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })

  // The menu opens, so the header rendered and this is not an empty pane — and
  // Like is in it, which is the entry every record has.
  await more(page).click()
  await expect(page.getByRole('menuitem', { name: /^Liked?( ·|$)/ })).toBeVisible()
  await expect(bell(page)).toHaveCount(0)
})
