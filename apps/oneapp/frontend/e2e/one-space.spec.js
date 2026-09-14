// One: the space every workspace has.
//
// The front door used to be a grid of cards called Spaces — somewhere you
// arrived in order to leave. It is gone, and what replaced it is a space like
// any other, with the things that belong to no space on it.
//
// Worth a browser test because the failure is the first thing anybody sees.
// A provider that does not fire is a workspace whose root redirects to a space
// that is not there; a redirect that does not except itself is a browser that
// navigates for ever; and a `component` naming nothing renders as "this screen
// has nothing to show yet" with no error anywhere.
import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test('signing in lands inside One rather than on a page about spaces',
  async ({ page, baseURL }) => {
    const errors = collectConsoleErrors(page)

    await signIn(page, baseURL)
    await page.goto('/one/')

    await expect(page).toHaveURL(/\/one\/space\/one/)
    // The greeting is the page, not the shell: if the component did not
    // resolve, the screen host draws its own "nothing to show yet" instead.
    await page.locator('[data-slot="home-greeting"]').waitFor({ timeout: 25_000 })
    await expect(page.locator('[data-slot="home-greeting"]')).toContainText(/Good /)

    expectNoRealErrors(errors)
  })

test('the corner wears One and the rail is One’s', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no bar')

  await signIn(page, baseURL)
  await page.goto('/one/space/one')

  await expect(page.locator('[data-slot="space-switcher"]')).toContainText('One')
  // And One is in its own board, under Spaces, like everything else. It is not
  // a second kind of destination.
  await page.locator('[data-slot="space-switcher"]').click()
  await expect(
    page.locator('[data-slot="app-board"]').getByRole('link', { name: 'One', exact: true }),
  ).toBeVisible()
})

test('an address for a space nobody has lands in One, once',
  async ({ page, baseURL }) => {
    const errors = collectConsoleErrors(page)

    await signIn(page, baseURL)
    await page.goto('/one/space/nothing-here')

    await expect(page).toHaveURL(/\/one\/space\/one/)
    await page.locator('[data-slot="home-greeting"]').waitFor({ timeout: 25_000 })

    expectNoRealErrors(errors)
  })

test('a block with nothing in it is absent rather than empty',
  async ({ page, baseURL }) => {
    await signIn(page, baseURL)
    await page.goto('/one/space/one')
    await page.locator('[data-slot="home-greeting"]').waitFor({ timeout: 25_000 })

    // Whatever the fixture holds, the rule is the same: a card that is drawn
    // has rows in it. A workspace that keeps no calendar should not have a
    // Next up card with a dash in it every morning for a year.
    const cards = page.locator('[data-slot^="home-"]:not([data-slot="home-greeting"])')
    for (let at = 0; at < await cards.count(); at += 1) {
      await expect(cards.nth(at).locator('[data-slot="row"]').first()).toBeVisible()
    }
  })
