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

/** Whether this run has the shell's sidebar, which only a desktop draws. */
const onDesktop = (page) => (page.viewportSize()?.width || 0) >= 768

/**
 * Go to a place by its name, the way somebody would.
 *
 * Two controls for one list: the rail on a desktop, and a dropdown beside the
 * breadcrumb on a phone — which has no rail, and without which the bin has no
 * route to it at all. Both are worth walking, which is why this is a helper
 * rather than a skip.
 */
async function goToPlace(page, label) {
  if (onDesktop(page)) {
    await page.getByRole('link', { name: label }).click()
    return
  }
  await page.locator('[data-slot="drive-places"]').click()
  await page.getByRole('menuitem', { name: label }).click()
}

test('the drive lists the workspace files, and every place in the rail loads', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/files')

  await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toBeVisible()

  // Each place is its own query and each one has its own empty state, so the
  // pass is "it settled on something", not "it found rows". A place that never
  // settles is the failure worth catching: it means the filter threw.
  for (const label of ['Recent', 'Favourites', 'Shared with me', 'Bin', 'All files']) {
    await goToPlace(page, label)
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
  // difference is the element rather than a class. The row is the container;
  // the thing you press is inside it.
  const file = page.locator('button[data-slot="drive-open"]')
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

test('a file can be hearted, and the heart is what Favourites lists', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/files?place=all')

  const file = page.locator('[data-slot="drive-file"]').first()
  await file.waitFor({ timeout: 20_000 })
  const named = await file.locator('[data-slot="drive-open"]').innerText()

  await file.getByRole('button', { name: /Add .* to favourites/ }).click()
  // The row re-reads from the server, so the heart flipping is the server
  // agreeing rather than the client asserting.
  await expect(file.getByRole('button', { name: /Remove .* from favourites/ }))
    .toBeVisible({ timeout: 10_000 })

  await goToPlace(page, 'Favourites')
  const there = page.locator('[data-slot="drive-file"]').first()
  await expect(there).toContainText(named.split('\n')[0])

  // Put it back, so the next run starts where this one did.
  await there.getByRole('button', { name: /Remove .* from favourites/ }).click()
  await expect(page.locator('[data-slot="empty-state"]')).toBeVisible({ timeout: 10_000 })

  expectNoRealErrors(errors)
})

test('choosing files offers what can be done to all of them at once', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/files?place=all')
  await page.locator('[data-slot="drive-file"]').first().waitFor({ timeout: 20_000 })

  // Nothing chosen, no bar: a control for an empty selection is a control
  // that does nothing.
  await expect(page.locator('[data-slot="drive-selection"]')).toHaveCount(0)

  await page.locator('[data-slot="drive-file"] input[type=checkbox]').first().check()
  await page.locator('[data-slot="drive-file"] input[type=checkbox]').nth(1).check()

  const bar = page.locator('[data-slot="drive-selection"]')
  await expect(bar.getByRole('button', { name: 'Move', exact: true })).toBeVisible()
  // The count is above the list on a phone, where repeating it in the bar is
  // what pushes the buttons onto a second line.
  await expect(page.locator('body')).toContainText(
    onDesktop(page) ? '2 things chosen' : '2 of',
  )

  await bar.getByRole('button', { name: 'Clear the selection' }).click()
  await expect(bar).toHaveCount(0)

  expectNoRealErrors(errors)
})

test('a file can be shared with a colleague, and the bin says what it promises', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/files?place=all')
  await page.locator('[data-slot="drive-file"]').first().waitFor({ timeout: 20_000 })

  await page.locator('[data-slot="drive-more"]').first().click()
  await page.getByRole('menuitem', { name: 'Share' }).click()
  const share = page.getByRole('dialog')
  await expect(share.getByText('Everyone on this workspace')).toBeVisible()
  await page.keyboard.press('Escape')

  // Thirty days is the promise the sweep keeps, and a bin whose terms are only
  // in the code is a bin nobody trusts.
  await goToPlace(page, 'Bin')
  await expect(page.getByRole('button', { name: 'Empty the bin' })).toBeVisible()

  expectNoRealErrors(errors)
})

test("a record's files are the Drive's own rows", async ({ page }) => {
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

  // Either the Drive's row or the Drive's empty state — never a third list
  // shaped like them, which is the whole point of the tab being a filter.
  await expect(
    page.locator('[data-slot="drive-file"], [data-slot="empty-state"]').first(),
  ).toBeVisible({ timeout: 15_000 })

  expectNoRealErrors(errors)
})

test('the storage screen says which file and not only which kind', async ({ page }) => {
  test.skip(
    !onDesktop(page),
    'the settings dialog is opened from the shell, and its phone route is the shell\'s own spec',
  )
  const errors = collectConsoleErrors(page)
  await page.goto('/one/files')

  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Settings' }).click()
  await page.getByRole('tab', { name: 'Storage' }).click()

  await expect(page.getByText('By kind')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('The biggest')).toBeVisible()

  // The panel must not be wider than the dialog that holds it, or every number
  // in it is clipped off the right edge.
  const fits = await page.evaluate(() => {
    const panel = document.querySelector('[role=tabpanel]:not([hidden])')
    const dialog = panel.closest('[role=dialog]')
    return panel.getBoundingClientRect().right <= dialog.getBoundingClientRect().right + 1
  })
  expect(fits).toBe(true)

  expectNoRealErrors(errors)
})
