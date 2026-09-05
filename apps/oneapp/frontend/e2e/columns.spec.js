// Which edge a column's values sit against, and the header with them.
//
// The fourth thing a column carries, beside where it sits, which edge it
// sticks to and how wide it is — and the first that is about the *values*
// rather than the table. Two claims are worth a browser: the header follows
// the cells, and the choice survives being saved into a view.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const APPROVALS = '/one/space/zzmock?screen=approvals&type=list'

/** Open the column dialog and set one column's alignment. */
const align = async (page, label, choice) => {
  await page.getByRole('button', { name: 'Choose columns' }).click()
  const row = page
    .locator('[data-slot="column-row"]')
    .filter({ hasText: label })
    .first()
  // A radio, not a button: `TabButtons` is a radio group, which is the right
  // role for one answer out of a few and is why it was reached for here.
  await row.getByRole('radio', { name: choice }).click()
  await page.getByRole('button', { name: 'Done' }).click()
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a column can be aligned, and its header goes with it', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the column dialog is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto(APPROVALS)
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })

  // Amount is a Currency, so it starts against the end without anybody saying
  // so — that is the automatic answer the fieldtype gives.
  const header = page.getByRole('columnheader', { name: 'Amount' })
  await expect(header).toHaveClass(/justify-end/)

  // Moved to the centre, the header moves with it. A right-aligned column
  // under a left-aligned heading reads as two columns.
  await align(page, 'Amount', 'Align to the centre')
  await expect(header).toHaveClass(/justify-center/)
  const cell = page
    .locator('[data-slot="list-row"]')
    .first()
    .locator('[data-slot="list-cell"]')
    // Title, Amount, State, Activity — the checkbox is not a cell.
    .nth(1)
  await expect(cell).toHaveClass(/justify-center/)

  // And back to automatic, which is not the same as "start": the fieldtype
  // decides again and a Currency goes back to the end.
  await align(page, 'Amount', 'Automatic')
  await expect(header).toHaveClass(/justify-end/)

  expectNoRealErrors(errors)
})

test('an alignment saved into a view is there on the next visit', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the column dialog is a desktop surface')
  const errors = collectConsoleErrors(page)

  await page.goto(APPROVALS)
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })

  await align(page, 'Title', 'Align to the end')
  const header = page.getByRole('columnheader', { name: 'Title' })
  await expect(header).toHaveClass(/justify-end/)

  // Into this person's own default for the screen, which is where an unsaved
  // change goes when they are not in a named view.
  await page.getByRole('button', { name: 'Save this screen' }).click()
  await expect(page.getByRole('button', { name: 'Save this screen' })).toHaveCount(0, {
    timeout: 15_000,
  })

  await page.reload()
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 20_000 })
  await expect(page.getByRole('columnheader', { name: 'Title' })).toHaveClass(/justify-end/)

  // Put it back, so the next run starts where this one did.
  await align(page, 'Title', 'Automatic')
  await page.getByRole('button', { name: 'Save this screen' }).click()
  await expect(page.getByRole('button', { name: 'Save this screen' })).toHaveCount(0, {
    timeout: 15_000,
  })

  expectNoRealErrors(errors)
})
