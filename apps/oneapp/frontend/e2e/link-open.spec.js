// A Link field offers to open what it points at — beside this, or instead of it.
//
// A Link is a record, and until now the form let you *change* which one and
// never let you go and look at it. The two buttons on the field's label row are
// the two things somebody actually wants: read it without losing the page they
// are on, or go and work on it.
//
// What is worth a browser here is not the buttons. It is that the destination
// is real: a Link holds a doctype and an id, this product has routes for
// *screens*, and which screen shows that doctype is a question only the space's
// own manifest answers. So these open a record and assert the record arrived.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/**
 * Open the first invoice, which is the fixture's most reliable link.
 *
 * Every invoice carries a customer, and RUA shows Customer on its Clients
 * screen — so `customer` is a link with a value *and* somewhere to go, which is
 * the pair this feature needs and which most links do not have. A project's
 * `custom_parent_project` is the other one, and only thirty-five of eighty-two
 * projects have it: finding one means scanning, and scanning a list on a
 * single-threaded dev server is a test that times out for reasons unrelated to
 * what it tests.
 */
async function openAnInvoice(page) {
  await page.goto('/one/space/rua?screen=invoices')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 25_000 })
  await rows.first().click()
  await page.locator('[data-slot="link-open"]').first().waitFor({ timeout: 25_000 })
}

test('a link opens what it points at, over the record it is on', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openAnInvoice(page)

  await page.locator('[data-slot="link-peek"]').first().click()

  // A window, and the same `at` every other peek in the product uses — which is
  // the point: this invented no new mechanism, so the back button closes it and
  // the URL is a place. It was a drawer over the page until
  // `docs/DESKTOP.md` stage 4 made it the same window the breadcrumb opens.
  await expect(page.locator('[data-window^="record:"]')).toBeVisible({ timeout: 20_000 })
  const url = new URL(page.url())
  // Both, in one parameter and in the order they were opened: the invoice is
  // still open underneath, which is the whole difference between this button
  // and the other one — §C4.
  expect(url.searchParams.get('at')).toMatch(/^record:.+\|peek:clients\/.+$/)
  expect(url.searchParams.get('screen')).toBe('invoices')

  expectNoRealErrors(errors)
})

test('a link goes to what it points at, on its own screen', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openAnInvoice(page)

  const going = await page
    .locator('[data-slot="link-open"]')
    .first()
    .getAttribute('aria-label')

  await page.locator('[data-slot="link-open"]').first().click()

  const url = new URL(page.url())
  expect(url.searchParams.get('screen')).toBe('clients')
  // The other button: the record replaces what was open rather than sitting
  // over it, so the stack is one deep.
  expect(url.searchParams.get('at')).toMatch(/^record:.+$/)
  // The view type and any saved view are dropped on the way: they belonged to
  // the screen being left, and asking a different screen for them is asking
  // for a view that is not its.
  expect(url.searchParams.get('layout')).toBeNull()

  // The customer really is open, rather than the URL merely saying so. The
  // button named it, so the page should now be showing that name.
  const named = String(going || '').replace(/^Open /, '')
  await expect(page.getByText(named, { exact: false }).first()).toBeVisible({
    timeout: 20_000,
  })

  expectNoRealErrors(errors)
})

test('a link with nowhere to go offers nothing', async ({ page }) => {
  await openAnInvoice(page)

  // Every link on this form that has a value and a screen shows two buttons,
  // and the rest show none — so the count of buttons is never the count of
  // links. Currency, UOM and Warehouse are all on an invoice and none of them
  // is a screen in this space; a door onto a wall is worse than no door.
  // Page-wide since `docs/DESKTOP.md` stage 4: the record is the page and there
  // is no pane to scope to. The filter bar's own pickers are counted too, which
  // only makes the left-hand number bigger and the claim safer.
  const links = await page.locator('[data-slot="trigger"]').count()
  const opens = await page.locator('[data-slot="link-open"]').count()
  expect(opens).toBeLessThan(links)
  expect(opens).toBeGreaterThan(0)
})

/**
 * A window holds something you consult, never something you work in.
 *
 * The question this answers was asked the other way round: should a peeked
 * record be a whole record? It cannot be. Its Link fields would offer to peek
 * *their* targets, so a window opens over a window and the third record on
 * screen is two removes from the page's subject; its Submit and Cancel would
 * act on a document somebody opened to glance at; and edits typed into it are
 * edits in something that closes when you click past it.
 *
 * So the peek is a preview with a door — read-only, no band, no menu, one
 * control — and the door leads to the record's own screen, where all of it
 * works. `lib/screen/previewing.js`.
 */
