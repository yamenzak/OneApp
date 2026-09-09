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
  // The readout by its own slot, not by "the first tabular-nums in the bar":
  // the fleet count is set in the same face and sits beside it, so DOM order
  // was deciding which number this test read.
  const readout = clock.locator('[data-slot="network-time"]')
  const before = await readout.innerText()

  // A range input is dragged, not typed into. Filling it and dispatching the
  // event the component listens for is the same thing without the geometry.
  await scrubber.evaluate((one) => {
    one.value = '250'
    one.dispatchEvent(new Event('input', { bubbles: true }))
  })

  await expect
    .poll(() => readout.innerText(), { timeout: 15_000 })
    .not.toBe(before)
  // Still the same screen: a scrub is a fetch, never a navigation.
  await expect(page.locator('[data-slot="network"]')).toBeVisible()
})

test('a doctype with a position gets a map, from the engine', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onemobility?screen=stops&type=map')

  await canvasIn(page, 'map')
  // The credit follows the ground, and this bench has no route out to one.
  //
  // It used to be asserted here unconditionally, and that was right while the
  // ground was raster: we authored the style, so we supplied the credit and it
  // was drawn whether or not a single tile arrived. A vector style carries its
  // own — the full linked one, out of the TileJSON — so on a bench that cannot
  // reach the style there is no credit, and nothing that owes one either: what
  // draws is a flat colour and the records on it. Which rule produces which
  // credit is `tests/test_basemap.py`, where it can be asserted for all four
  // grounds rather than for whichever one this machine can reach.
  await expect(page.getByText(/OpenStreetMap/)).toHaveCount(0)

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
  // Given time, because the screen makes two round trips on mount now: the
  // facet vocabulary first — what can be narrowed is the server's to say, and
  // the bar cannot draw before it answers — and then the numbers. The frame is
  // on screen after the first, so waiting for `[data-slot="insights"]` above is
  // no longer the same thing as waiting for data.
  //
  // Scoped to the headline row rather than matched anywhere on the screen.
  // These words are not unique here and never will be: "Readings" opens a chart
  // subtitle further down and "On time" is a series a legend can hide, so a
  // loose match resolved to two elements and the test passed or failed on
  // whether the assertion beat that chart to the DOM. A test decided by which
  // of two components mounts first is not testing what it says it is.
  const headline = screen.locator('[data-slot="insights-headline"]')
  await expect(headline.getByText('Readings')).toBeVisible({ timeout: 20_000 })
  await expect(headline.getByText('On time')).toBeVisible({ timeout: 20_000 })
  await expect(headline.getByText('Busiest hour')).toBeVisible({ timeout: 20_000 })

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

  // The facet bar's controls are Comboboxes with a button trigger — the value
  // list is long enough on a real network that it has to be searchable — so
  // the trigger is a button carrying the facet's name, not a `<select>`.
  const bar = screen.locator('[data-slot="facet-bar"]')
  await bar.getByRole('button', { name: 'Line' }).click()
  await page.getByRole('option').first().click()

  await expect.poll(() => asked.length, { timeout: 15_000 }).toBeGreaterThan(0)
  // One vocabulary for every screen, sent as one object — see
  // `onemobility/facets.py`. It used to be a bare `line=`, which is how the
  // map and this screen came to have two separate filters.
  expect(asked[asked.length - 1]).toContain('facets=')
})

test('a record carries its own name over to the screen that can say how it ran', async ({ page }) => {
  // A line, a stop and a vehicle are documents; how each of them ran is not —
  // it is in the fact tiers, outside the document system, and no dashboard
  // widget over `tabTransit Line` reaches it. So the record hands its name to
  // Insights through the engine's screen-action, and the facet bar there
  // arrives with that one thing chosen.
  await page.goto('/one/space/onemobility?screen=insights&vehicle=zz-1041')
  const screen = page.locator('[data-slot="insights"]')
  await screen.waitFor({ timeout: 30_000 })

  // Opened *at* a vehicle, so opened where a vehicle can be seen: `vehicleDay`
  // is the tier with that column, and it is the fleet tab that reads it.
  await expect(screen.getByRole('tab', { name: 'The fleet' })).toHaveAttribute(
    'aria-selected', 'true', { timeout: 20_000 },
  )
  await expect(
    screen.locator('[data-slot="facet-bar"]').getByRole('button', { name: /1041/ }),
  ).toBeVisible({ timeout: 20_000 })
})

test('a facet this tier cannot answer is refused before it is used', async ({ page }) => {
  await page.goto('/one/space/onemobility?screen=insights')
  const screen = page.locator('[data-slot="insights"]')
  await screen.waitFor({ timeout: 30_000 })

  // `serviceHour` is rolled per line and per hour and has no vehicle column,
  // so the network tab cannot narrow by one — and says so before anybody
  // chooses, rather than accepting the choice and quietly ignoring it.
  const bar = screen.locator('[data-slot="facet-bar"]')
  await expect(bar.getByRole('button', { name: 'Vehicle' })).toBeDisabled()

  // The fleet tab is rolled per vehicle per day, so there it is a real
  // control. Same bar, same vocabulary, a different table behind it.
  await screen.getByRole('tab', { name: 'The fleet' }).click()
  await expect(bar.getByRole('button', { name: 'Vehicle' })).toBeEnabled({ timeout: 20_000 })
})

