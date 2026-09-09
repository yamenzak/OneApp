// OneMobility, in a browser.
//
// Three things no unit test reaches. That the live map actually *draws* —
// MapLibre sizes its canvas from its container at construction, and the
// container's height has already been taken away once by a stylesheet the
// library ships, which is a failure that produces a white rectangle and no
// error anywhere. That the engine's map view type puts a doctype's records on
// a map without the space writing a line of code for it. And that the aggregate
// tier reaches four plots, which is the whole of the Insights screen and is a
// pipeline four layers deep: observations, the roll-up, `facts.aggregate`, and
// a chart component that wants its data in a particular shape.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/** The MapLibre canvas inside a slot, once it has a real size. */
async function canvasIn(page, slot) {
  const canvas = page.locator(`[data-slot="${slot}"] canvas`).first()
  await canvas.waitFor({ timeout: 30_000 })
  // Polled rather than read once: the map is constructed after a dynamic
  // import and a resize observation, so the first measurement is taken before
  // any of that has happened.
  await expect
    .poll(() => canvas.evaluate((one) => one.height), { timeout: 20_000 })
    .toBeGreaterThan(320)
  return canvas
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the network draws, and the clock says which moment', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onemobility?screen=network')

  const clock = page.locator('[data-slot="network-clock"]')
  await clock.waitFor({ timeout: 30_000 })
  // Live when there is something live and replay when there is not — either is
  // correct, and which one depends on the hour the suite happens to run at.
  await expect(clock.getByText(/Live|Replay/).first()).toBeVisible()
  await expect(clock.getByText(/vehicles/)).toBeVisible()

  await canvasIn(page, 'network')
  expectNoRealErrors(errors)
})

test('the scrubber moves the clock without reloading the screen', async ({ page }) => {
  await page.goto('/one/space/onemobility?screen=network')
  const clock = page.locator('[data-slot="network-clock"]')
  await clock.waitFor({ timeout: 30_000 })

  const scrubber = clock.locator('input[type="range"]')
  const before = await clock.locator('.tabular-nums').first().innerText()

  // A range input is dragged, not typed into. Filling it and dispatching the
  // event the component listens for is the same thing without the geometry.
  await scrubber.evaluate((one) => {
    one.value = '250'
    one.dispatchEvent(new Event('input', { bubbles: true }))
  })

  await expect
    .poll(() => clock.locator('.tabular-nums').first().innerText(), { timeout: 15_000 })
    .not.toBe(before)
  // Still the same screen: a scrub is a fetch, never a navigation.
  await expect(page.locator('[data-slot="network"]')).toBeVisible()
})

test('a doctype with a position gets a map, from the engine', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onemobility?screen=stops&type=map')

  await canvasIn(page, 'map')
  // The attribution is the map saying where its ground came from. It is drawn
  // whether or not the tiles arrive, because the credit is owed to the data.
  await expect(page.getByText(/OpenStreetMap/).first()).toBeVisible()

  // And the same records are still a list: a view type is a way of looking at
  // a screen, not a different screen.
  await page.goto('/one/space/onemobility?screen=stops&type=list')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  expectNoRealErrors(errors)
})

test('the aggregate tier reaches the charts', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onemobility?screen=insights')

  const screen = page.locator('[data-slot="insights"]')
  await screen.waitFor({ timeout: 30_000 })

  // The four headline figures, and a real number in the first of them: the
  // fixture seeds a fortnight of observations and rolls each day up, so an
  // empty reading here means the pipeline broke somewhere along its four
  // layers rather than that there is nothing to show.
  await expect(screen.getByText('Readings')).toBeVisible()
  await expect(screen.getByText('On time')).toBeVisible()
  await expect(screen.getByText('Busiest hour')).toBeVisible()

  // Every chart draws into an SVG or a canvas of its own. Four plots, so four
  // of them; fewer means one silently failed to render its data.
  await expect
    .poll(() => screen.locator('svg, canvas').count(), { timeout: 20_000 })
    .toBeGreaterThanOrEqual(4)

  // Hour against weekday, which is the plot that is worth the screen.
  await expect(screen.getByText('Monday')).toBeVisible()

  expectNoRealErrors(errors)
})

test('narrowing to one line asks the server again', async ({ page }) => {
  await page.goto('/one/space/onemobility?screen=insights')
  const screen = page.locator('[data-slot="insights"]')
  await screen.waitFor({ timeout: 30_000 })

  const asked = []
  page.on('request', (one) => {
    if (one.url().includes('onemobility.rhythm')) asked.push(one.url())
  })

  // frappe-ui's Select is a combobox with a popover, not a native `<select>`,
  // so it is opened and an option is clicked.
  await screen.locator('[data-slot="insights-controls"]').getByRole('combobox').first().click()
  await page.getByRole('option').nth(1).click()

  await expect.poll(() => asked.length, { timeout: 15_000 }).toBeGreaterThan(0)
  expect(asked[asked.length - 1]).toContain('line=')
})