test('a peeked record is a preview, not a second place to work', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openAnInvoice(page)

  await page.locator('[data-slot="link-peek"]').first().click()
  const peeked = page.locator('[data-window^="record:"]')
  await expect(peeked).toBeVisible({ timeout: 20_000 })

  // The fields read rather than edit — which is `canWrite`, and read-only is
  // not disabled (§B5), so a locked field is its value as text and not a greyed
  // box. Nothing to type into means nothing that can become unsaved.
  await expect(peeked.locator('[data-slot="read-value"]').first()).toBeVisible({
    timeout: 20_000,
  })
  await expect(peeked.locator('[data-slot="record-unsaved"]')).toHaveCount(0)

  // No peek inside the peek. The customer has links of its own — the invoice
  // reached it through one — and none of them opens a second window over this.
  await expect(peeked.locator('[data-slot="link-peek"]')).toHaveCount(0)

  // No menu, so nothing cancels, deletes or amends from in here; and no band,
  // so nothing submits either.
  await expect(peeked.locator('[data-slot="record-more"]')).toHaveCount(0)
  await expect(peeked.locator('[data-slot="record-band"]')).toHaveCount(0)

  // And it is the same record the page draws, not a narrower cousin: one rail,
  // grouped, rather than the doctype's own tabs nested inside Details. The
  // window is wide enough for a rail and a column of form, and `upright`
  // measures that rather than asking whether this is a window.
  await expect(peeked.locator('[data-slot="record-tabs-rail"]')).toHaveCount(1)

  expectNoRealErrors(errors)
})

test('the one control in a window is the way out of it', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openAnInvoice(page)

  await page.locator('[data-slot="link-peek"]').first().click()
  await expect(page.locator('[data-window^="record:"]')).toBeVisible({ timeout: 20_000 })

  // At the foot and in words. It was an icon on the title bar, one seat along
  // from "Fill the desk" — an arrow beside a pair of arrows, one changing the
  // size of the box and the other changing what page you are on.
  const foot = page.locator('[data-slot="preview-foot"]')
  await expect(foot).toBeVisible({ timeout: 20_000 })
  await foot.getByRole('button', { name: 'Open it properly' }).click()

  // The window is gone and the record it held is the page — the same place the
  // field's second button goes, reached from the preview instead of instead of
  // it.
  await expect(page.locator('[data-window^="record:"]')).toHaveCount(0)
  const url = new URL(page.url())
  expect(url.searchParams.get('screen')).toBe('clients')
  expect(url.searchParams.get('at')).toMatch(/^record:.+$/)

  expectNoRealErrors(errors)
})

/**
 * Several previews at once, and only one of them drawn.
 *
 * Glancing at a second thing is not a reason to forget the first, so `at`
 * stacks peeks rather than replacing them and each gets a dock tile with the
 * record's own face on it. They share one corner, so every one but the front
 * is covered to the pixel — and a mounted record nobody can see is a form, a
 * set of tabs and a presence subscription held for no reason, so the ones
 * behind are shells until they are raised.
 *
 * Built through the address rather than through two presses: the window covers
 * the form the second link would be on, and the URL is the product's own
 * record of what is open — the gesture that writes it is the one the first
 * test in this file already covers.
 */
test('two previews are two tiles, and the front one is the only one drawn', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openAnInvoice(page)
  await page.locator('[data-slot="link-peek"]').first().click()
  await expect(page.locator('[data-window^="record:"]').first())
    .toBeVisible({ timeout: 20_000 })

  // The invoice itself, peeked through its own screen: a second record to look
  // at that needs nothing known about the fixture.
  const url = new URL(page.url())
  const invoice = url.searchParams.get('at').split('|')[0].replace(/^record:/, '')
  url.searchParams.set('at', `${url.searchParams.get('at')}|peek:invoices/${invoice}`)
  await page.goto(`${url.pathname}${url.search}`)

  const tiles = page.locator('[data-window-tile^="record:"]')
  await expect(tiles).toHaveCount(2, { timeout: 25_000 })

  // One foot, because one window is drawn. The other is its title bar and
  // nothing else.
  await expect(page.locator('[data-slot="preview-foot"]')).toHaveCount(1, { timeout: 25_000 })

  // And the one drawn is the innermost, which is what the URL says — not
  // whichever of the two fetches came back first.
  const front = page.locator(`[data-window="record:invoices/${invoice}"]`)
  await expect(front.locator('[data-slot="preview-foot"]')).toBeVisible()

  expectNoRealErrors(errors)
})

test('pressing a tile swaps which preview is drawn, and the tiles stay put', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openAnInvoice(page)
  await page.locator('[data-slot="link-peek"]').first().click()
  await expect(page.locator('[data-window^="record:"]').first()).toBeVisible({ timeout: 20_000 })

  const url = new URL(page.url())
  const invoice = url.searchParams.get('at').split('|')[0].replace(/^record:/, '')
  url.searchParams.set('at', `${url.searchParams.get('at')}|peek:invoices/${invoice}`)
  await page.goto(`${url.pathname}${url.search}`)

  const tiles = page.locator('[data-window-tile^="record:"]')
  await expect(tiles).toHaveCount(2, { timeout: 25_000 })
  const order = await tiles.evaluateAll((els) => els.map((e) => e.getAttribute('data-window-tile')))

  // The one behind, brought forward. It is now the window with a foot on it.
  const behind = page.locator(`[data-window-tile="${order[0]}"]`)
  await behind.click()
  await expect(page.locator(`[data-window="${order[0]}"] [data-slot="preview-foot"]`))
    .toBeVisible({ timeout: 20_000 })
  await expect(page.locator('[data-slot="preview-foot"]')).toHaveCount(1)

  // And the row did not rearrange itself under the pointer that pressed it.
  // `desk.open` is the stack, so raising moves a window in it; the dock reads
  // the order they arrived instead.
  await expect(tiles).toHaveCount(2)
  expect(await tiles.evaluateAll((els) => els.map((e) => e.getAttribute('data-window-tile'))))
    .toEqual(order)

  expectNoRealErrors(errors)
})
