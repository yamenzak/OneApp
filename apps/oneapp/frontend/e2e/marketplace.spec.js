// Adding a space to the workspace.
//
// The rail entry is offered to whoever can actually act on it — the control
// plane's `require_workspace_admin` admits the owner and an Admin member, and
// an icon leading to a page of refusals is worse than no icon.
//
// What the page draws depends on something a browser cannot arrange: the
// catalogue lives on the control plane and reaches this site over a signed
// call. A dev site is linked with `scripts/link_dev_control.py` and is not by
// default, so this asserts the half that holds either way — the door is there,
// it opens, and what is behind it is one of two honest answers rather than a
// blank or a stack trace. The card states themselves are
// `tests/test_marketplace.py`, where they can be asked directly.
import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const MEMBER = { user: 'robin@zzmock.test' }

test('the rail offers a way to add a space, and it opens', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no rail')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/files')
  await page.locator('[data-slot="marketplace-link"]').click()

  await expect(page).toHaveURL(/\/one\/add/)
  await expect(page.getByText('Add a space', { exact: true }).first()).toBeVisible()

  // Cards, or the sentence that says why there are none. Never nothing.
  const cards = page.locator('[data-slot="marketplace-card"]')
  const said = page.getByText('Cannot reach your account')
  const empty = page.getByText('Nothing to add right now')
  await expect
    .poll(async () =>
      (await cards.count()) + (await said.count()) + (await empty.count()))
    .toBeGreaterThan(0)

  // Every card says what pressing it would do, rather than showing a button
  // whose state is the only clue.
  for (const card of await cards.all()) {
    const state = await card.getAttribute('data-state')
    expect(['available', 'installing', 'unavailable']).toContain(state)
    if (state !== 'available') {
      await expect(card.locator('[data-slot="marketplace-state"]')).toBeVisible()
    }
  }

  expectNoRealErrors(errors)
})

test('a member is not offered it', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no rail')
  await signIn(page, baseURL, MEMBER)
  await page.goto('/one/files')

  // The gear is beside it and is offered to everybody, so this is the honest
  // check that the rail rendered at all before concluding the entry is absent.
  await expect(page.locator('[data-slot="settings-link"]')).toBeVisible()
  await expect(page.locator('[data-slot="marketplace-link"]')).toHaveCount(0)
})
