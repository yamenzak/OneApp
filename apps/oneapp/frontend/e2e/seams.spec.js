// Where the sheet and the document editor meet the rest of the product.
//
// Each of these is one control on a surface that already existed, and each one
// is the difference between "the workspace has a spreadsheet" and "the
// workspace prices a quotation in one". They are together because they are one
// idea said five times: the editors are not a place you go, they are what the
// thing you are already looking at opens into.
import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, nameInUrl, signIn } from './auth.js'

const EVENT = 'Quarterly review'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/**
 * The fixture's Event, open, on the tab asked for.
 *
 * `.last()` because the record's own tab strip is nested inside the pane's and
 * both have a Details — the inner one is the doctype's.
 */
async function openEvent(page, tab) {
  await page.goto('/one/space/zzmock?screen=events&type=list')
  const row = page.locator('[data-slot="list-row"]').filter({ hasText: EVENT })
  await row.first().waitFor({ timeout: 15_000 })
  await row.first().locator('[data-slot="list-cell"]').nth(1).click()
  const chosen = page.getByRole('tab', { name: tab }).last()
  await chosen.waitFor({ timeout: 15_000 })
  await chosen.click()
  return page.getByRole('tabpanel', { name: tab }).last()
}

test('a child table opens in a sheet, headings and all', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  const errors = collectConsoleErrors(page)
  const panel = await openEvent(page, 'Notifications')

  // By slot, not by name: every row in the grid also has an "Open this row",
  // and this button says only where it goes.
  await panel.locator('[data-slot="open-in-sheet"]').click()

  // In a dialog, over the record — not on a page of its own. Pricing a child
  // table is something you do *while looking at the record*, and the route
  // change this replaced took the record away.
  const held = page.locator('[data-slot="sheet-dialog"]')
  await held.waitFor({ timeout: 30_000 })
  await expect(page.locator('.sn-toolbar')).toBeVisible()
  // Still there behind it. By slot rather than by role: a modal takes the rest
  // of the page out of the accessibility tree, which is the whole point of a
  // modal and would make `getByRole` answer "gone" about a record that is not.
  await expect(page.locator('[data-slot="object-pane"]')).toBeAttached()

  // Which sheet, from the dialog rather than from a URL there no longer is.
  const name = await held.getAttribute('data-sheet')
  expect(name).toBeTruthy()

  // The contract the pull reads: a named range drawn round the block, starting
  // at row one so the headings are inside it. Nobody typed either.
  const res = await page.request.get(
    `/api/method/oneapp.onesheet.named_ranges?sheet=${name}`,
  )
  expect(res.ok()).toBe(true)
  const [range] = (await res.json()).message
  expect(range.ref).toMatch(/^A1:/)

  // And the same range reads back the three notification rows it came from.
  const seen = await page.request.get(
    `/api/method/oneapp.onesheet.preview?sheet=${name}&label=${range.label}`,
  )
  expect(seen.ok()).toBe(true)
  const preview = (await seen.json()).message
  expect(preview.rows).toHaveLength(3)

  expectNoRealErrors(errors)
})

test('a long-text field opens in the document editor', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  const errors = collectConsoleErrors(page)
  await openEvent(page, 'Details')

  const details = page.getByRole('tabpanel', { name: 'Details' }).last()
  await details.locator('[data-slot="open-in-doc"]').first().click()

  const dialog = page.getByRole('dialog').filter({ hasText: 'Description' })
  await dialog.locator('.ProseMirror').first().click()
  await page.keyboard.type('A room the field itself does not have.')
  await dialog.getByRole('button', { name: 'Save' }).click()

  // Back into the field, not off into a file: this text is part of the record
  // and part of what its print format renders.
  await expect(page.getByText('A room the field itself does not have.').first()).toBeVisible()
  expectNoRealErrors(errors)
})

test("a record's Files tab makes a document of its own", async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  const errors = collectConsoleErrors(page)
  const panel = await openEvent(page, 'Files')

  await panel.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Document', exact: true }).click()
  await page.waitForURL(/\/one\/docs\//, { timeout: 30_000 })

  const name = nameInUrl(page, '/one/docs/')
  const res = await page.request.get(
    `/api/method/oneapp.onedoc.get_doc?name=${name}`,
  )
  expect(res.ok()).toBe(true)

  // Attached to the record rather than filed in a folder — which is what makes
  // "the project's scope of works" a query rather than a feature.
  expect((await res.json()).message.attached_to.doctype).toBe('Event')

  expectNoRealErrors(errors)
})

test('a document marked as a template is one the editor offers to load', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  const title = `Scope of works ${Date.now()}`

  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Document', exact: true }).click()
  await page.waitForURL(/\/one\/docs\//, { timeout: 30_000 })
  await expect(page.locator('.ProseMirror').first()).toBeVisible()

  await page.getByRole('button', { name: 'What to do with this document' }).click()
  await page.getByRole('menuitem', { name: 'Rename' }).click()
  const renaming = page.getByRole('dialog').filter({ hasText: 'Rename' })
  await renaming.getByRole('textbox', { name: 'Name' }).fill(title)
  await renaming.getByRole('button', { name: 'Rename' }).click()

  await page.getByRole('button', { name: 'What to do with this document' }).click()
  await page.getByRole('menuitem', { name: 'Use as a template' }).click()

  // The flag is the whole feature, and where it is read is the editor rather
  // than the Drive's New menu: New is a menu of *kinds*, and the moment you
  // want a template is the moment you are looking at a blank page.
  await page.getByRole('button', { name: 'What to do with this document' }).click()
  await page.getByRole('menuitem', { name: 'Load a template' }).click()
  await expect(page.locator('[data-slot="template-row"]', { hasText: title })).toBeVisible()

  expectNoRealErrors(errors)
})

test('a code field opens in OneCode, and what is saved there is the field', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  const errors = collectConsoleErrors(page)

  // A letter head, because it is the fixture's one `Code` field on a screen —
  // and that screen exists for this test. See `seed_dev_space.LETTERHEAD`.
  await page.goto('/one/space/zzmock?screen=letterheads&type=list')
  const row = page.locator('[data-slot="list-row"]').filter({ hasText: 'zzMock House Style' })
  await row.first().waitFor({ timeout: 15_000 })
  await row.first().locator('[data-slot="list-cell"]').nth(1).click()

  // Beside the field rather than in a menu: eight lines of a form is not enough
  // room for markup, and the way out of that should be where the problem is.
  const opener = page.locator('[data-slot="open-in-code"]').first()
  await opener.waitFor({ timeout: 15_000 })
  await opener.click()

  const dialog = page.getByRole('dialog').filter({ hasText: 'Header HTML' })
  await expect(dialog).toBeVisible()

  // The field's own value, coloured as the field's own language: `Letter Head`
  // stores HTML, and the tag names are what CodeMirror had to be told about.
  await expect(dialog.locator('.cm-content')).toContainText('zzMock Contracting LLC')

  await dialog.locator('.cm-content').click()
  await page.keyboard.press('ControlOrMeta+End')
  await page.keyboard.type('<!-- edited in OneCode -->')
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(dialog).toBeHidden()

  // Back into the field, not into a file. That is the whole design: a letter
  // head's markup is part of the letter head.
  await expect(page.locator('.cm-content').first()).toContainText('edited in OneCode')
  expectNoRealErrors(errors)
})
