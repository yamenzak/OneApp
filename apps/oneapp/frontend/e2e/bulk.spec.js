// One change, applied to a selection.
//
// The claim worth a browser is that each record is saved on its own and what
// could not take the change comes back named — the fixture's approvals include
// a submitted one, so a bulk change over all of them is exactly the partial
// failure this is built to report rather than swallow.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const APPROVALS = '/one/space/zzmock?screen=approvals&type=list'
// The compliance register for the happy path: eight plain records, nothing
// submittable, so a change over two of them is a change two of them can take.
// The approvals are the fixture's docstatus fixture and exactly one of them is
// a draft — which is what makes them the right screen for the refusal below.
const COMPLIANCE = '/one/space/zzmock?screen=compliance&type=list'

const rowFor = (page, title) =>
  page.locator('[data-slot="list-row"]').filter({ hasText: title })

/** Tick one row by the title in it. */
const tick = (page, title) =>
  rowFor(page, title).first().locator('[data-slot="list-row-checkbox"]').click()

/**
 * Open the bulk-edit dialog on the current selection and set one field.
 *
 * frappe-ui's `Select` is a combobox button rather than a native `<select>`, so
 * the field is chosen by opening it and clicking the option.
 */
const bulkSet = async (page, label, value, box = 'input[type=text]') => {
  await page.locator('[data-slot="selection-bar"]')
    .getByRole('button', { name: 'Edit', exact: true })
    .click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('combobox').click()
  await page.getByRole('option', { name: label, exact: true }).click()
  await dialog.locator(box).fill(value)
  await dialog.getByRole('button', { name: 'Change them' }).click()
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('one change reaches every record that was ticked', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the row checkboxes are a desktop affordance')
  const errors = collectConsoleErrors(page)

  await page.goto(COMPLIANCE)
  await rowFor(page, 'Trade Licence — 2024').first().waitFor({ timeout: 20_000 })

  await tick(page, 'Trade Licence — 2024')
  await tick(page, 'Memorandum of Association')
  const bar = page.locator('[data-slot="selection-bar"]')
  await expect(bar).toContainText('2 selected')

  // Which field, then what to — the whole dialog, and the same `FieldControl`
  // the record form draws, so a Data field is a text box here too.
  const stamp = `ZZ Registrar ${Date.now()}`
  await bulkSet(page, 'Issued By', stamp)
  await expect(page.locator('[data-slot="selection-bar"]')).toHaveCount(0, {
    timeout: 20_000,
  })

  // Both took it, and it came back from the server: the list re-reads after a
  // bulk change, and `Issued by` is not one of the columns this screen shows,
  // so the only way to see it is to open a record.
  for (const title of ['Trade Licence — 2024', 'Memorandum of Association']) {
    await page.goto(COMPLIANCE)
    await rowFor(page, title).first().locator('[data-slot="list-cell"]').nth(1).click()
    await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 15_000 })
    await expect(page.locator(`input[value="${stamp}"]`).first()).toBeVisible({
      timeout: 15_000,
    })
  }

  expectNoRealErrors(errors)
})

test('a record that refuses the change is named, not swallowed', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the row checkboxes are a desktop affordance')
  const errors = collectConsoleErrors(page)

  await page.goto(APPROVALS)
  await rowFor(page, 'Office chairs').first().waitFor({ timeout: 20_000 })

  // Office chairs is approved, which on this fixture's workflow is a docstatus
  // of 1 — Frappe refuses a change to `amount` after submission. A bulk change
  // that silently skipped it would be worse than one that failed, so the record
  // is named and the ones that took it still took it.
  await tick(page, 'Office chairs')
  await bulkSet(page, 'Amount', '4242', 'input[type=number]')

  await expect(page.getByText(/ZZA-\d+/).first()).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText(/after submission/i).first()).toBeVisible()

  // And it is unchanged.
  await page.reload()
  await expect(rowFor(page, 'Office chairs').first()).toContainText('1,200.00', {
    timeout: 20_000,
  })

  expectNoRealErrors(errors)
})
