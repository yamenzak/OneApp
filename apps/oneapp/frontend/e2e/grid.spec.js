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

const openList = async (page, view) => {
  await page.goto(`/one/app/zztasks${view ? `?view=${view}` : ''}`)
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
  await openList(page, 'backlog')

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
  await openList(page, 'backlog')

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
  await openList(page, 'backlog')

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
  await expect.poll(async () => (await edges.first().boundingBox()).x).toBeLessThan(middle)
})

test('the footer counts what matches, and load more appends', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page, 'backlog')

  const rows = () => page.locator('[data-slot="list-row"]')

  // The count is what matches, not what was sent — read it rather than pinning
  // a number, because the fixture is a real site and rows come and go.
  const counter = page.getByText(/^\d+ of \d+$/)
  const total = Number((await counter.innerText()).split(' of ')[1])
  expect(total).toBeGreaterThan(20)

  // A smaller page, so there is a second one.
  // A radio group, not buttons — TabButtons is a real single-choice control.
  await page.getByRole('radio', { name: '20', exact: true }).click()
  await expect(rows()).toHaveCount(20)
  await expect(counter).toHaveText(`20 of ${total}`)

  await page.getByRole('button', { name: 'Load more' }).click()
  await expect(rows()).toHaveCount(Math.min(40, total))
  // A second page does not lose the first: appended, not replaced.
  await expect(counter).toHaveText(`${Math.min(40, total)} of ${total}`)
  expectNoRealErrors(errors)
})
