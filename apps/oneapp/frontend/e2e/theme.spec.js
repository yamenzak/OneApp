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
const ACCENT = '#e50914'

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
