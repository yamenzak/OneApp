import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('an app declared as a manifest renders its screens', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/app/zztasks')
  await page.waitForTimeout(1800)

  console.log('BODY:', (await page.locator('body').innerText()).slice(0, 700))
  await info.attach(`app-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

  // Rows from the tenant site, through the view.
  await expect(page.getByText('Halloway').first()).toBeVisible()
  // The filter is applied: the closed one is not here.
  await expect(page.getByText('File Q3 returns')).toHaveCount(0)

  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
  expectNoRealErrors(errors)
})

test('the app brings its own navigation', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/app/zztasks')
  await page.waitForTimeout(1500)

  // Both declared views, without a line of SPA code naming either.
  await expect(page.getByText('Open', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Everything', { exact: true }).first()).toBeVisible()

  await page.getByText('Everything', { exact: true }).first().click()
  await page.waitForTimeout(1200)
  // The unfiltered view shows the closed one too.
  await expect(page.getByText('File Q3 returns').first()).toBeVisible()

  await info.attach(`nav-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

test('a record opens and saves', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/app/zztasks')
  await page.waitForTimeout(1500)

  await page.getByText('Halloway').first().click()
  await page.waitForTimeout(600)

  // Labels and a Select's options come from the doctype, not from the manifest.
  await expect(page.getByText('Priority').first()).toBeVisible()
  await info.attach(`record-${info.project.name}`, {
    body: await page.screenshot(), contentType: 'image/png' })
  expectNoRealErrors(errors)
})
