// Where an open record is drawn, and who decides.
//
// Three surfaces — the pane beside the list, the page that is the whole content
// area, and the drawer over a page — and the bugs they hide are all of the
// "renders fine, means the wrong thing" kind: a name printed twice, a peeked
// record that replaced the thing you were reading, a preference nobody stored.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

async function openFirst(page, screen) {
  await page.goto(`/one/space/rua?screen=${screen}`)
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 25_000 })
}

test('a record can be made to fill the window, and it is remembered', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'a phone has one surface and no choice')
  const errors = collectConsoleErrors(page)

  await openFirst(page, 'invoices')

  // It opens beside the list, because the invoices screen declares no showcase.
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
  const beside = await page.locator('[data-slot="record-pane"]').boundingBox()

  await page.getByRole('button', { name: 'Fill the window' }).click()
  await expect(page.locator('[data-slot="list-row"]').first()).toBeHidden()
  const whole = await page.locator('[data-slot="record-pane"]').boundingBox()
  expect(whole.width).toBeGreaterThan(beside.width)

  // A preference, not a click you make every time: the next record on this
  // screen opens the way the last one was left.
  //
  // Settled first: a reload while the record's own requests are in flight
  // aborts them, and an aborted fetch reaches the console as a real-looking
  // error that has nothing to do with what is being tested.
  await page.waitForLoadState('networkidle')
  await page.reload()
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 25_000 })
  await expect(page.locator('[data-slot="list-row"]').first()).toBeHidden()

  // And back, so the test leaves the browser as it found it — the preference
  // is per screen and would otherwise reach every spec that opens an invoice.
  await page.getByRole('button', { name: 'Show beside the list' }).click()
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  expectNoRealErrors(errors)
})

test('a record says its own name once', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a phone covers the trail, so it says it')
  const errors = collectConsoleErrors(page)

  // In a pane the trail above the list says it, so the header does not.
  await openFirst(page, 'invoices')
  await expect(page.locator('[data-slot="record-identity"]')).toBeHidden()

  // On a showcase page the hero says it, in 48px — and the trail still does
  // too, so the header stays quiet there as well. Settled before leaving, for
  // the same reason as above.
  await page.waitForLoadState('networkidle')
  await page.goto('/one/space/rua?screen=projects')
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="showcase-title"]').waitFor({ timeout: 25_000 })
  await expect(page.locator('[data-slot="record-identity"]')).toBeHidden()

  expectNoRealErrors(errors)
})

test('a record that fills the window has one header, not two', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a phone covers the trail and draws its own')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/rua?screen=projects')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="showcase"]').waitFor({ timeout: 25_000 })

  // One row of controls, and it is on the trail's line rather than in a band of
  // its own: it sits above the photograph, in the header the screen already had.
  const controls = page.locator('[data-slot="record-controls"]')
  await expect(controls).toHaveCount(1)
  const bar = await controls.boundingBox()
  const hero = await page.locator('[data-slot="showcase"]').boundingBox()
  expect(bar.y + bar.height).toBeLessThanOrEqual(hero.y + 1)
  // The trail is on that same line, which is what makes it one header and not
  // a second one that happens to be thin.
  const trail = await page.locator('[data-slot="breadcrumb"]').boundingBox()
  expect(Math.abs(trail.y - bar.y)).toBeLessThan(24)

  // And New stands down: the list it would add a row to is not on screen.
  await expect(page.getByRole('button', { name: 'New' })).toBeHidden()

  // A pane keeps its own band — it is a column beside a list whose header is
  // the trail, so its controls are the pane's and sit below that line.
  await page.waitForLoadState('networkidle')
  await page.goto('/one/space/rua?screen=invoices')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 25_000 })
  const inPane = await page.locator('[data-slot="record-controls"]').boundingBox()
  const listTrail = await page.locator('[data-slot="breadcrumb"]').boundingBox()
  expect(inPane.y).toBeGreaterThan(listTrail.y + listTrail.height)
  await expect(page.getByRole('button', { name: 'New' })).toBeVisible()

  expectNoRealErrors(errors)
})

test('a line opened from a project opens over it, not instead of it', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the drawer is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/space/rua?screen=projects')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  // A job with invoices against it. Their jobs are in `modified` order, so this
  // opens a few and stops at the first whose Invoices tab has rows.
  const rows = page.locator('[data-slot="list-row"]')
  const last = await rows.count()
  let opened = false
  for (let at = last - 1; at >= Math.max(0, last - 20) && !opened; at -= 1) {
    await rows.nth(at).scrollIntoViewIfNeeded()
    await rows.nth(at).click()
    await page.locator('[data-slot="showcase-title"]').waitFor({ timeout: 25_000 })
    await page.locator('[data-slot="tab-list"]').first().getByRole('tab', { name: 'Invoices' }).click()
    const inside = page.locator('[data-slot="record-pane"] [data-slot="list-row"]').first()
    await inside.waitFor({ timeout: 6_000 }).catch(() => {})
    if (await inside.count()) {
      await inside.click()
      opened = true
    } else {
      await page.getByRole('button', { name: 'Close the record' }).click()
    }
  }
  test.skip(!opened, 'none of the last twenty jobs has an invoice against it')

  // `textContent`, not `innerText`: the hero is `text-transform: uppercase`, so
  // `innerText` returns what is painted and `toHaveText` compares what is in
  // the DOM. Reading one and asserting the other fails on capitals alone.
  const job = await page.locator('[data-slot="showcase-title"]').first().textContent()

  await page.locator('[data-slot="record-drawer"]').waitFor({ timeout: 20_000 })
  // In the URL, so it is a place with a link and the back button undoes it.
  expect(new URL(page.url()).searchParams.get('peek')).toBeTruthy()
  expect(new URL(page.url()).searchParams.get('peekScreen')).toBe('invoices')

  // The job is still there, under it. That is the whole point of the drawer.
  await expect(page.locator('[data-slot="showcase-title"]').first()).toHaveText(job)

  // Nothing else on screen is naming the invoice, so the drawer's header does.
  await expect(page.locator('[data-slot="record-identity"]')).toBeVisible()

  // Escape puts the job back, and takes the peek out of the URL with it.
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-slot="record-drawer"]')).toBeHidden()
  expect(new URL(page.url()).searchParams.get('peek')).toBeNull()

  expectNoRealErrors(errors)
})
