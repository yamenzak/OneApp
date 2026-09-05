// The RUA space: eleven screens over ERPNext, HRMS and our own two registers.
//
// Nothing here is a doctype anybody has to maintain — that is the whole point
// of the move. What is bespoke is the vocabulary: they say LPO and not Purchase
// Order, and a screen calling it the other thing is one they translate every
// time they read it.
//
// Skipped where the tenant has no ERPNext, which is what the dev seed does with
// the space itself: nine of the eleven screens would be over doctypes that are
// not there.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

async function open(page, screen) {
  await page.goto(`/one/space/rua?screen=${screen}`)
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')
}

test('the rail calls things what they are called on site', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the rail is a sheet on a phone')
  const errors = collectConsoleErrors(page)

  await open(page, 'projects')

  // Their word, not ERPNext's. A Purchase Order is an LPO to every person in
  // this company, and the screen is for the people.
  const rail = page.locator('nav, aside').first()
  await expect(rail.getByText('LPOs', { exact: true })).toBeVisible()
  await expect(rail.getByText('Clients', { exact: true })).toBeVisible()
  await expect(rail.getByText('Team', { exact: true })).toBeVisible()

  expectNoRealErrors(errors)
})

test('a project leads with the stage their sales team uses', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for a column set')
  const errors = collectConsoleErrors(page)

  await open(page, 'projects')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  // `custom_stage` and not `status`: Tender and Job in Hand are both Open to a
  // project ledger and a world apart to the people selling.
  const said = await page.locator('[data-slot="list-row"]').allInnerTexts()
  expect(said.join(' ')).toMatch(/Tender|Job in Hand|In Progress|Completed/)

  expectNoRealErrors(errors)
})

test('money reads as money', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the total is off a phone')
  const errors = collectConsoleErrors(page)

  await open(page, 'invoices')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })

  // Two decimals, from the site's number format. It used to read the *float*
  // precision when no currency precision was set, which is not a fallback
  // Frappe makes — and every contract value in the product came out with a
  // thousandth of a dirham on the end.
  const said = await page.locator('[data-slot="list-row"]').first().innerText()
  expect(said).toMatch(/\d,\d{3}\.\d{2}(\D|$)/)
  expect(said).not.toMatch(/\.\d{3}(\D|$)/)

  expectNoRealErrors(errors)
})
