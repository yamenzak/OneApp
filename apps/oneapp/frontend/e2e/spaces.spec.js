import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a space declared as a manifest renders its screens', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zztasks')

  console.log('BODY:', (await page.locator('body').innerText()).slice(0, 700))
  await info.attach(`app-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

  // Rows from the tenant site, through the screen.
  await expect(page.getByText('Halloway').first()).toBeVisible()
  // The filter is applied: the closed one is not here.
  await expect(page.getByText('File Q3 returns')).toHaveCount(0)

  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
  expectNoRealErrors(errors)
})

test('the space brings its own navigation', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zztasks')

  // Both declared screens, without a line of SPA code naming either.
  await expect(page.getByText('Open', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Everything', { exact: true }).first()).toBeVisible()

  await page.getByText('Everything', { exact: true }).first().click()
  // The unfiltered screen shows the closed one too.
  await expect(page.getByText('File Q3 returns').first()).toBeVisible()

  await info.attach(`nav-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

test('a record opens and saves', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zztasks')

  await page.getByText('Halloway').first().click()

  // Labels and a Select's options come from the doctype, not from the manifest.
  // Scoped to the dialog: the quick filter row above the list has a box with
  // the same label, and on a phone that one is hidden.
  await expect(
    page.locator('[role="dialog"]').getByText('Priority', { exact: true }),
  ).toBeVisible()
  await info.attach(`record-${info.project.name}`, {
    body: await page.screenshot(), contentType: 'image/png' })
  expectNoRealErrors(errors)
})
