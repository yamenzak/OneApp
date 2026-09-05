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

test('a link opens what it points at, beside the record it is on', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openAnInvoice(page)

  await page.locator('[data-slot="link-peek"]').first().click()

  // The drawer, and the same two query parameters every other peek in the
  // product uses — which is the point: this invented no new mechanism, so the
  // back button closes it and the URL is a place.
  await expect(page.locator('[data-slot="record-drawer"]')).toBeVisible({ timeout: 20_000 })
  const url = new URL(page.url())
  expect(url.searchParams.get('peek')).toBeTruthy()
  expect(url.searchParams.get('peekScreen')).toBe('clients')
  // And the record it was on is still behind it, which is the whole difference
  // between this button and the other one.
  expect(url.searchParams.get('screen')).toBe('invoices')
  expect(url.searchParams.get('record')).toBeTruthy()

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
  expect(url.searchParams.get('record')).toBeTruthy()
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
  const links = await page.locator('[data-slot="record-pane"] [data-slot="trigger"]').count()
  const opens = await page.locator('[data-slot="link-open"]').count()
  expect(opens).toBeLessThan(links)
  expect(opens).toBeGreaterThan(0)
})
