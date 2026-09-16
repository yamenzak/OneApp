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
    //
    // Waited for rather than counted. The board's first group is the session's
    // spaces, which arrive with the session rather than with the catalogue, so
    // a `count()` — asked once, never retried — read whatever had rendered by
    // then. The twenty-first tile being there says the same thing and waits.
    await expect(tiles.nth(20)).toBeVisible({ timeout: 25_000 })

    // Every catalogue tile draws its mark. An `<svg>` with nothing in it is
    // what a brand name this build does not have produces, and it is
    // invisible. Only the catalogue's: a space of a customer's own wears no
    // mark and gets its initial, which is `SpaceFace`'s third answer.
    //
    // Polled, because it is *two* counts and a tile rendering between them is
    // a mismatch that means nothing. `expect.poll` reads the pair together and
    // retries until they agree or time out.
    const off = board.locator('[data-slot="app-tile-off"]')
    await expect
      .poll(async () => (await off.locator('svg').count()) - (await off.count()), {
        timeout: 15_000,
      })
      .toBe(0)
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

  // OneWorkbook is one of the three editors, and the thing worth asserting
  // about them is that they do not all open the same thing: each is the file
  // manager landed on the place that holds what it makes.
  //
  // A press and not a link. What it opens is a window, and a window has no
  // address to follow — `onestorage/lib/window.js`. The board drew these as
  // links while the dock pressed them, which was one tile with two behaviours
  // depending which copy of it you found.
  // Scoped to the board: the dock has a tile of the same name since the
  // editors got theirs, and this test is about the board's.
  await page.locator('[data-slot="app-board"]')
    .getByRole('button', { name: 'OneWorkbook' })
    .click()
  const room = page.locator('[data-window="onesheet"]')
  await expect(room).toBeVisible({ timeout: 15_000 })
  await expect(room.locator('[data-slot="drive-window-path"]')).toContainText('Workbooks')
  // And the page underneath is where it was: that is what a window is for.
  await expect(page).toHaveURL(/\/one\/space\/onehr/)

  expectNoRealErrors(errors)
})

test('the corner folds to the mark alone', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no bar')

  await signIn(page, baseURL)
  await page.goto('/one/space/onehr')

  const corner = page.locator('[data-slot="space-switcher"]')
  await expect(corner).toContainText('OnePeople')

  await page.locator('[data-slot="sidebar-collapse"]').click()
  // The name and the chevrons go; the mark does not. A 3rem column has no room
  // for a chevron that says what the press already says.
  await expect(corner).not.toContainText('OnePeople')
  await expect(corner.locator('svg')).toHaveCount(1)
  // And it still opens.
  await corner.click()
  await expect(page.locator('[data-slot="app-tile"]').first()).toBeVisible()
})

test('the dock says which app you are standing in', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone draws no dock')

  await signIn(page, baseURL)
  await page.goto('/one/files')

  // Every other navigation in this product marks where you are — the rail's
  // open screen, a list's open row — and a row of marks is worse than a row of
  // glyphs at saying it, because a mark is bright whether or not you are in it.
  const files = page.locator('[data-app="files"]')
  await files.waitFor({ timeout: 25_000 })
  await expect(files).toHaveAttribute('data-open', 'yes')
  await expect(page.locator('[data-app="mail"]')).toHaveAttribute('data-open', 'no')

  await page.goto('/one/calendar')
  await expect(page.locator('[data-app="calendar"]'))
    .toHaveAttribute('data-open', 'yes', { timeout: 15_000 })
  await expect(files).toHaveAttribute('data-open', 'no')
})

test('an app this workspace has not got is in the dock, dim, and says why',
  async ({ page, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no dock')

    await signIn(page, baseURL)
    await page.goto('/one/files')
    await page.locator('[data-slot="dock"]').waitFor({ timeout: 25_000 })

    // The rule the whole catalogue exists for, §F1: a surface renders what the
    // source declared — including what it cannot do — rather than leaving a
    // gap somebody cannot ask a question about. Every dock tile is one or the
    // other, and neither is a link that refuses.
    const tiles = page.locator('[data-slot="dock-tile"], [data-slot="dock-tile-off"]')
    expect(await tiles.count()).toBeGreaterThan(0)

    // By index rather than over a snapshot of handles. Whether an app is live
    // is sometimes answered a moment after the page settles — the assistant's
    // is a fetch — so a tile can flip from off to on between `all()` and the
    // assertion, and a handle bound to the element it replaced is stale. `nth`
    // is a live locator and re-resolves, so a tile that stops being dim simply
    // stops being one of these.
    const off = page.locator('[data-slot="dock-tile-off"]')
    for (let at = 0; at < await off.count(); at += 1) {
      const one = off.nth(at)
      await expect(one).toHaveAttribute('aria-disabled', 'true')
      expect((await one.getAttribute('title')) || '').not.toBe('')
    }
  })

test('One is written quietly, in the corner as well as on the board',
  async ({ page, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no bar')

    await signIn(page, baseURL)
    await page.goto('/one/space/onehr')

    // The corner used to write a space's name flat, because it decided by kind
    // — a space is somebody's — and OnePeople is a space whose name is still
    // ours. Both halves are here, and the prefix is the quiet one.
    const corner = page.locator('[data-slot="space-switcher"]')
    await expect(corner).toContainText('OnePeople')
    await expect(corner.locator('[data-slot="brand-prefix"]')).toHaveText('One')

    // And the same on the board one row down, which is where it was already
    // right — so this is the assertion that they agree.
    await corner.click()
    const tile = page
      .locator('[data-slot="app-board"] [data-slot="app-tile"]')
      .filter({ hasText: 'OnePeople' })
      .first()
    await expect(tile.locator('[data-slot="brand-prefix"]')).toHaveText('One')

    // A space a customer named is said whole: RUA wears no mark of ours.
    const rua = page
      .locator('[data-slot="app-board"] [data-slot="app-tile"]')
      .filter({ hasText: 'RUA' })
      .first()
    await expect(rua.locator('[data-slot="brand-prefix"]')).toHaveCount(0)
  })

test('the assistant opens from the dock, and one more press puts it away',
  async ({ page, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'the widget is a page on a phone')

    await signIn(page, baseURL)
    await page.goto('/one/space/onehr')

    // Its own mark, the same one the board and the switcher draw. An `<svg>`
    // with nothing in it is what a brand name this build does not have
    // produces, so this is the witness for the mark as well as the tile.
    const tile = page.locator('[data-slot="dock-tile"][data-app="chat"]')
    await tile.waitFor({ timeout: 25_000 })
    await expect(tile.locator('[data-slot="brand-oneai"]')).toBeVisible()

    const widget = page.locator('[data-window="assistant"]')
    await tile.click()
    await expect(widget).toBeVisible()
    // And the dock marks it while it is open, because that is what "you are in
    // it" means for a surface that floats over the page.
    await expect(tile).toHaveAttribute('data-open', 'yes')

    // One more press folds it away — the only thing left to ask of a window
    // you are looking at. Folded and not closed: it is still on the desk, its
    // tile still lit, and what was in it is still there.
    await tile.click()
    await expect(widget).toBeHidden()
    await expect(tile).toHaveAttribute('data-open', 'yes')

    // And back, with the same window rather than a new one.
    await tile.click()
    await expect(widget).toBeVisible()
  })
