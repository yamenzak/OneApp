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

  // Narrowed to the fixture's own pictures rather than "whatever is newest".
  // A sheet is a file too and it does not preview — it opens its grid — so
  // "the first row in All files" stopped being a file with bytes the moment
  // Sheets landed.
  await page.getByPlaceholder('Search files').fill('zzmock')
  // The search is debounced, so the list on screen is still the unfiltered one
  // for a moment — and clicking its first row is clicking whatever was newest.
  await expect(page.locator('[data-slot="drive-file"]').first()).toContainText('zzmock')

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

  // Opening it is what makes it recent, so Recents has something in it now.
  // Nothing called the endpoint that stamps this, so the rail's second place
  // was empty on every site and looked like a place nobody used.
  await page.keyboard.press('Escape')
  await goToPlace(page, 'Recent')
  await expect(page.locator('[data-slot="drive-file"]').first()).toBeVisible({
    timeout: 15_000,
  })

  // Back to the preview, for the rest of what it offers.
  await page.goBack()
  await file.first().click()

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

test('a link made here is a link a stranger can follow', async ({ page, browser }) => {
  test.skip(!onDesktop(page), 'one viewport is enough: this is a server path, not a layout')

  const errors = collectConsoleErrors(page)
  await page.goto('/one/files?place=all')

  // The fixture's own pictures, for the same reason as the preview test above:
  // a sheet is a file and clicking one opens its grid rather than a dialog.
  await page.getByPlaceholder('Search files').fill('zzmock')
  await expect(page.locator('[data-slot="drive-file"]').first()).toContainText('zzmock')

  const file = page.locator('button[data-slot="drive-open"]')
  await file.first().waitFor({ timeout: 20_000 })
  await file.first().click()
  await page.getByRole('dialog').getByRole('button', { name: 'Share a link' }).click()

  // Links this file already has, from earlier runs. The dialog draws them
  // before the new one exists, so waiting for "a row" would read whichever was
  // already on screen — and reading a revoked one is a 403 that looks like a
  // broken guest route rather than a racing test.
  const rows = page.locator('[data-slot="file-link"]')
  const before = await rows.count()
  await page.getByRole('button', { name: 'Make a link' }).click()
  await expect(rows).toHaveCount(before + 1, { timeout: 15_000 })

  const made = rows.first()
  const url = (await made.locator('p').first().innerText()).trim()
  expect(url).toContain('open_link?secret=')

  // A context with no cookies, because the whole claim is that the secret is
  // the authentication. Following it while signed in would prove nothing —
  // and this path answered 500 to everybody for as long as it existed.
  const stranger = await browser.newContext()
  try {
    const answer = await stranger.request.get(url)
    expect(answer.status()).toBe(200)
    expect((await answer.body()).length).toBeGreaterThan(0)
  } finally {
    await stranger.close()
  }

  // Revoking re-reads the list, so this is also where the count shows up —
  // the row on screen was drawn before the stranger followed anything, and a
  // dialog nobody reloaded is correctly stale.
  await page.getByRole('button', { name: 'Stop this link working' }).first().click()
  await expect(made).toContainText('Revoked', { timeout: 15_000 })
  // Counted, which is the reason a revoked link is kept rather than deleted.
  await expect(made).toContainText('opened 1 time')

  const after = await browser.newContext()
  try {
    expect((await after.request.get(url)).status()).not.toBe(200)
  } finally {
    await after.close()
  }

  expectNoRealErrors(errors)
})

/**
 * Getting files in, which until now there was no control for.
 *
 * The empty state has always said "Upload a file or make a folder to start"
 * beside a toolbar that offered only the folder: the only ways a file could
 * reach a workspace were a record's attach field and the picker's upload tab,
 * both of which put it somewhere else. So the thing under test is not the
 * uploader — it is Frappe's — but that the Drive now has a way in at all, and
 * that four files dropped at once report themselves rather than vanishing into
 * a spinner.
 */
test('files chosen from the toolbar upload, and the tray says what happened', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/files')
  await expect(page.locator('[data-slot="drive-dropzone"]')).toBeVisible()

  const stamp = Date.now()
  await page.locator('input[name="drive-upload"]').setInputFiles([
    { name: `probe-${stamp}-a.txt`, mimeType: 'text/plain', buffer: Buffer.from('a') },
    { name: `probe-${stamp}-b.txt`, mimeType: 'text/plain', buffer: Buffer.from('b') },
  ])

  const tray = page.locator('[data-slot="upload-tray"]')
  await expect(tray).toBeVisible()
  await expect(tray).toContainText(`probe-${stamp}-a.txt`)
  // One at a time and in order, which is why the second is still queued while
  // the first is on the wire.
  await expect(tray).toContainText('2 files uploaded', { timeout: 30_000 })

  // And they are in the workspace, not only in the tray.
  await page.getByPlaceholder('Search files').fill(`probe-${stamp}`)
  await expect(page.locator('[data-slot="drive-file"]')).toHaveCount(2, { timeout: 20_000 })

  expectNoRealErrors(errors)
})

