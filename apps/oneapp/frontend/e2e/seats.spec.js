// What a seat can see, and what it is not shown at all.
//
// A space declares jobs — OneHR ships an employee, a people officer and a
// payroll officer — and the permissions behind them have always been right:
// open Payslips as an employee and you are refused, in a sentence that says
// why. What was wrong was the rail, which listed all thirty screens whatever
// you held. A door drawn for somebody who may not walk through it is a rail
// that has to be learned rather than read, and the refusal is the same
// information arriving one click too late.
//
// `docs/ERP-SPACES.md` §8.4. The unit half is `tests/test_space_seats.py`;
// what only a browser can say is that the payload the rail is built from is
// the one being narrowed.
import { expect, test } from '@playwright/test'

import { signIn } from './auth.js'

// Seeded by `scripts/seed_dev_space.py` holding exactly one seat, because
// everybody else on this fixture holds every role a space ships.
const EMPLOYEE = { user: 'sam@zzmock.test', password: 'Dev-Loop-2026!x' }

/**
 * Every name in the space rail, in the order it draws them.
 *
 * The open screen's own ways of being looked at — Grid, List, Tree — are links
 * in here too. Left in rather than filtered out: nothing this asserts is called
 * one of those, and a selector that tried to tell them apart would be asserting
 * the rail's markup rather than its contents.
 */
const railOf = async (page) =>
  page.locator('[data-slot="space-nav"] a').allInnerTexts()

/**
 * The rail, once it is this space's rather than the shell's.
 *
 * Until the session has answered there is no space to draw and the rail is two
 * links to elsewhere — so reading it at first paint gets `['Spaces', 'Account']`
 * and an assertion about seats that was really about timing. A heading only
 * exists where a space declared screen groups, which is the signal that the
 * real one has arrived.
 */
const railDrawn = (page) =>
  expect(page.locator('[data-slot="nav-heading"]').first()).toBeVisible({
    timeout: 20_000,
  })

/** The words over the groups, which a run of screens draws the first of. */
const headingsOf = async (page) =>
  page.locator('[data-slot="nav-heading"]').allInnerTexts()

test('the rail is the seat, not the space', async ({ browser, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the space rail is a desktop sidebar')

  // A context each rather than one signed out and back in: the shell keeps the
  // session it booted with, so clearing the cookie and logging in again left
  // the first person's rail on screen and the assertion below measured nothing.
  const owner = await browser.newContext()
  const page = await owner.newPage()
  await signIn(page, baseURL)
  await page.goto('/one/space/onehr')
  const missing = await page
    .getByText('No space named', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so OneHR is not here')

  await railDrawn(page)
  const everything = await railOf(page)
  // The dev fixture's owner holds every seat on purpose, so this is the whole
  // manifest and the thing the employee below is measured against.
  expect(everything).toContain('Payslips')
  expect(everything).toContain('Applicants')

  const seat = await browser.newContext()
  const theirPage = await seat.newPage()
  await signIn(theirPage, baseURL, EMPLOYEE)
  await theirPage.goto('/one/space/onehr')
  await railDrawn(theirPage)
  const theirs = await railOf(theirPage)

  // Their own, which is the point: an employee files leave and reads their
  // own record, and the two things they were offered and refused are gone.
  expect(theirs).toContain('People')
  expect(theirs).toContain('Leave')
  expect(theirs).not.toContain('Payslips')
  expect(theirs).not.toContain('Applicants')
  expect(theirs.length).toBeLessThan(everything.length)

  // And a heading with nothing under it goes with them. Hiring is four
  // screens, all the people officer's, so the word should not be drawn at all.
  // Upper-cased by the rail's own styling, and `allInnerTexts` reads what is
  // drawn rather than what was written.
  expect(await headingsOf(theirPage)).not.toContain('HIRING')

  // The link still refuses rather than resolving to something else: a rail
  // that stopped offering a screen is not permission to send somebody
  // somewhere they did not ask for.
  await theirPage.goto('/one/space/onehr?screen=payslips')
  await expect(theirPage.getByText('not of your role in it')).toBeVisible({
    timeout: 20_000,
  })

  await owner.close()
  await seat.close()
})
