// What the doctype's author wrote between the fields, and the three verbs the
// desk has always had.
//
// A Heading and an HTML block are layout fields: they carry no value, so they
// are never columns — and for that reason the record form dropped them, which
// meant a form arrived without the annotations its author added to make it
// readable. Duplicate, Copy link and Reload were the other half of the same
// gap: three things a person expects of a record and had to work around.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const COMPLIANCE = '/one/space/zzmock?screen=compliance'

const openFirst = async (page) => {
  await page.goto(COMPLIANCE)
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 20_000 })
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a heading and an html block the doctype wrote are on the form', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openFirst(page)

  await expect(page.locator('[data-slot="form-heading"]', { hasText: 'Before it lapses' }))
    .toBeVisible()

  // Sanitised on the way in, and still markup: the bold word has to survive,
  // or the sanitiser is stripping the thing it was added to keep.
  const note = page.locator('[data-slot="form-html"]').first()
  await expect(note).toContainText('once')
  await expect(note.locator('b')).toHaveText('following')

  expectNoRealErrors(errors)
})

test('the record menu offers duplicate, copy link and reload', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the menu is the same; the pane is not')
  const errors = collectConsoleErrors(page)
  await openFirst(page)

  await page.locator('[data-slot="record-more"]').click()
  await expect(page.getByRole('menuitem', { name: 'Duplicate' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Copy link' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: 'Reload' })).toBeVisible()

  expectNoRealErrors(errors)
})

test('duplicating opens a draft holding what the record held', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the menu is the same; the pane is not')
  const errors = collectConsoleErrors(page)
  await openFirst(page)

  const title = await page.getByRole('textbox', { name: 'Title' }).inputValue()

  await page.locator('[data-slot="record-more"]').click()
  await page.getByRole('menuitem', { name: 'Duplicate' }).click()

  // A dialog, not a second record: nothing has been written, and closing it
  // leaves nothing behind. That is Frappe's own Duplicate and it is the honest
  // shape — a copy is a draft somebody is about to change.
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('textbox', { name: 'Title' })).toHaveValue(title)

  await page.keyboard.press('Escape')
  expectNoRealErrors(errors)
})
