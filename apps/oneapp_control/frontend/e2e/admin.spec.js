import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the console renders its chrome and navigation', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/admin/setup')

  // The header is teleported into the shell's target, so an empty bar means the
  // teleport never happened — which looks like a styling problem and is not.
  await expect(page.getByRole('banner').or(page.locator('[data-slot*="page-header"]')).first())
    .toBeVisible()

  await expect(page.getByText('Provisioning is disabled')).toBeVisible()

  // Every readiness item, not just the group counts. The counts came from the
  // same array as the rows and were right while the list rendered nothing.
  await expect(page.getByText('Frappe Cloud API')).toBeVisible()
  await expect(page.getByText('Control plane URL')).toBeVisible()

  await info.attach('setup', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

test('settings opens and shows a panel', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/admin/setup')

  await page.getByRole('button', { name: /open settings/i }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  // The nav must be beside the panel, not inside its scroll area.
  // The nav must sit beside the panel, not inside its scroll area.
  await expect(dialog.getByText('Storage buckets')).toBeVisible()
  // And the opened panel must actually render its fields.
  await expect(dialog.getByText('API key')).toBeVisible()

  await info.attach('settings', { body: await page.screenshot(), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

for (const [name, path] of Object.entries({
  tenants: '/admin/tenants',
  jobs: '/admin/jobs',
  shards: '/admin/shards',
})) {
  test(`${name} renders rows or a real empty state`, async ({ page }, info) => {
    const errors = collectConsoleErrors(page)
    await page.goto(path)
    await page.waitForLoadState('networkidle')

    // Either data or an empty state. A blank panel is the failure mode here:
    // it is what every list did while looking merely uneventful.
    // Either data or an empty state; a blank panel is the failure this catches.
    const rows = page.locator('[data-slot="list-row"]')
    const empty = page.locator('text=/no [a-z]|nothing here/i').first()
    await expect(rows.first().or(empty).first()).toBeVisible()

    await info.attach(name, { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
    expectNoRealErrors(errors)
  })
}