test('an overlay is chosen from the panel, and is a link when it is', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onemobility?screen=network')
  const legend = page.locator('[data-slot="network-legend"]')
  await legend.waitFor({ timeout: 30_000 })
  await canvasIn(page, 'network')

  // The switcher is in the layers panel now, not on the key.
  await page.locator('[data-slot="layers-button"]').click()
  await page.locator('[data-slot="overlay-picker"]').getByRole('combobox').click()
  await page.getByRole('option', { name: 'Where it runs late' }).click()
  await page.keyboard.press('Escape')

  // The key is the proof the server answered: its ends are the 5th and 95th
  // percentile of what came back, so a number in the unit means cells exist.
  // Asserting on the canvas cannot work — MapLibre draws into WebGL and a
  // painted surface and an empty one are the same DOM.
  await expect(legend.getByText(/min$/).first()).toBeVisible({ timeout: 30_000 })
  await expect(page).toHaveURL(/overlay=delay/)

  // And the other direction: arriving at the URL opens on that layer, so the
  // corridor somebody found is a thing they can send.
  await page.goto('/one/space/onemobility?screen=network&overlay=occupancy')
  const again = page.locator('[data-slot="network-legend"]')
  await again.waitFor({ timeout: 30_000 })
  await expect(again).toContainText('Where it fills up', { timeout: 30_000 })
  expectNoRealErrors(errors)
})

test('the controls are a rail and the legend is a key', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onemobility?screen=network')
  await canvasIn(page, 'network')

  // The legend holds no controls at all any more. It is the whole point of the
  // split, and it is the thing that quietly regresses the next time somebody
  // needs somewhere to put a switch.
  const legend = page.locator('[data-slot="network-legend"]')
  await expect(legend).toBeVisible({ timeout: 30_000 })
  await expect(legend.getByRole('combobox')).toHaveCount(0)
  await expect(legend.getByRole('switch')).toHaveCount(0)

  const controls = page.locator('[data-slot="map-controls"]')
  await controls.locator('[data-slot="layers-button"]').click()
  await expect(page.getByRole('switch', { name: 'Routes' })).toBeVisible({ timeout: 20_000 })
  await page.keyboard.press('Escape')

  // Seven silhouettes for each of seven modes, drawn rather than named.
  await controls.locator('[data-slot="shapes-button"]').click()
  const picker = page.locator('[data-slot="marker-picker"]')
  await expect(picker).toBeVisible({ timeout: 20_000 })
  // One row per mode, each with two controls: the silhouette the map draws and
  // the glyph the thing is called by. Two different jobs — one moves and
  // rotates and carries occupancy, the other sits beside a name — and the row
  // keeps them apart because of it.
  await expect(
    picker.getByRole('button', { name: 'The silhouette the map draws' }),
  ).toHaveCount(7)
  await expect(
    picker.getByRole('button', { name: 'The glyph beside this mode' }),
  ).toHaveCount(7)

  // And every drawing there is behind the first of them.
  await picker.getByRole('button', { name: 'The silhouette the map draws' }).first().click()
  await expect(page.getByRole('button', { name: 'Articulated bus' })).toBeVisible({
    timeout: 20_000,
  })
  expectNoRealErrors(errors)
})

test('a route can be looked at alone, and put back', async ({ page }) => {
  await page.goto('/one/space/onemobility?screen=network')
  const canvas = await canvasIn(page, 'network')
  const box = await canvas.boundingBox()

  // A route line is eight pixels wide and this fixture's geometry moves with
  // the seed, so the click is aimed at a grid rather than at a coordinate.
  const clear = page.locator('[data-slot="isolate-clear"]')
  for (let x = 0.35; x < 0.8 && !(await clear.count()); x += 0.05) {
    for (let y = 0.2; y < 0.7 && !(await clear.count()); y += 0.05) {
      await page.mouse.click(box.x + box.width * x, box.y + box.height * y)
      await page.waitForTimeout(120)
    }
  }
  await expect(clear).toBeVisible({ timeout: 20_000 })
  await expect(page.locator('[data-slot="network-legend"]')).toContainText('dimmed')

  await clear.click()
  await expect(clear).toHaveCount(0)
})

