// How many of each, and a way to narrow to one.
//
// Frappe's list sidebar, as a menu — this product's sidebar is the space's own
// navigation and has nowhere to put it. Two claims are worth a browser: the
// numbers add up to the list they are shown over, and clicking one narrows the
// list to exactly that many.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const COMPLIANCE = '/one/space/zzmock?screen=compliance&type=list'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the counts add up to the list they are shown over', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for a count')
  const errors = collectConsoleErrors(page)

  await page.goto(COMPLIANCE)
  const rows = page.locator('[data-slot="list-row"]')
  await rows.first().waitFor({ timeout: 20_000 })
  const total = await rows.count()

  // It opens on the screen's own status field, which is the one somebody
  // almost always means.
  await page.getByRole('button', { name: 'How many' }).click()
  const values = page.locator('[data-slot="tally-value"]')
  await expect(values.first()).toBeVisible({ timeout: 15_000 })

  const counted = (await values.allInnerTexts())
    .map((one) => Number(one.trim().split(/\s+/).pop()))
    .reduce((sum, one) => sum + one, 0)
  expect(counted).toBe(total)

  expectNoRealErrors(errors)
})

test('clicking a value narrows the list to exactly that many', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough')
  const errors = collectConsoleErrors(page)

  await page.goto(COMPLIANCE)
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })

  await page.getByRole('button', { name: 'How many' }).click()
  const first = page.locator('[data-slot="tally-value"]').first()
  await expect(first).toBeVisible({ timeout: 15_000 })
  const wanted = Number((await first.innerText()).trim().split(/\s+/).pop())
  await first.click()

  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(wanted, {
    timeout: 15_000,
  })

  // And it landed in the filter panel, where it can be seen and removed —
  // a list narrowed by something invisible is a list that looks broken.
  await expect(page.getByRole('button', { name: /^Filter/ })).toContainText('1')

  expectNoRealErrors(errors)
})
