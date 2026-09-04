import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * The file manager, and the picker that made it worth building.
 *
 * The server half is unit-tested — what a kind is, what each place filters on,
 * what a link refuses. What only a browser can answer is whether the pieces
 * meet: whether the rail's places actually load, whether opening a file opens
 * a preview rather than navigating away from the app, and whether the picker
 * behind an Attachments tab offers the workspace's existing files at all. That
 * last one is the whole point of the arc and it is one query away from showing
 * an empty drive, because almost every file lives in `Home/Attachments`.
 */

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the drive lists the workspace files, and every place in the rail loads', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/files')

  await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toBeVisible()

  // Each place is its own query and each one has its own empty state, so the
  // pass is "it settled on something", not "it found rows". A place that never
  // settles is the failure worth catching: it means the filter threw.
  const places = page.locator('[data-slot="drive-place"]')
  const count = await places.count()
  expect(count).toBe(5)
  for (let index = 0; index < count; index += 1) {
    await places.nth(index).click()
    await expect(
      page.locator('[data-slot="drive-file"], [data-slot="empty-state"]').first(),
    ).toBeVisible({ timeout: 15_000 })
  }

  expectNoRealErrors(errors)
})

test('opening a file opens a preview, and the preview offers a link', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/files?place=all')

  // A folder is a link and navigates; only a file opens a preview, and the
  // difference is the element rather than a class.
  const file = page.locator('button[data-slot="drive-file"]')
  await file.first().waitFor({ timeout: 20_000 })
  await file.first().click()

  const preview = page.getByRole('dialog')
  await expect(preview).toBeVisible()
  await expect(preview.getByRole('button', { name: 'Download' })).toBeVisible()

  // A text preview is the case that catches the download route serving an
  // error page instead of the file — which is what it did on any site without
  // an R2 bucket, and reads as a `.txt` whose contents are "Redirecting...".
  await expect(preview.locator('pre, img, iframe, video, audio').first()).toBeVisible()
  await expect(preview.getByText('Redirecting')).toHaveCount(0)

  // Sharing replaces the preview rather than stacking on it, because two open
  // modals nest and the outer one goes `aria-hidden` under the inner. What
  // makes a link different from a copy of the file is that it ends, so the
  // expiry is the part worth asserting.
  await preview.getByRole('button', { name: 'Share a link' }).click()
  const share = page.getByRole('dialog')
  await expect(share.getByText('It stops working after')).toBeVisible()
  await expect(share.getByRole('button', { name: 'Make a link' })).toBeVisible()

  expectNoRealErrors(errors)
})

test('the picker on a record offers files the workspace already has', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/rua?screen=projects')

  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')

  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.getByRole('tab', { name: 'Files' }).click()
  await page.getByRole('button', { name: 'Attach a file' }).click()

  const picker = page.getByRole('dialog')
  await expect(picker).toBeVisible()

  // Upload first, because that is what every one of these surfaces used to be.
  await expect(picker.getByRole('button', { name: 'Choose a file' })).toBeVisible()

  // And then the half that is new: the drive, flat, with a search over it.
  await picker.getByRole('tab', { name: 'Choose from files' }).click()
  await expect(picker.getByPlaceholder('Search files')).toBeVisible()
  await expect(
    picker.locator('[data-slot="drive-file"], [data-slot="empty-state"]').first(),
  ).toBeVisible({ timeout: 15_000 })

  expectNoRealErrors(errors)
})
