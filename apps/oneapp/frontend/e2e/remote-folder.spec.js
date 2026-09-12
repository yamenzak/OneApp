// A folder on somebody else's server, in the rail and in the list.
//
// The fixture's mount is Paused and points at a host that does not exist,
// which is deliberate: a browser suite that needed a live FTP server would be
// a suite that fails on anybody's laptop. What can be asserted without one is
// everything this feature added to the Drive — the rail entry, the way in,
// the read-only chrome, the way to make another, and that a mount which
// cannot answer says so rather than looking empty.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a connected folder is in the rail, under a heading of its own', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the rail is a desktop sidebar')
  const errors = collectConsoleErrors(page)

  await page.goto('/one/files')
  await expect(page.locator('[data-slot="drive-mounts-heading"]')).toHaveText('Connected')

  const mount = page.locator('[data-slot="drive-mount"]', { hasText: 'zzVDV drop' })
  await expect(mount).toBeVisible()

  // Below the places, not among them. A mount is a socket and a place is a
  // `where` on one table, and the heading is what says so.
  const places = await page.locator('[data-slot="drive-place"]').count()
  expect(places).toBeGreaterThan(4)

  expectNoRealErrors(errors)
})

test('a mount that cannot answer says so, and is not an empty folder', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the rail is a desktop sidebar')

  await page.goto('/one/files')
  await page.locator('[data-slot="drive-mount"]', { hasText: 'zzVDV drop' }).click()
  await page.waitForURL(/folder=remote/)

  // The fixture's mount is paused, so the read is refused before a socket is
  // opened. Either way the reader gets the server's own sentence — the thing
  // that stops "the feed is broken" being a Monday-morning discovery.
  await expect(page.getByText('Your files did not load')).toBeVisible({ timeout: 20_000 })

  // And nothing that writes. There is no row on a host to rename, bin or
  // upload into, and the Drive offers none of it.
  await expect(page.getByRole('button', { name: 'Upload', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Check again' })).toBeVisible()
})

// No console-error assertion on this one: it deliberately connects to a
// closed port, and the refusal it is checking for arrives as a failed request
// that the resource layer logs. An assertion that no error was logged would be
// an assertion that the thing under test did not happen.
test('another folder can be connected from the New menu', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the New menu is the desktop header')

  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Connect a folder' }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Connect a folder')).toBeVisible()
  // The port is a placeholder rather than a value: a blank one means the
  // protocol's own, and pre-filling 22 makes SFTP's default look like a
  // choice somebody made.
  // `exact`, because "Name" is inside "Username" and "Host" inside "Folder on
  // the host" — a substring match here is a strict-mode violation, not a
  // wrong field.
  await expect(dialog.getByLabel('Port', { exact: true })).toHaveAttribute('placeholder', '22')

  // A host that is not there is refused in the host's own words, and no mount
  // is left behind — which is the whole of why this dialog exists.
  await dialog.getByLabel('Name', { exact: true }).fill('zzNowhere')
  await dialog.getByLabel('Host', { exact: true }).fill('127.0.0.1')
  await dialog.getByLabel('Port', { exact: true }).fill('1')
  await dialog.getByRole('button', { name: 'Connect' }).click()
  await expect(dialog.getByText('That did not connect')).toBeVisible({ timeout: 30_000 })

  await page.reload()
  await expect(page.locator('[data-slot="drive-mount"]', { hasText: 'zzNowhere' })).toHaveCount(0)
})
