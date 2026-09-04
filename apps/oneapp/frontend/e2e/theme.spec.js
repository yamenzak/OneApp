// A space's declared look, on the document rather than in a stylesheet.
//
// Three things worth a browser. That an accent declared in a manifest actually
// arrives as a paint on the screen — the whole chain, from the control plane's
// literal through `visible_spaces` to `document.documentElement`. That it is on
// `<html>` and not on the screen's container, which is the only place that also
// reaches a dropdown teleported to `document.body`. And that leaving the space
// puts the reader's own light-or-dark preference back, because a theme that
// overwrote it would be a space that redecorated the whole product on its way
// past.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// What RUA declares, in `oneapp_control/spaces/rua.py`.
const ACCENT = '#ffcd11'

/**
 * How bright a colour a browser handed back is, 0 to 1.
 *
 * Takes the numbers out of whatever notation arrived — `rgb(...)`,
 * `color(srgb ...)`, `#rrggbb` — and scales them to one range, because which
 * one a browser answers with is not something a test should depend on.
 */
function brightness(value) {
  if (value.startsWith('#')) {
    return (
      [1, 3, 5].reduce((sum, at) => sum + parseInt(value.slice(at, at + 2), 16), 0) /
      3 /
      255
    )
  }
  const numbers = (value.match(/[\d.]+/g) || []).slice(0, 3).map(Number)
  if (numbers.length < 3) return 0
  const scale = numbers.some((one) => one > 1) ? 255 : 1
  return numbers.reduce((sum, one) => sum + one, 0) / 3 / scale
}

/** A CSS custom property as the document currently resolves it. */
function token(page, name) {
  return page.evaluate(
    (one) => getComputedStyle(document.documentElement).getPropertyValue(one).trim(),
    name,
  )
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a space paints itself, and hands the document back', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/rua?screen=projects')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  // The declaration reached the paint. `--surface-gray-10` is frappe-ui's solid
  // button, which is near-black by default in both modes — so this is red only
  // if the manifest's own colour got here.
  expect(await token(page, '--surface-gray-10')).toBe(ACCENT)
  // And the mode with it.
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  // On the document, not on a container. The distinction is invisible until a
  // menu opens: dropdowns, dialogs and toasts are teleported to `document.body`
  // and a theme scoped to the screen would skin the list and leave every menu
  // over it in the other palette.
  const inline = await page.evaluate(() =>
    document.documentElement.getAttribute('style'),
  )
  expect(inline).toContain('--surface-gray-10')

  // Out of the space, and the theme goes with it — the launcher is nobody's
  // application and is drawn in the product's own colours.
  await page.goto('/one/')
  await expect
    .poll(() => token(page, '--surface-gray-10'), { timeout: 10_000 })
    .not.toBe(ACCENT)
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', 'dark')

  expectNoRealErrors(errors)
})

test('a bright accent brings its own ink', async ({ page }) => {
  await page.goto('/one/space/rua?screen=projects')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  // The one that matters, and the reason it is a browser test rather than a
  // unit one: what is being checked is that the label on a filled button can
  // be read. `--ink-base` is what frappe-ui puts there, RUA's accent is a
  // bright yellow, and the default in dark mode is a near-black that happens
  // to be right here and was wrong for the red before it. Asserting the token
  // asserts the outcome; asserting the button's colour would assert Tailwind.
  const ink = await token(page, '--ink-base')
  expect(ink.toLowerCase()).toBe('#1c1c1c')

  // And the button really does take it, rather than the token sitting unread.
  //
  // Read as brightness rather than as a string. A browser answers
  // `getComputedStyle` in whichever colour space the value reached it in —
  // this one comes back `color(srgb 1 0.803922 0.0666667)`, not
  // `rgb(255, 205, 17)` — so an exact match tests the pipeline's notation and
  // not the thing that matters, which is that the label is legible on the fill.
  const label = page.getByRole('button', { name: 'New' }).first()
  await expect(label).toBeVisible()
  const painted = await label.evaluate((el) => {
    const style = getComputedStyle(el)
    return { ink: style.color, fill: style.backgroundColor }
  })
  expect(brightness(painted.fill)).toBeGreaterThan(0.6)
  expect(brightness(painted.ink)).toBeLessThan(0.2)
})

test('the ground owns the hairlines and the navigation', async ({ page }) => {
  await page.goto('/one/space/rua?screen=projects')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  // Borders derived from the declared ground rather than left at frappe-ui's
  // step off its own grey — which on a near-black page ruled the screen into
  // boxes. What is asserted is the relationship, not the number: a hairline
  // must be lighter than the ground it is on and much closer to it than to
  // the text.
  const base = await token(page, '--surface-base')
  const rule = await token(page, '--outline-gray-1')
  expect(brightness(rule)).toBeGreaterThan(brightness(base))
  expect(brightness(rule) - brightness(base)).toBeLessThan(40 / 255)

  // And the navigation is its own surface: a step off the page, not the page.
  const sidebar = await token(page, '--surface-sidebar')
  expect(sidebar).not.toBe(base)
  expect(brightness(sidebar)).toBeGreaterThan(brightness(base))
})
