import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors } from './auth.js'

// Deliberately no `signIn`. This is the one surface in the product that a Guest
// has to be able to load — everything else is a Space behind a session — and
// the failure mode worth catching is that it stops being open to one.

test('signup loads for somebody with no session', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/signup/')

  await expect(page.getByRole('heading', { name: 'Create your workspace' })).toBeVisible()
  await expect(page.getByLabel('Workspace name')).toBeVisible()

  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  console.log(`${info.project.name}: overflow=${overflow}`)

  await info.attach(`signup-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expect(overflow).toBeLessThanOrEqual(1)
  expectNoRealErrors(errors)
})

test('an unknown path under the bundle comes back to signup', async ({ page }) => {
  // `/admin` and `/portal` were served from here and are gone. Whoever follows
  // an old link was on their way to an account either way.
  await page.goto('/signup/admin')
  await expect(page).toHaveURL(/\/signup\/?$/)
})
