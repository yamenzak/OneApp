// Getting from the Drive to an editor, now that an editor is a window.
//
// Every one of these specs used to press New and wait for the address to
// become `/one/docs/<id>` or `/one/sheets/<id>`, because that is what the
// Drive did: it navigated. `docs/DESKTOP.md` stage 6 changed that — a document
// and a workbook open in a window over whatever you were reading, and the page
// underneath stays where it was, which is the whole point of a window and the
// reason five spec files stopped being able to find their own editor.
//
// Both surfaces are still real and both are still tested. The window is what a
// person gets from the Drive; the page at `/one/docs/<id>` is what a pasted
// link opens, and it is the one these files were written against — a reload, a
// second browser, a share link and a print all go through it. So this lands in
// the window, reads the id off it, and then opens the page: one helper, and
// every test below it keeps asserting what it was written to assert.
import { expect } from '@playwright/test'

/** The id of the file whose window is open, from `lib/editing.js`'s own key. */
export async function openFileId(page) {
  const window = page.locator('[data-window^="file:"]').first()
  await expect(window).toBeVisible({ timeout: 30_000 })
  const said = await window.getAttribute('data-window')
  return (said || '').replace(/^file:/, '')
}

/**
 * Press New in the Drive, choose something, and land on its editor page.
 *
 * `choose` is run after the menu item is clicked, for the two kinds that ask a
 * second question — Code asks which language.
 */
export async function newFromDrive(page, item, { route = 'docs', choose = null } = {}) {
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: item, exact: true }).click()
  if (choose) await choose()

  const id = await openFileId(page)
  await page.goto(`/one/${route}/${id}`)
  return id
}
