import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

async function openTab(page, label) {
  await page.goto('/admin/setup')
  await page.getByRole('button', { name: /settings/i }).first().click()
  await page.getByText(label, { exact: true }).click()
}

test('the model catalogue renders', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openTab(page, 'Models')

  await expect(page.getByText('AI models').first()).toBeVisible()
  await expect(page.getByText('gemini-3.7-flash').first()).toBeVisible()

  await info.attach('models', {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

test('a model that could not be priced says why', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openTab(page, 'Models')

  await page.getByText('flux-2-dev').first().click()
  // The wording that defeated the parser, verbatim. A model held back with no
  // reason is a model nobody can put back.
  await expect(page.getByText(/could not price/i).first()).toBeVisible()
  await expect(page.getByText('Markup override').first()).toBeVisible()

  await info.attach('needs-review', {
    body: await page.screenshot(), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

test('the feature registry renders', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openTab(page, 'Features')

  await expect(page.getByText('Invoice summary').first()).toBeVisible()

  // Desktop only: the Control column is dropped on a phone, where which
  // features are always-on is answered by opening one rather than by the list.
  if (test.info().project.name === 'desktop') {
    await expect(page.getByText('Always on').first()).toBeVisible()
  }

  await info.attach('features', {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

/**
 * Measured, not eyeballed, and across every panel rather than only the new ones.
 *
 * A flex item's `min-width` defaults to `auto`, so a table declaring
 * `min-w-[40rem]` stretched its panel instead of scrolling: 787px of panel in a
 * 412px viewport, with `document.scrollWidth` clean the whole time because the
 * dialog clips what overflows. Nothing in a screenshot shows that — the panel
 * simply looks cropped.
 */
test.describe('every settings panel fits a phone', () => {
  const PANELS = ['Plans', 'Apps', 'Regions', 'Storage buckets', 'Models', 'Features']

  for (const label of PANELS) {
    test(label, async ({ page }) => {
      await openTab(page, label)
      const geometry = await page.evaluate(() => {
        const panel = document.querySelector('[role="tabpanel"][data-state="active"]')
        return { viewport: window.innerWidth, panel: panel.clientWidth }
      })
      expect(geometry.panel, `${label} is wider than the viewport`)
        .toBeLessThanOrEqual(geometry.viewport)
    })
  }
})
