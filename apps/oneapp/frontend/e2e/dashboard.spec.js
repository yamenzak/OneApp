// The dashboard view.
//
// The fourth way of looking at a screen, and the first that draws no records.
// What matters is that it is *declared* — the widgets come out of the space's
// manifest, computed against the same rows the list shows — so this asserts
// the whole path: a screen that declares widgets offers the type, the type
// draws them, and the toolbar above them narrows them.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const open = async (page, baseURL, query = '') => {
  await signIn(page, baseURL)
  await page.goto(`/one/space/zzmock?screen=tasks&type=dashboard${query}`)
}

test('a screen that declares widgets offers a dashboard, and draws them', async ({
  page,
  baseURL,
}) => {
  const errors = collectConsoleErrors(page)
  await open(page, baseURL)

  // One of each family, from the manifest: two readings, a ring, bars, a line
  // down time and a grid.
  const widgets = page.locator('[data-oneapp-widget]')
  await expect(widgets).toHaveCount(6, { timeout: 20_000 })

  // The readings are numbers the server counted, not placeholders.
  await expect(page.getByText('Open', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Closed', { exact: true }).first()).toBeVisible()

  // And the plots rendered. frappe-ui runs echarts with the SVG renderer
  // rather than the canvas one — it keeps text selectable and costs less of
  // echarts — so the proof that a chart is a chart is an `<svg>` with
  // something in it, not a canvas.
  for (const kind of ['donut', 'bar', 'line', 'heatmap']) {
    await expect(
      page.locator(`[data-oneapp-widget="${kind}"] svg`).first(),
      `the ${kind} drew no plot`,
    ).toBeVisible({ timeout: 20_000 })
  }

  expectNoRealErrors(errors)
})

test('a screen with nothing to measure does not offer one', async ({ page, baseURL }) => {
  // Notes declares no widgets, so the type is dropped rather than opening on
  // an empty page — the same rule that keeps a board off a screen with no
  // field to make columns of.
  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=notes')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })
  await expect(
    page.locator('a[href*="screen=notes"][href*="type=dashboard"]'),
  ).toHaveCount(0)
})

test('the dashboard is narrowed by the filter above it', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the quick filters are behind a control')

  // A dashboard that ignored the filter above it would quietly disagree with
  // its own screen, which is the one thing it must not do. The quick filter
  // row is the same toolbar the list sits under, and the charts are re-fetched
  // through the same `payload()` the rows are.
  await open(page, baseURL)
  const ring = page.locator('[data-oneapp-widget="donut"]')
  await expect(ring).toBeVisible({ timeout: 20_000 })
  const both = await ring.textContent()

  await page.getByRole('combobox').filter({ hasText: 'Status' }).click()
  await page.getByRole('option', { name: 'Open', exact: true }).click()

  // One status rather than two, so the ring says something different. What it
  // says is the server's business; that it moved at all is this test's.
  await expect
    .poll(async () => ring.textContent(), { timeout: 20_000 })
    .not.toBe(both)
})
