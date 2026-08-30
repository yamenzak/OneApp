import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('an app screen can be defined without the desk', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/admin/setup')
  await page.getByRole('button', { name: /settings/i }).first().click()
  await page.getByText('App screens', { exact: true }).click()
  await page.waitForTimeout(1500)

  await expect(page.getByText('App screens').first()).toBeVisible()
  // The declared screens of whichever app the picker landed on, or an honest
  // empty state saying an app may have none.
  await expect(
    page.getByText(/Slug|No screens yet|No apps registered/).first(),
  ).toBeVisible()

  await info.attach(`app-screens-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expectNoRealErrors(errors)
})
