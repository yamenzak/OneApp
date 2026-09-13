// The 390px baseline — `docs/UNIFICATION.md` §D4, Stage 5.
//
// Every routed surface, at the width of the phone most people have, asserting
// the one thing that is true of all of them and cheap to check: **the page does
// not scroll sideways**. A horizontal scrollbar on a phone is the signature of
// a layout that was designed once, at 1280, and left to fend for itself — a bar
// that does not wrap, a grid with a `min-width`, a table nobody put in a
// scroller. It is not every mobile bug, but it is the one that says "nobody
// looked", and it is the difference between a surface with a phone design and a
// surface with a phone fallback.
//
// One spec rather than an assertion inside each surface's own: the rule is
// about the *set*, and a list of addresses in one place is a list somebody
// notices is short. A new routed surface that is not here is the omission this
// makes visible.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const onDesktop = (page) => (page.viewportSize()?.width || 0) >= 768

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/**
 * Every address the shell can be at, and what has to be on screen before the
 * width is worth measuring.
 *
 * `settle` for the surfaces that draw themselves after a fetch — a canvas, a
 * chart — where there is no one element that means "finished".
 */
const SURFACES = [
  { what: 'a space, as a list', at: '/one/space/zzmock?screen=tasks',
    ready: '[data-slot="list-row"]' },
  { what: 'the drive', at: '/one/files', ready: '[data-slot="drive-file"]' },
  { what: 'the drive, as a grid', at: '/one/files?place=all&as=grid',
    ready: '[data-slot="drive-file"]' },
  { what: 'mail', at: '/one/mail', ready: '[data-slot="mail-thread"], [data-slot="empty-state"]' },
  { what: 'the diary', at: '/one/calendar', settle: 1500 },
  { what: 'the assistant', at: '/one/chat', settle: 1000 },
  { what: 'the spaces', at: '/one', settle: 1000 },
  { what: 'account', at: '/one/account', settle: 1000 },
  { what: 'the marketplace', at: '/one/add', settle: 1500 },
  { what: 'a written screen', at: '/one/space/onemobility?screen=insights', settle: 3000 },
]

for (const surface of SURFACES) {
  test(`${surface.what} fits a phone`, async ({ page }) => {
    test.skip(onDesktop(page), 'the baseline is a phone width; desktop has its own sweep')
    const errors = collectConsoleErrors(page)

    await page.goto(surface.at)
    if (surface.ready) {
      await page.locator(surface.ready).first().waitFor({ timeout: 30_000 })
    }
    if (surface.settle) await page.waitForTimeout(surface.settle)

    // One pixel of slack: a sub-pixel border on a full-width element rounds up
    // in Chromium and is not a layout anybody can see.
    const over = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    )
    expect(over, `${surface.at} scrolls ${over}px sideways`).toBeLessThanOrEqual(1)

    expectNoRealErrors(errors)
  })
}