test('the workspace can change the ground, and it survives a reload', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onemobility?screen=network')
  await canvasIn(page, 'network')

  const open = async () => {
    if (!(await page.locator('[data-slot="ground-picker"]').count())) {
      await page.locator('[data-slot="ground-button"]').click()
    }
    return page.locator('[data-slot="ground-picker"]')
  }

  const picker = await open()
  await expect(picker).toBeVisible({ timeout: 20_000 })
  const places = picker.getByRole('switch')
  await expect(places).toHaveAttribute('aria-checked', 'true')

  // A sentinel on the window, because the claim being tested is that this does
  // *not* reload: labels and detail are properties of layers already on the
  // map, and a screen that quietly re-fetched the world would pass every other
  // assertion here.
  await page.evaluate(() => {
    window.__ground = 'same document'
  })

  await places.click()
  await expect(places).toHaveAttribute('aria-checked', 'false')
  expect(await page.evaluate(() => window.__ground)).toBe('same document')

  // frappe-ui's Select is a combobox rather than a native one, so it is opened
  // and picked from rather than filled.
  await (await open()).getByRole('combobox').nth(1).click()
  await page.getByRole('option', { name: 'Minimal', exact: true }).click()
  expect(await page.evaluate(() => window.__ground)).toBe('same document')

  // And it is the workspace's, not this tab's.
  await page.reload()
  await canvasIn(page, 'network')
  const after = await open()
  await expect(after.getByRole('switch')).toHaveAttribute('aria-checked', 'false')
  await expect(after.getByRole('combobox').nth(1)).toContainText('Minimal')

  // Put the fixture back: this setting is shared, so a spec that left it
  // changed would be changing what every later spec is looking at.
  await after.getByRole('switch').click()
  await (await open()).getByRole('combobox').nth(1).click()
  await page.getByRole('option', { name: 'Quiet', exact: true }).click()
  await expect((await open()).getByRole('combobox').nth(1)).toContainText('Quiet')
  expectNoRealErrors(errors)
})

test('the outlook reads the same tier forward, and says what it rests on', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/onemobility?screen=outlook')

  // Four figures and the plots under them, all off `serviceHour` — the same
  // table Insights reads, asked about a day rather than a window.
  const headline = page.locator('[data-slot="outlook-headline"]')
  await headline.waitFor({ timeout: 30_000 })
  await expect(headline.getByText('Worst hour')).toBeVisible()
  await expect(headline.getByText('Chance of late')).toBeVisible()

  // The rule the screen exists to keep: three lines and not one, so the
  // spread is drawn rather than averaged away.
  for (const band of ['Half the runs', 'Most runs', 'Nearly all runs']) {
    await expect(page.getByText(band, { exact: true })).toBeVisible({ timeout: 20_000 })
  }

  // And what it is resting on, in readings rather than as a claim of accuracy.
  await expect(page.locator('[data-slot="outlook-controls"]')).toContainText('readings')
  await expect(page.locator('[data-slot="outlook-unusual"]')).toBeVisible()

  // And whether any of it has been right, off the record the nightly job wrote
  // before the answer existed — which is the only version of this number that
  // means anything.
  const scored = page.locator('[data-slot="outlook-accuracy"]')
  await expect(scored).toContainText('Inside the range')
  await expect(scored).toContainText('written down the night before')
  expectNoRealErrors(errors)
})

test('a day next week is the same lookup as a day last week', async ({ page }) => {
  await page.goto('/one/space/onemobility?screen=outlook')
  const headline = page.locator('[data-slot="outlook-headline"]')
  await headline.waitFor({ timeout: 30_000 })

  const controls = page.locator('[data-slot="outlook-controls"]')
  await controls.getByRole('combobox').first().click()
  await page.getByRole('option', { name: 'Tomorrow', exact: true }).click()

  // Still answered, and still off the aggregate tier: a Wednesday that has not
  // happened is every Wednesday that has, which is the whole argument for this
  // being one read rather than a forecaster bolted onto a reporter.
  await expect(headline.getByText('Worst hour')).toBeVisible({ timeout: 20_000 })
  await expect(controls).toContainText('readings')
})

test('the scrubber runs past now, and says it has', async ({ page }) => {
  await page.goto('/one/space/onemobility?screen=network')
  const clock = page.locator('[data-slot="network-clock"]')
  await clock.waitFor({ timeout: 30_000 })
  await canvasIn(page, 'network')

  // The forward half of README §7a: the same control, past the present. Driven
  // to the end of the service day, which on today is always ahead of now — and
  // on the seeded fixture is an hour the roll-up has a history for.
  const scrub = clock.locator('input[type="range"]')
  await scrub.evaluate((el) => {
    el.value = '1000'
    el.dispatchEvent(new Event('input', { bubbles: true }))
  })

  // A moment that has not happened is a claim, and the badge is the only place
  // on the clock that can say which of the two the reader is looking at.
  await expect(clock.getByText('Expected', { exact: true })).toBeVisible({ timeout: 20_000 })
  // And no vehicle reported at a time that has not arrived. A fleet left over
  // from the last poll would be read as one that had.
  await expect(clock.getByText('0 vehicles')).toBeVisible()

  // Back to live, and the claim goes with it.
  await clock.getByRole('button', { name: 'Live' }).click()
  await expect(clock.getByText('Expected', { exact: true })).toHaveCount(0)
})
