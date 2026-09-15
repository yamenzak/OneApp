// A space's front page.
//
// Every block is another screen of the same space, which is what makes it
// role-specific without anything in the browser knowing what a role is: a
// block whose screen the reader cannot open is not sent, and where the
// difference is whose rows rather than which screens, the manifest names a
// `@me`-narrowed twin.
//
// Worth a browser test because the failures are quiet. A block resolved
// against every screen rather than the navigable ones is a door somebody is
// then refused at; a block that keeps the screen's pixel column widths is a
// table clipped against its own panel with nothing to say so; and a home
// declared anywhere but first is a home nobody lands on.
import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test('opening a space lands on its front page, not on somebody’s list',
  async ({ page, baseURL }) => {
    const errors = collectConsoleErrors(page)

    await signIn(page, baseURL)
    await page.goto('/one/space/onecrm')

    await page.locator('[data-slot="space-greeting"]').waitFor({ timeout: 25_000 })
    await expect(page.locator('[data-slot="space-greeting"]')).toContainText(/Good /)

    // Four blocks, each one a screen of this space with that screen's own
    // name, count and New button.
    const blocks = page.locator('[data-slot^="home-block-"]')
    await expect(blocks).toHaveCount(4)
    await expect(page.locator('[data-slot="home-block-my-deals"]'))
      .toContainText('My deals')
    await expect(
      page.locator('[data-slot="home-block-leads"]')
        .getByRole('button', { name: /New Lead/ }),
    ).toBeVisible()

    expectNoRealErrors(errors)
  })

test('a block is a glance, and its table fits the block',
  async ({ page, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'one column there, so nothing to fit beside')

    await signIn(page, baseURL)
    await page.goto('/one/space/oneproject')
    const block = page.locator('[data-slot="home-block-tasks"]')
    await block.waitFor({ timeout: 25_000 })

    // Five rows, because a home is something you glance at on the way
    // somewhere — the screen itself is one press away and has all of them.
    await expect(block.locator('[data-slot="list-row"]')).toHaveCount(5)

    // And no wider than the panel holding it. A screen's column widths are
    // chosen for a page; three of them in a quarter of one add up past the
    // block, and the last column is clipped against its own edge with nothing
    // to scroll.
    const fits = await block.evaluate((el) => {
      const table = el.querySelector('[data-slot="list"]')
      return !table || table.scrollWidth <= el.clientWidth + 1
    })
    expect(fits).toBe(true)
  })

test('a block opens the screen it is a glance at', async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  await page.goto('/one/space/oneproject')

  const block = page.locator('[data-slot="home-block-milestones"]')
  await block.waitFor({ timeout: 25_000 })
  await block.getByRole('button', { name: 'Open', exact: true }).click()
  await expect(page).toHaveURL(/screen=milestones/)
})

test('a row on a block opens that record where its records live',
  async ({ page, baseURL }) => {
    await signIn(page, baseURL)
    await page.goto('/one/space/oneproject')

    const block = page.locator('[data-slot="home-block-projects"]')
    await block.waitFor({ timeout: 25_000 })
    await block.locator('[data-slot="list-row"]').first().click()

    await expect(page).toHaveURL(/screen=projects/)
    await expect(page).toHaveURL(/at=record/)
  })