test('dropping files on the list uploads them into the folder you are in', async ({
  page,
}) => {
  await page.goto('/one/files')
  const zone = page.locator('[data-slot="drive-dropzone"]')
  await expect(zone).toBeVisible()

  const stamp = Date.now()
  // A real `DataTransfer` with a real `File` on it. `setInputFiles` exercises
  // the button; only this exercises the drop, and the drop is the half that
  // has its own event plumbing to get wrong.
  await zone.dispatchEvent('drop', {
    dataTransfer: await page.evaluateHandle((name) => {
      const data = new DataTransfer()
      data.items.add(new File(['dropped'], name, { type: 'text/plain' }))
      return data
    }, `dropped-${stamp}.txt`),
  })

  await expect(page.locator('[data-slot="upload-tray"]'))
    .toContainText('1 file uploaded', { timeout: 30_000 })
  await page.getByPlaceholder('Search files').fill(`dropped-${stamp}`)
  await expect(page.locator('[data-slot="drive-file"]').first())
    .toContainText(`dropped-${stamp}.txt`, { timeout: 20_000 })
})

/**
 * The direct path, on a bench with no bucket.
 *
 * The interesting half — presigned PUTs at Cloudflare — cannot run here and is
 * covered by `tests/test_direct_upload.py`. What can only be checked in a
 * browser is that the wiring is *live*: that a file over the threshold asks
 * `direct.begin` before anything else, that a file under it does not ask at
 * all, and that a site answering `{"direct": false}` still lands the file. Each
 * of those is silent at build time and each of them has a failure that looks
 * exactly like the old behaviour.
 */
test('a large file asks for a direct upload first, and falls back when there is no bucket', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page)
  const asked = []
  page.on('request', (request) => {
    const url = request.url()
    if (url.includes('storage.direct.')) asked.push(url.split('storage.direct.')[1].split('?')[0])
  })

  await page.goto('/one/files')
  await expect(page.locator('[data-slot="drive-dropzone"]')).toBeVisible()

  const stamp = Date.now()
  // Over the 8 MB threshold, which is the only thing that decides the path.
  await page.locator('input[name="drive-upload"]').setInputFiles([
    {
      name: `big-${stamp}.bin`,
      mimeType: 'application/octet-stream',
      buffer: Buffer.alloc(9 * 1024 * 1024, 7),
    },
  ])

  await expect(page.locator('[data-slot="upload-tray"]'))
    .toContainText('1 file uploaded', { timeout: 60_000 })

  expect(asked).toEqual(['begin'])

  await page.getByPlaceholder('Search files').fill(`big-${stamp}`)
  await expect(page.locator('[data-slot="drive-file"]').first())
    .toContainText(`big-${stamp}.bin`, { timeout: 20_000 })

  // And a small one never asks — three round trips to save a second is not a
  // saving, and every ordinary upload has to keep costing what it cost.
  asked.length = 0
  await page.locator('input[name="drive-upload"]').setInputFiles([
    { name: `small-${stamp}.txt`, mimeType: 'text/plain', buffer: Buffer.from('small') },
  ])
  await expect(page.locator('[data-slot="upload-tray"]'))
    .toContainText('uploaded', { timeout: 30_000 })
  expect(asked).toEqual([])

  expectNoRealErrors(errors)
})

test('right-clicking a row offers what its menu offers', async ({ page }) => {
  await page.goto('/one/files')
  const row = page.locator('[data-slot="drive-file"]').first()
  await row.waitFor({ timeout: 20_000 })

  // One menu for the whole list, filled by whichever row was right-clicked —
  // so the check that matters is that it is filled at all, and with this row's
  // actions rather than an empty array.
  await row.click({ button: 'right' })
  await expect(page.getByRole('menuitem', { name: 'Rename' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Move to the bin' })).toBeVisible()
})

test('a file dragged onto a folder ends up inside it', async ({ page }) => {
  const stamp = Date.now()
  const folder = `Landing ${stamp}`

  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New folder' }).click()
  await page.getByRole('textbox', { name: 'Name' }).fill(folder)
  await page.getByRole('button', { name: 'Make it', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await page.locator('input[name="drive-upload"]').setInputFiles([
    { name: `mover-${stamp}.txt`, mimeType: 'text/plain', buffer: Buffer.from('m') },
  ])
  await expect(page.locator('[data-slot="upload-tray"]'))
    .toContainText('1 file uploaded', { timeout: 30_000 })

  // Both rows on screen at once, which a search for the shared stamp gives.
  await page.getByPlaceholder('Search files').fill(String(stamp))
  const file = page.locator('[data-slot="drive-file"]').filter({ hasText: `mover-${stamp}.txt` })
  const target = page.locator('[data-slot="drive-file"]').filter({ hasText: folder })
  await expect(file).toHaveCount(1, { timeout: 20_000 })
  await expect(target).toHaveCount(1)

  await file.dragTo(target)

  // The proof is inside the folder, not the row disappearing from this list —
  // a filtered list drops rows for several reasons and only one of them is a
  // move that worked.
  await target.locator('[data-slot="drive-open"]').click()
  await expect(page.locator('[data-slot="drive-file"]').first())
    .toContainText(`mover-${stamp}.txt`, { timeout: 20_000 })
})
