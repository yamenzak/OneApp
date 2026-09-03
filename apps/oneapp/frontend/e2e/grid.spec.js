import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// The list as a data grid: a fixed-height pane that owns both its scrollbars.
//
// The bug this exists to stop is not visible in a screenshot of the top of the
// page: a table wider than the window puts its horizontal scrollbar at the
// bottom of the *table*, so on two hundred rows you have to scroll down past
// everything to find out you could have scrolled sideways.

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

const SCROLLER = '[data-slot="list-header"]'

const openList = async (page, screen) => {
  await page.goto(`/one/space/zzmock${screen ? `?screen=${screen}` : ''}`)
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
}

// The element that actually scrolls, found from the header rather than by a
// class: a class is a detail of how it is built, an offsetParent is what it is.
const scrollerBox = (page) =>
  page.evaluate((sel) => {
    const el = document.querySelector(sel)?.parentElement?.closest('div')
    const scroller = el?.scrollWidth > el?.clientWidth ? el : el?.parentElement
    const box = scroller.getBoundingClientRect()
    return {
      bottom: box.bottom,
      viewport: window.innerHeight,
      scrollWidth: scroller.scrollWidth,
      clientWidth: scroller.clientWidth,
      scrollHeight: scroller.scrollHeight,
      clientHeight: scroller.clientHeight,
    }
  }, SCROLLER)

test('the horizontal scrollbar is on screen, not at the foot of the table', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const box = await scrollerBox(page)
  // There is something to scroll sideways to.
  expect(box.scrollWidth).toBeGreaterThan(box.clientWidth)
  // And its bottom edge — where its scrollbar is — is inside the window.
  expect(box.bottom).toBeLessThanOrEqual(box.viewport)
  // Forty rows in a pane this tall means the pane scrolls, not the page.
  expect(box.scrollHeight).toBeGreaterThan(box.clientHeight)
  const pageOverflow = await page.evaluate(
    () => document.documentElement.scrollHeight - document.documentElement.clientHeight,
  )
  expect(pageOverflow).toBeLessThanOrEqual(1)
  expectNoRealErrors(errors)
})

test('the column header stays put while the rows scroll under it', async ({ page }) => {
  await openList(page)

  const header = page.locator(SCROLLER)
  const before = await header.boundingBox()
  await page.mouse.move(400, 300)
  await page.mouse.wheel(0, 600)
  await expect
    .poll(async () => (await header.boundingBox()).y)
    .toBeCloseTo(before.y, 0)
  // And it really did scroll.
  const box = await scrollerBox(page)
  expect(box.scrollHeight).toBeGreaterThan(box.clientHeight)
})

test('the edge says there is more to the right, and stops when there is not', async ({ page }) => {
  await openList(page)

  // An aria-hidden marker, found by its geometry rather than by text: a strip
  // the full height of the pane at one edge of it.
  const edges = page.locator('[aria-hidden="true"].absolute.inset-y-0')
  await expect(edges).toHaveCount(1)

  await page.evaluate((sel) => {
    const header = document.querySelector(sel)
    let el = header.parentElement
    while (el && el.scrollWidth <= el.clientWidth) el = el.parentElement
    el.scrollLeft = el.scrollWidth
  }, SCROLLER)

  // At the far right there is more to the *left* instead — still one marker,
  // and now on the other side of the pane.
  await expect(edges).toHaveCount(1)
  const middle = await page.evaluate((sel) => {
    let el = document.querySelector(sel).parentElement
    while (el && el.scrollWidth <= el.clientWidth) el = el.parentElement
    const box = el.getBoundingClientRect()
    return box.left + box.width / 2
  }, SCROLLER)
  // `?? Infinity` rather than a bare `.x`, because the marker is two elements
  // over this moment and not one: the right-hand one unmounts as the left-hand
  // one mounts, and a `boundingBox()` that lands between them answers null.
  // Thrown, that ends the poll on the first tick; answered as a number that
  // cannot pass, it is simply another tick.
  await expect
    .poll(async () => (await edges.first().boundingBox())?.x ?? Infinity)
    .toBeLessThan(middle)
})

test('the footer counts what matches, and load more appends', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const rows = () => page.locator('[data-slot="list-row"]')

  // The count is what matches, not what was sent — read it rather than pinning
  // a number, because the fixture is a real site and rows come and go.
  // The count is the page-length control now, so it is found by its slot
  // rather than by its shape — a bare "48 of 1,240" would also match the
  // chevron's own button.
  const counter = page.locator('[data-slot="page-length"]')
  const total = Number((await counter.innerText()).split(' of ')[1])
  expect(total).toBeGreaterThan(20)

  // A smaller page, so there is a second one. How many to fetch lives inside
  // the count now — one control, because they are one question.
  await page.locator('[data-slot="page-length"]').click()
  await page.getByRole('menuitem', { name: '20 rows' }).click()
  await expect(rows()).toHaveCount(20)
  await expect(counter).toHaveText(`20 of ${total}`)

  await page.getByRole('button', { name: 'Load more' }).click()
  await expect(rows()).toHaveCount(Math.min(40, total))
  // A second page does not lose the first: appended, not replaced.
  await expect(counter).toHaveText(`${Math.min(40, total)} of ${total}`)
  expectNoRealErrors(errors)
})

test('a table narrower than the pane fills it', async ({ page }) => {
  // Three columns in a wide pane used to be a small table in a pool of white
  // space. Notes is the narrow screen: a title, a body and the activity column.
  const errors = collectConsoleErrors(page)
  await openList(page, 'notes')

  const measured = await page.evaluate((sel) => {
    const header = document.querySelector(sel)
    const scroller = header.parentElement.closest('div')
    const cells = [...header.querySelectorAll('[data-slot="list-header-cell"]')]
    return {
      pane: scroller.clientWidth,
      right: cells.at(-1).getBoundingClientRect().right,
      left: scroller.getBoundingClientRect().left,
      scrollable: scroller.scrollWidth - scroller.clientWidth,
    }
  }, SCROLLER)

  // The last column ends where the pane's own padding starts, and there is
  // nothing to scroll sideways to — the arithmetic has to account for the
  // checkbox inset, the row padding and the gap between every pair of tracks,
  // and forgetting the gaps is a scrollbar over four pixels of nothing.
  expect(measured.scrollable).toBeLessThanOrEqual(1)
  expect(measured.right - measured.left).toBeGreaterThan(measured.pane - 24)
  expectNoRealErrors(errors)
})
