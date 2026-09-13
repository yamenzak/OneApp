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
  await expect(page).toHaveURL(/[?&]at=record:/)
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

// --- the board as an object -------------------------------------------------
//
// Frappe keeps a board's arrangement — column order, colour, archived, card
// order — on a Kanban Board doctype. Here it is a *view*: `view_settings.board
// .arrangement`, saved by the same button as the filters. Which means every
// one of these has to survive a save and a reload, and that is the half worth
// a browser.

const TASKS = '/one/space/zzmock?screen=tasks&type=board'

/** Save whatever is unsaved into this person's own default for the screen. */
const save = async (page) => {
  await page.getByRole('button', { name: 'Save this screen' }).click()
  await expect(page.getByRole('button', { name: 'Save this screen' })).toHaveCount(0, {
    timeout: 15_000,
  })
}

/**
 * Open the board with nothing archived and no column moved.
 *
 * These tests save what they do — that is half of what they are checking — so
 * one of them failing in the middle leaves a saved arrangement behind for the
 * next, and the next fails looking for a column that is not there. Rather than
 * a cleanup that only runs when the test gets that far, each starts by putting
 * the board back.
 */
const openBoard = async (page) => {
  await page.goto(TASKS)
  await page.locator(BOARD).first().waitFor({ timeout: 15_000 })

  const restore = page.locator('[data-slot^="column-restore-"]')
  const many = await restore.count()
  for (let at = 0; at < many; at += 1) await restore.first().click()
  if (many) await save(page)
}

const columnOrder = (page) =>
  page.locator(BOARD).evaluateAll((all) => all.map((one) => one.dataset.oneappColumn))

// Polled, not read once: moving a column is a Vue re-render and a one-shot
// `evaluateAll` reads the DOM before it happens about one run in five.
const expectOrder = (page, wanted) =>
  expect.poll(() => columnOrder(page), { timeout: 10_000 }).toEqual(wanted)

test('a column can be archived, and comes back', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the board is a desktop surface')
  const errors = collectConsoleErrors(page)

  await openBoard(page)
  await expect(page.locator('[data-oneapp-column="Cancelled"]')).toBeVisible()

  await page.locator('[data-oneapp-column="Cancelled"] [data-slot="column-menu"]').click()
  await page.locator('[data-slot="column-archive"]').click()

  // Gone from the board and named in the rail beside it: a column somebody
  // hid is one they can stop seeing, and a column they cannot find again is
  // one they lost.
  await expect(page.locator('[data-oneapp-column="Cancelled"]')).toHaveCount(0)
  await expect(page.locator('[data-slot="column-restore-Cancelled"]')).toBeVisible()

  await save(page)
  await page.reload()
  await page.locator(BOARD).first().waitFor({ timeout: 15_000 })
  await expect(page.locator('[data-oneapp-column="Cancelled"]')).toHaveCount(0)

  // Put it back, so the next run starts where this one did.
  await page.locator('[data-slot="column-restore-Cancelled"]').click()
  await expect(page.locator('[data-oneapp-column="Cancelled"]')).toBeVisible()
  await save(page)

  expectNoRealErrors(errors)
})

test('a column can be moved, and stays where it was put', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the board is a desktop surface')
  const errors = collectConsoleErrors(page)

  await openBoard(page)

  // Relative to whatever order the board is in rather than to a list written
  // here: this test saves what it does, so a run that dies in the middle would
  // otherwise leave the next one asserting an order nobody put it in.
  const was = await columnOrder(page)
  const [first, second] = was

  await page.locator(`[data-oneapp-column="${second}"] [data-slot="column-menu"]`).click()
  await page.getByRole('button', { name: 'Move left' }).click()
  await page.keyboard.press('Escape')
  await expectOrder(page, [second, first, ...was.slice(2)])

  await save(page)
  await page.reload()
  await page.locator(BOARD).first().waitFor({ timeout: 15_000 })
  await expectOrder(page, [second, first, ...was.slice(2)])

  await page.locator(`[data-oneapp-column="${second}"] [data-slot="column-menu"]`).click()
  await page.getByRole('button', { name: 'Move right' }).click()
  await page.keyboard.press('Escape')
  await expectOrder(page, was)
  await save(page)

  expectNoRealErrors(errors)
})

test('a card can be made at the foot of a column', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the board is a desktop surface')
  const errors = collectConsoleErrors(page)

  await openBoard(page)

  const MADE = `zzBoard quick add ${Date.now()}`
  const cancelled = page.locator('[data-oneapp-column="Cancelled"]')
  const was = await cancelled.locator('article').count()

  // A name and Enter. No dialog: the thing a board is for is moving work
  // along, and a modal with the doctype's whole form is the wrong weight for
  // "and then call the glazier".
  const box = page.locator('[data-slot="quick-add-Cancelled"]')
  await box.fill(MADE)
  await box.press('Enter')

  await expect(cancelled.locator('article')).toHaveCount(was + 1, { timeout: 15_000 })
  // And it landed in the column it was typed under, which is the whole point
  // of a foot rather than a New button somewhere else.
  await expect(cancelled.getByText(MADE)).toBeVisible()

  // Taken away again through the list, because a fixture that grows by one
  // ToDo every run is a fixture whose counts nobody can assert.
  await page.goto('/one/space/zzmock?screen=tasks&type=list')
  const row = page.locator('[data-slot="list-row"]').filter({ hasText: MADE })
  await row.first().waitFor({ timeout: 20_000 })
  await row.first().locator('[data-slot="list-row-checkbox"]').click()
  // "Delete 1", because the bar says how many — a selection is easy to lose
  // track of.
  await page.locator('[data-slot="selection-bar"]')
    .getByRole('button', { name: /^Delete/ })
    .click()
  await page.getByRole('dialog').getByRole('button', { name: 'Delete' }).click()
  await expect(page.locator('[data-slot="list-row"]').filter({ hasText: MADE }))
    .toHaveCount(0, { timeout: 20_000 })

  expectNoRealErrors(errors)
})
