// Two things a stylesheet gets wrong silently.
//
// A `var(--x)` naming a token that does not exist is not an error: CSS drops
// the whole declaration, so a floating panel simply has no background and
// draws over whatever is behind it. And `overflow-x-auto` on its own asks for
// a vertical scroller too — the two axes cannot disagree that way — so a tab
// strip one pixel taller than its box grows a scrollbar down its side.
//
// Both are invisible to a unit test and to the console. They need a browser.
import { expect, test } from '@playwright/test'
import { signIn } from './auth.js'

/** The four frappe-ui renamed out from under the vendored sheets CSS. */
const RENAMED = [
  '--surface-modal',
  '--surface-white',
  '--surface-menu-bar',
  '--outline-gray-modals',
]

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('every token a panel paints itself with resolves, in both schemes', async ({ page }) => {
  await page.goto('/one/space/zzmock')
  await page.waitForTimeout(1500)

  for (const scheme of ['light', 'dark']) {
    await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), scheme)
    const values = await page.evaluate((names) => {
      const root = getComputedStyle(document.documentElement)
      return Object.fromEntries(names.map((n) => [n, root.getPropertyValue(n).trim()]))
    }, RENAMED)
    for (const [name, value] of Object.entries(values)) {
      expect(value, `${name} resolves to nothing in ${scheme}, so anything painting `
        + 'with it is transparent').toBeTruthy()
    }
    // And they move with the scheme rather than being a light-mode hex: the
    // whole point of aliasing them onto live tokens instead of #ffffff.
    if (scheme === 'dark') {
      expect(values['--surface-modal']).not.toBe('oklch(1 0 0)')
    }
  }
})

test('a popover is opaque', async ({ page }) => {
  await page.goto('/one/space/zzmock')
  const bell = page.getByRole('button', { name: /Notification/i }).first()
  await bell.waitFor({ timeout: 20_000 })
  await bell.click()

  const panel = page.locator('[data-slot="content-body"]').first()
  await expect(panel).toBeVisible({ timeout: 10_000 })
  const bg = await panel.evaluate((el) => getComputedStyle(el).backgroundColor)
  expect(bg).not.toBe('rgba(0, 0, 0, 0)')
  expect(bg).not.toBe('transparent')
})

test('a tab strip scrolls sideways and not down', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await page.goto('/one/space/zzmock?screen=events&type=list')
  const row = page.locator('[data-slot="list-row"]').first()
  await row.waitFor({ timeout: 25_000 })
  await row.locator('[data-slot="list-cell"]').nth(1).click()

  await expect(page.locator('[role="tablist"]').first()).toBeVisible({ timeout: 20_000 })
  const strips = await page.evaluate(() =>
    [...document.querySelectorAll('[role="tablist"]')].map((el) => {
      const wrap = el.parentElement
      return {
        overflowY: getComputedStyle(wrap).overflowY,
        over: wrap.scrollHeight - wrap.clientHeight,
      }
    }),
  )
  expect(strips.length).toBeGreaterThan(0)
  for (const strip of strips) {
    // The underline under the active tab is what makes the row one pixel
    // taller than the box it is in, which is all a scrollbar needs.
    expect(strip.overflowY, 'an x-only scroller must pin its y axis').toBe('hidden')
    expect(strip.over).toBeLessThanOrEqual(0)
  }
})
