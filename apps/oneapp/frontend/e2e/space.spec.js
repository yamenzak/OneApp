import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the launcher renders', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/')

  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  console.log(`${info.project.name}: overflow=${overflow}`)
  console.log('BODY:', (await page.locator('body').innerText()).slice(0, 800))

  await info.attach(`launcher-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expect(overflow).toBeLessThanOrEqual(1)
  expectNoRealErrors(errors)
})
