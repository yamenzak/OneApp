// The two link doors, pressed from inside the create dialog.
//
// Both were broken there and each for its own reason. The peek drawer was a
// `fixed z-50` inside the page and frappe-ui's Dialog is a `z-50` portalled to
// `body`, so the record you asked to read opened *behind* the dialog asking
// for it. And "open it" navigated without closing the dialog, which then sat
// over the screen it had been left for, still holding a form for the doctype
// it used to be filling in — and refused to save.
//
// So: a peek from a dialog covers the dialog, and going somewhere closes it.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const DIALOG = '[data-oneapp="form-dialog"]'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/**
 * A create dialog with a Link that has both a value and somewhere to go.
 *
 * An invoice's `customer` is the fixture's reliable pair — RUA shows Customer
 * on its Clients screen — and it is the same one `link-open.spec.js` leans on
 * for the saved-record half of this feature.
 */
async function newInvoiceWithACustomer(page) {
  await page.goto('/one/space/rua?screen=invoices')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')

  const button = page.getByRole('button', { name: 'New', exact: true }).first()
  await button.waitFor({ timeout: 25_000 })
  await button.click()
  const dialog = page.locator(DIALOG)
  await expect(dialog).toBeVisible()

  // Named with its own "(required)", the way the form draws it — `Customer`
  // on its own also matches Customer Name in Arabic.
  const customer = dialog.getByRole('combobox', { name: 'Customer (required)' })
  await expect(customer).toBeVisible({ timeout: 15_000 })
  await customer.click()
  await page.waitForTimeout(500)
  const option = page.locator('[role="option"]:visible').first()
  if (!(await option.count())) test.skip(true, 'no customer to pick on this site')
  await option.click()

  await page.locator('[data-slot="link-peek"]').first().waitFor({ timeout: 15_000 })
  return dialog
}

test('a link peeked from the create dialog opens over it, not under it', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  const dialog = await newInvoiceWithACustomer(page)

  await page.locator('[data-slot="link-peek"]').first().click()

  const drawer = page.locator('[data-slot="record-drawer"]')
  await expect(drawer).toBeVisible({ timeout: 20_000 })
  // The dialog is still there — peeking costs nothing and abandons nothing.
  await expect(dialog).toBeVisible()

  // Over it, which is the whole bug: whoever mounted last is on top, and the
  // drawer mounted last. Asked of the browser rather than of the stylesheet,
  // because the answer came from DOM order and not from a z-index.
  const onTop = await page.evaluate(() => {
    const box = document.querySelector('[data-slot="record-drawer"] .bg-surface-elevation-2')
    const r = box.getBoundingClientRect()
    const hit = document.elementFromPoint(r.x + r.width / 2, r.y + 40)
    return !!hit && !!hit.closest('[data-slot="record-drawer"]')
  })
  expect(onTop, 'the peeked record is behind the dialog that asked for it').toBe(true)

  expectNoRealErrors(errors)
})

test('going to a link from the create dialog closes the dialog', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  const dialog = await newInvoiceWithACustomer(page)

  // And says so first: the button that throws away a half-filled record reads
  // differently from the one that costs nothing.
  const label = await page.locator('[data-slot="link-open"]').first().getAttribute('aria-label')
  expect(label).toContain('Discard')

  await page.locator('[data-slot="link-open"]').first().click()

  await expect(dialog).toBeHidden({ timeout: 10_000 })
  const url = new URL(page.url())
  expect(url.searchParams.get('screen')).toBe('clients')
  expect(url.searchParams.get('record')).toBeTruthy()

  expectNoRealErrors(errors)
})
