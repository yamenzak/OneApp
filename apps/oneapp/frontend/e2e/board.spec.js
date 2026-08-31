// The board: the same rows as the list, drawn as columns of a status.
//
// Everything here is real — a real screen over ToDo, whose `status` Select is
// what the columns are, and a real save when a card moves. A board that draws
// its columns from a hard-coded list is a board that goes wrong the first time
// somebody edits the doctype, which is exactly what these check it does not do.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const BOARD = '[data-oneapp-column]'
const CARD = '[data-oneapp-column] article'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a board draws one column per option of the status field', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock?screen=tasks&type=board')

  const columns = page.locator(BOARD)
  await columns.first().waitFor({ timeout: 15_000 })

  // ToDo's own Select, in the doctype's own order. Not a list typed in here:
  // asserting the values proves the board read the field rather than guessed.
  await expect(columns).toHaveCount(3)
  for (const value of ['Open', 'Closed', 'Cancelled']) {
    await expect(page.locator(`[data-oneapp-column="${value}"]`)).toBeVisible()
  }

  // And the rows are in them. The fixture's tasks are Open.
  await expect(page.locator('[data-oneapp-column="Open"] article').first()).toBeVisible()
  expectNoRealErrors(errors)
})

test('the sidebar offers the board only where a screen names a status', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the phone has no sidebar')
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  // Tasks names `status`, so the board is one of the ways to see it. The
  // screen that is open is already expanded, so there is nothing to click.
  await expect(
    page.locator('a[href*="screen=tasks"][href*="type=board"]'),
  ).toBeVisible()

  // Notes names none. A board over it would be a single column called
  // everything, which is a list drawn badly — so it is not offered at all,
  // and expanding the screen does not produce one either.
  const expand = page.getByRole('button', { name: 'Ways to see Notes' })
  if (await expand.count()) await expand.click()
  await expect(page.locator('a[href*="screen=notes"][href*="type=board"]')).toHaveCount(0)
})

test('a card opens its record', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  await page.goto('/one/space/zzmock?screen=tasks&type=board')
  await page.locator(CARD).first().waitFor({ timeout: 15_000 })

  await page.locator(CARD).first().click()
  await expect(page).toHaveURL(/[?&]record=/)
  await expect(page.locator('[data-slot="record-pane"]')).toBeVisible()
})

test('New inside a column opens the form with that column filled in', async ({ page }) => {
  await page.goto('/one/space/zzmock?screen=tasks&type=board')
  await page.locator(BOARD).first().waitFor({ timeout: 15_000 })

  await page
    .locator('[data-oneapp-column="Cancelled"]')
    .getByRole('button', { name: 'New in Cancelled' })
    .click()

  const dialog = page.locator('[data-oneapp="form-dialog"]')
  await expect(dialog).toBeVisible()
  // Pressing New inside a column means "a new one, here" — not "a new one, and
  // now go and find the status you just pressed".
  await expect(dialog.getByRole('combobox', { name: 'Status' })).toContainText(
    'Cancelled',
  )
})

test('moving a card writes the field the columns are', async ({ page }, info) => {
  // HTML5 drag and drop is a pointer gesture and a touch screen has none, so
  // there is nothing to drive here. A phone changes a status by opening the
  // record, which is what it does for every other field.
  test.skip(info.project.name === 'mobile', 'a touch screen cannot drag')
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock?screen=tasks&type=board')
  await page.locator(CARD).first().waitFor({ timeout: 15_000 })

  // A card by name, so this says something about one record rather than about
  // whichever one happened to sort first.
  const open = page.locator('[data-oneapp-column="Open"] article', {
    hasText: 'Book the van for Thursday',
  })
  await expect(open).toBeVisible()

  await open.dragTo(page.locator('[data-oneapp-column="Cancelled"]'))

  // In the new column, and gone from the old one — the board re-reads the
  // list after a save rather than trusting where the card was dropped.
  await expect(
    page.locator('[data-oneapp-column="Cancelled"] article', {
      hasText: 'Book the van for Thursday',
    }),
  ).toBeVisible()
  await expect(open).toHaveCount(0)

  // And it is the record that changed, not the board: a reload reads it back
  // from the server.
  await page.reload()
  await expect(
    page.locator('[data-oneapp-column="Cancelled"] article', {
      hasText: 'Book the van for Thursday',
    }),
  ).toBeVisible({ timeout: 15_000 })

  // Put the fixture back. Every other spec reads this task as Open.
  await page
    .locator('[data-oneapp-column="Cancelled"] article', {
      hasText: 'Book the van for Thursday',
    })
    .dragTo(page.locator('[data-oneapp-column="Open"]'))
  await expect(open).toBeVisible()
  expectNoRealErrors(errors)
})
