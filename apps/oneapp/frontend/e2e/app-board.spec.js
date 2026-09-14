// The corner, and what is behind it.
//
// The switcher used to show this workspace's spaces and the four apps that
// happened to be switched on. So the answer to "is there a OneTask" was
// silence — indistinguishable from "yes, and you cannot see it". The board is
// the whole catalogue now: what is here, what is not, and why not.
//
// Worth a browser test because all three failures are quiet. A tile whose mark
// is missing renders as an empty square; a `router-link` on a disabled entry
// renders as something pressable that goes to the wrong place; and a popover
// whose scroller is a hard clip looks like a rendering fault rather than like
// there being more below.
import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.describe.configure({ mode: 'serial' })

test('the board is every app, not the four this workspace switched on',
  async ({ page, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no bar')
    const errors = collectConsoleErrors(page)

    await signIn(page, baseURL)
    await page.goto('/one/space/onehr')
    await page.locator('[data-slot="space-switcher"]').click()

    // Three groups, in this order: where you work, what is beside it, and what
    // there is that you have not got. Scoped to the board, because the rail
    // behind it says "Spaces" too.
    const board = page.locator('[data-slot="app-board"]')
    const tiles = board.locator('[data-slot="app-tile"], [data-slot="app-tile-off"]')
    await tiles.first().waitFor({ timeout: 25_000 })
    await expect(board.getByText('Spaces', { exact: true })).toBeVisible()
    await expect(board.getByText('Apps', { exact: true })).toBeVisible()
    await expect(board.getByText('Not here yet', { exact: true })).toBeVisible()

    // More than twenty: the design draws twenty-seven and two of them are
    // deliberately off the board. An exact count would be a test of the
    // fixture's space list rather than of this.
    expect(await tiles.count()).toBeGreaterThan(20)

    // Every catalogue tile draws its mark. An `<svg>` with nothing in it is
    // what a brand name this build does not have produces, and it is
    // invisible. Only the catalogue's: a space of a customer's own wears no
    // mark and gets its initial, which is `SpaceFace`'s third answer.
    const off = board.locator('[data-slot="app-tile-off"]')
    expect(await off.locator('svg').count()).toBe(await off.count())
    expectNoRealErrors(errors)
  })

test('an app nobody has built is on the board, dim, and says so',
  async ({ page, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no bar')
    const errors = collectConsoleErrors(page)

    await signIn(page, baseURL)
    await page.goto('/one/space/onehr')
    await page.locator('[data-slot="space-switcher"]').click()

    const soon = page.locator('[data-slot="app-tile-off"]', { hasText: 'OneTask' })
    await soon.waitFor({ timeout: 25_000 })
    await expect(soon).toHaveAttribute('title', 'Not built yet')
    // Not a link: a disabled tile is a plain element, so there is nothing to
    // press rather than something that refuses.
    await expect(soon).toHaveAttribute('aria-disabled', 'true')
    expect(await soon.evaluate((el) => el.tagName)).toBe('DIV')

    expectNoRealErrors(errors)
  })

test('a live tile opens the app it draws', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no bar')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/onehr')
  await page.locator('[data-slot="space-switcher"]').click()

  // OneSheet is one of the three editors, and the thing worth asserting about
  // them is that they do not all go to the same page: each opens the place in
  // the Drive that holds what it makes.
  await page.getByRole('link', { name: 'OneSheet' }).click()
  await expect(page).toHaveURL(/\/one\/files\?place=workbooks/)

  expectNoRealErrors(errors)
})

test('the corner folds to the mark alone', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no bar')

  await signIn(page, baseURL)
  await page.goto('/one/space/onehr')

  const corner = page.locator('[data-slot="space-switcher"]')
  await expect(corner).toContainText('OneHR')

  await page.locator('[data-slot="sidebar-collapse"]').click()
  // The name and the chevrons go; the mark does not. A 3rem column has no room
  // for a chevron that says what the press already says.
  await expect(corner).not.toContainText('OneHR')
  await expect(corner.locator('svg')).toHaveCount(1)
  // And it still opens.
  await corner.click()
  await expect(page.locator('[data-slot="app-tile"]').first()).toBeVisible()
})

test('the foot says which surface you are standing in', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no column')

  await signIn(page, baseURL)
  await page.goto('/one/files')

  // Every other navigation in this product marks where you are — the rail's
  // open screen, a list's open row — and this row of four identical glyphs
  // said nothing at all until it did.
  const files = page.locator('[data-slot="files-link"]')
  await files.waitFor({ timeout: 25_000 })
  await expect(files).toHaveClass(/bg-surface-elevation-3/)
  await expect(page.locator('[data-slot="mail-link"]')).not.toHaveClass(
    /bg-surface-elevation-3/,
  )

  await page.goto('/one/calendar')
  await expect(page.locator('[data-slot="calendar-link"]'))
    .toHaveClass(/bg-surface-elevation-3/, { timeout: 15_000 })
  await expect(files).not.toHaveClass(/bg-surface-elevation-3/)
})

test('the quick dial is the assistant’s own mark, and it opens', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the widget is a page on a phone')

  await signIn(page, baseURL)
  await page.goto('/one/space/onehr')

  // The mark fills the disc rather than sitting small inside a washed ring —
  // which is what made it read as a generic corner button. An `<svg>` with
  // nothing in it is what a brand name this build does not have produces.
  const dial = page.locator('[data-slot="assistant-launcher"]')
  await dial.waitFor({ timeout: 25_000 })
  await expect(dial.locator('[data-slot="brand-oneai"]')).toBeVisible()

  await dial.click()
  await expect(page.locator('[data-slot="assistant-widget"]')).toBeVisible()
  // And the foot marks it while it is showing, because that is what "you are
  // in it" means for a surface that floats over the page.
  await expect(page.locator('[data-slot="chat-link"]'))
    .toHaveClass(/bg-surface-elevation-3/)
})
