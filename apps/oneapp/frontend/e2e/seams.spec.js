// Where the sheet and the document editor meet the rest of the product.
//
// Each of these is one control on a surface that already existed, and each one
// is the difference between "the workspace has a spreadsheet" and "the
// workspace prices a quotation in one". They are together because they are one
// idea said four times: the editors are not a place you go, they are what the
// thing you are already looking at opens into.
import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

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

  await panel.getByRole('button', { name: 'Open in a sheet' }).click()
  await page.waitForURL(/\/one\/sheets\//, { timeout: 30_000 })

  const name = page.url().split('/one/sheets/')[1]

  // The contract the pull reads: a named range drawn round the block, starting
  // at row one so the headings are inside it. Nobody typed either.
  const res = await page.request.get(
    `/api/method/oneapp.oneapp_core.sheets.named_ranges?sheet=${name}`,
  )
  expect(res.ok()).toBe(true)
  const [range] = (await res.json()).message
  expect(range.ref).toMatch(/^A1:/)

  // And the same range reads back the three notification rows it came from.
  const seen = await page.request.get(
    `/api/method/oneapp.oneapp_core.sheets.preview?sheet=${name}&label=${range.label}`,
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
  await details.getByRole('button', { name: 'Open in the editor' }).first().click()

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

  const name = page.url().split('/one/docs/')[1]
  const res = await page.request.get(
    `/api/method/oneapp.oneapp_core.docs.get_doc?name=${name}`,
  )
  expect(res.ok()).toBe(true)

  // Attached to the record rather than filed in a folder — which is what makes
  // "the project's scope of works" a query rather than a feature.
  expect((await res.json()).message.attached_to.doctype).toBe('Event')

  expectNoRealErrors(errors)
})

test('a document marked as a template is one the New menu offers', async ({ page }) => {
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

  // The flag is the whole feature: the Drive's New menu is the template list.
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await expect(page.getByRole('menuitem', { name: title })).toBeVisible()

  expectNoRealErrors(errors)
})
