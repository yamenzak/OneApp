import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * The grid, in a browser.
 *
 * The engine and the renderer are Frappe's and come with their own suite —
 * nine hundred and thirty-one unit tests, four seconds, `yarn test`. None of
 * that says whether a person can type into this thing *here*: whether the
 * Drive can get you to a sheet at all, whether a keystroke reaches the canvas,
 * whether what was typed survives a reload (the only proof the save actually
 * reached our server), and whether a named range still fills a record.
 *
 * **The grid is a canvas.** There are no cells in the DOM to select, click or
 * read, so this file drives the way a person does — click a pixel, press keys —
 * and reads back through the three places the editor puts state into the DOM:
 * the active-cell chip, the formula bar, and the selection's Count/Sum/Avg. A
 * computed value is asserted through Sum, which is the only number on screen
 * that a headless browser can read.
 *
 * A sheet is made by the test rather than seeded, because a test that shares a
 * fixture with another test is a test that fails when the other one is edited.
 */

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

// The canvas's own geometry, from `lib/sheets/canvas/constants.js`. Stated here
// rather than imported so a change there fails this loudly instead of silently
// moving every click one column left.
const ROW_HEADER_W = 50
const COL_HEADER_H = 24
const COL_W = 100
const ROW_H = 24

const grid = (page) => page.locator('canvas').first()
/** The active cell, as the chip beside the formula bar says it. */
const active = (page) => page.locator('.sn-cell-ref')
const formulaBar = (page) => page.locator('input[name="formula-bar"]')
// The two icon-only menus, by their own class. They carry a tooltip and no
// accessible name — that is a rule this repository keeps and Frappe's editor
// does not, and editing four thousand lines of theirs to satisfy it is what
// vendoring exists to avoid (`tests/vendored.py`).
const moreMenu = (page) => page.locator('.sn-tool-more button')
const addTab = (page) => page.locator('.sn-tab-add')
const fileMenu = (page) =>
  page.locator('.sn-topbar-right').getByRole('button', { name: 'File' })

/**
 * What a cell came to, read back off the server.
 *
 * A canvas has no text to assert against, and the status bar sums what was
 * *typed* rather than what it came to — so `=A1*A2` contributes nothing to it.
 * This asks the question that actually matters anyway: the browser computed
 * something, and the server has it.
 *
 * Polled, not read once. The save is debounced, and "Saved" in the header is
 * true of the *previous* save until the next one starts — so a read taken the
 * moment it appears is a read of the state before the edit.
 */
async function computed(page, id, ref) {
  const res = await page.request.get(
    `/api/method/oneapp.oneapp_core.sheets.read_range?sheet=${id}&tab=Sheet1&ref=${ref}`,
  )
  expect(res.ok()).toBe(true)
  return (await res.json()).message.values[0][0]
}

/** `computed`, until it says what it should or the clock runs out. */
function expectComputed(page, id, ref) {
  return expect.poll(() => computed(page, id, ref), { timeout: 20_000 })
}

/** `"B3"` → the pixel at the middle of that cell. Unscrolled sheets only. */
function at(ref) {
  const [, letters, digits] = ref.match(/^([A-Z]+)(\d+)$/)
  let col = 0
  for (const ch of letters) col = col * 26 + (ch.charCodeAt(0) - 64)
  return {
    x: ROW_HEADER_W + (col - 1) * COL_W + COL_W / 2,
    y: COL_HEADER_H + (Number(digits) - 1) * ROW_H + ROW_H / 2,
  }
}

/** Put the selection on a cell, and prove it landed. */
async function select(page, ref) {
  await grid(page).click({ position: at(ref) })
  await expect(active(page)).toHaveText(ref)
}

/** Type into a cell the way a person does: click it, type, press Enter. */
async function type(page, ref, text) {
  await select(page, ref)
  await page.keyboard.type(text)
  await page.keyboard.press('Enter')
}

/**
 * Make an empty sheet from the Drive and land in it. Returns its id.
 *
 * Two clicks, not one: New sheet is a menu, because a workspace with an
 * estimator template starts from it far more often than from a blank grid.
 *
 * Waits for the toolbar *and* the canvas: the toolbar mounts before the grid
 * instance is wired, and a keystroke sent in that window goes nowhere.
 */
async function newSheet(page) {
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New sheet' }).click()
  await page.getByRole('menuitem', { name: 'Blank sheet' }).click()
  await page.waitForURL(/\/one\/sheets\//)
  await ready(page)
  await expect(active(page)).toHaveText('A1')
  return page.url().split('/one/sheets/')[1]
}

/**
 * The grid is drawn *and* the workbook is in it.
 *
 * The canvas exists before `get_sheet` resolves, and the active-cell chip says
 * C2 the instant you click it whether or not C2's contents have arrived — so
 * without this a read of the formula bar right after a reload reads an empty
 * one and calls it a lost edit. The editor's own loading overlay is the signal
 * it already publishes.
 */
async function ready(page) {
  await expect(page.locator('.sn-toolbar')).toBeVisible({ timeout: 30_000 })
  await expect(grid(page)).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.sn-canvas-loading')).toHaveCount(0, { timeout: 30_000 })
}

/** Rename through the title field in the editor's own bar. */
async function rename(page, title) {
  const field = page.locator('input[name="sheet-title"]')
  await field.fill(title)
  await field.blur()
}

/** Name a rectangle, through the dialog the More menu opens. */
async function nameRange(page, label, ref) {
  await moreMenu(page).click()
  await page.getByRole('menuitem', { name: 'Named ranges…' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name').fill(label)
  await dialog.getByLabel('Range').fill(ref)
  await dialog.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(dialog).toContainText(label)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
}

/**
 * The header says the save landed.
 *
 * Only ever a *second* check. "Saved" is true of the previous save until the
 * next one starts, so on its own it says nothing about the edit just made —
 * `expectComputed` polling the server is what proves that, and this is what
 * proves the editor agrees. The chip is absent entirely on a sheet nobody has
 * touched, so don't call this where nothing was typed.
 */
async function saved(page) {
  await expect(page.locator('.sn-save-status')).toContainText('Saved', { timeout: 30_000 })
}

/**
 * Open the fixture Event and land on its Participants tab.
 *
 * The tab is clicked and then *waited for*, because the record's spec arrives
 * after the first render and `RecordForm` sends the strip back to its first tab
 * when it does — so a click that lands in that window is quietly undone.
 */
async function openParticipants(page) {
  await page.goto('/one/space/zzmock?screen=events')
  const row = page.locator('[data-slot="list-row"]').filter({ hasText: 'Quarterly review' })
  await row.first().waitFor({ timeout: 20_000 })
  await row.first().locator('[data-slot="list-cell"]').nth(1).click()

  const tab = page.getByRole('tab', { name: 'Participants' })
  await tab.waitFor({ timeout: 20_000 })
  await expect(async () => {
    await tab.click()
    await expect(page.getByRole('tabpanel', { name: 'Participants' })).toBeVisible({ timeout: 2000 })
  }).toPass({ timeout: 20_000 })
}

/** The two-column sheet the read-back tests fill an Event's participants from. */
async function attendeeSheet(page, title) {
  const id = await newSheet(page)
  await rename(page, title)

  await type(page, 'A1', 'Reference Document Type')
  await type(page, 'B1', 'Reference Docname')
  await type(page, 'A2', 'User')
  await type(page, 'B2', 'Administrator')

  await nameRange(page, 'Attendees', 'A1:B2')
  await saved(page)
  return id
}

test('a sheet in the file list opens its grid rather than a preview', async ({ page }) => {
  // The one thing about a sheet that is not like every other file: it has no
  // bytes to look at, so clicking it navigates instead of opening the preview
  // dialog every other row opens.
  const id = await newSheet(page)
  await page.goto('/one/files?place=all')
  await page.getByPlaceholder('Search files').fill('Untitled sheet')
  // The search is debounced; without this the click lands on whatever row the
  // unfiltered list had first.
  await expect(page.locator('[data-slot="drive-file"]').first())
    .toContainText('Untitled sheet')
  const row = page.locator('button[data-slot="drive-open"]').first()
  await row.waitFor({ timeout: 20_000 })
  await row.click()

  await page.waitForURL(/\/one\/sheets\//)
  await expect(grid(page)).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(id).toBeTruthy()
})

test('a sheet is made from the Drive and opens on an empty grid', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await newSheet(page)

  await expect(page.locator('.sn-toolbar')).toBeVisible()
  await expect(page.locator('.sn-tabs-track')).toContainText('Sheet1')
  await expect(formulaBar(page)).toHaveValue('')

  expectNoRealErrors(errors)
})

test('typing into a cell puts a value in it, and a formula reads it back', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page)
  const id = await newSheet(page)

  await type(page, 'A1', '6')
  await type(page, 'A2', '7')
  await type(page, 'A3', '=A1*A2')
  await saved(page)
  await expectComputed(page, id, 'A3').toBe('42')

  // The point of the whole engine: changing what a formula reads changes the
  // formula, without anybody touching the formula.
  await type(page, 'A1', '10')
  await saved(page)
  await expectComputed(page, id, 'A3').toBe('70')

  expectNoRealErrors(errors)
})

test('the formula bar shows the formula, and the cell shows the number', async ({
  page,
}) => {
  const id = await newSheet(page)
  await type(page, 'B1', '4')
  await type(page, 'B2', '=B1+1')
  await saved(page)

  await select(page, 'B2')
  await expect(formulaBar(page)).toHaveValue('=B1+1')
  await expectComputed(page, id, 'B2').toBe('5')
})

test('what was typed is still there after a reload', async ({ page }) => {
  const id = await newSheet(page)
  await type(page, 'C1', '3')
  await type(page, 'C2', '=C1*3')
  // Polled, so the reload cannot beat the save it is meant to be testing.
  await expectComputed(page, id, 'C2').toBe('9')
  await saved(page)

  await page.goto(`/one/sheets/${id}`)
  await ready(page)
  await select(page, 'C2')
  await expect(formulaBar(page)).toHaveValue('=C1*3')
  await expectComputed(page, id, 'C2').toBe('9')
})

test('an unknown function says so the way Excel does', async ({ page }) => {
  const id = await newSheet(page)
  await type(page, 'A1', '=NOSUCHFUNCTION(1)')
  await saved(page)
  await expectComputed(page, id, 'A1').toBe('#NAME?')
})

test('a formula that reads itself is caught rather than hanging the grid', async ({
  page,
}) => {
  const id = await newSheet(page)
  await type(page, 'A1', '=A1+1')
  // Two proofs, and the second is the one that matters: the cell says it is a
  // cycle, and the page is still answering at all — one that was not caught
  // would have taken the tab with it.
  await saved(page)
  await expectComputed(page, id, 'A1').toContain('CIRCULAR')
  await select(page, 'B1')
  await expect(active(page)).toHaveText('B1')
})

test('arrow keys move the selection and the formula bar follows', async ({ page }) => {
  await newSheet(page)
  await type(page, 'B2', 'here')
  await select(page, 'A1')
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowDown')
  await expect(active(page)).toHaveText('B2')
  await expect(formulaBar(page)).toHaveValue('here')
})

test('a tab is added and the grid switches to it', async ({ page }) => {
  await newSheet(page)
  await type(page, 'A1', 'first tab')

  await addTab(page).click()
  await expect(page.locator('.sn-tabs-track')).toContainText('Sheet2')
  // The new tab is empty, which is the thing worth checking: a tab that showed
  // the first tab's cells would be one table pretending to be two.
  await select(page, 'A1')
  await expect(formulaBar(page)).toHaveValue('')
})

test('a range can be named, and the name is offered back', async ({ page }) => {
  await newSheet(page)
  await type(page, 'A1', 'Item')
  await type(page, 'B1', 'Rate')
  await nameRange(page, 'LineItems', 'A1:B1')

  // A named range is workbook state, so the proof it stuck is that it comes
  // back — reopened from the same dialog, after a save and a reload.
  await saved(page)
  await page.reload()
  await expect(page.locator('.sn-toolbar')).toBeVisible({ timeout: 30_000 })
  await moreMenu(page).click()
  await page.getByRole('menuitem', { name: 'Named ranges…' }).click()
  await expect(page.getByRole('dialog')).toContainText('LineItems')
})

/**
 * The stage the whole of Sheets exists for: a named range fills a document.
 *
 * Written against Frappe's Event, whose participants table is the one core
 * child table with a required column in it — so a mapping that half worked
 * would throw rather than quietly write blanks. The sheet is typed rather than
 * seeded, because the point is that a person can do this without anybody
 * having declared anything in advance.
 */
test('a named range fills a record\'s child table', async ({ page }) => {
  const title = `Attendees ${Date.now()}`
  await attendeeSheet(page, title)

  await openParticipants(page)

  await page.getByRole('tabpanel', { name: 'Participants' })
    .getByRole('button', { name: /^Fill/ }).click()

  // frappe-ui's Select is reka-ui's, not a native `<select>` — a combobox that
  // opens a listbox. `selectOption` throws on one.
  await page.getByLabel('Sheet', { exact: true }).click()
  await page.getByRole('option', { name: title, exact: true }).click()
  await page.getByLabel('Named range').click()
  await page.getByRole('option', { name: 'Attendees — Sheet1!A1:B2', exact: true }).click()

  // The preview is the confirmation: what it shows is what the pull writes,
  // because both run the same code on the server.
  await expect(page.getByRole('dialog')).toContainText('1 row, from Sheet1!A1:B2')
  await page.getByRole('button', { name: 'Replace these rows with 1' }).click()

  await expect(page.getByRole('dialog')).toHaveCount(0)

  // The pull writes through the server, so the record is refetched — which
  // sends the form back to its first tab. Coming back to Participants is also
  // the stronger check: what is asserted is the row that landed, not a count
  // beside it.
  await openParticipants(page)
  // By the row rather than by text: what landed is the *value* of a Link
  // control, and a combobox's value is not text content for `hasText` to find.
  await expect(page.getByRole('row', { name: /Administrator/ }).first())
    .toBeVisible({ timeout: 15_000 })
})

/**
 * A template is a sheet with a flag on it, and starting from one copies its
 * workbook. What is worth checking in a browser is the loop rather than the
 * copy: marking one, finding it in the New sheet menu, and landing in a grid
 * that already has the template's cells in it.
 */
test('a sheet can be made a template, and a new sheet starts from it', async ({ page }) => {
  const title = `Estimator ${Date.now()}`

  await newSheet(page)
  await rename(page, title)
  await type(page, 'A1', 'Rate card')
  await type(page, 'B1', '250')
  await saved(page)

  await fileMenu(page).click()
  await page.getByRole('menuitem', { name: 'Use as a template' }).click()

  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New sheet' }).click()
  await page.getByRole('menuitem', { name: title, exact: true }).click()

  await page.waitForURL(/\/one\/sheets\//)
  await ready(page)
  await select(page, 'A1')
  await expect(formulaBar(page)).toHaveValue('Rate card')
  await select(page, 'B1')
  await expect(formulaBar(page)).toHaveValue('250')
})

/**
 * Excel, both ways, as one round trip.
 *
 * No committed `.xlsx` fixture: the test exports one and imports what it
 * exported, which checks both halves against each other and cannot drift from
 * a binary nobody can read in a diff. What it is really asking is whether a
 * formula survives — a spreadsheet that exports numbers and imports numbers is
 * a CSV with more steps. Both halves are ExcelJS here rather than SheetJS; see
 * `lib/sheets/xlsx-file.js`.
 */
test('a sheet exports to Excel and comes back with its formulas', async ({ page }) => {
  await newSheet(page)
  await type(page, 'A1', 'Rate')
  await type(page, 'A2', '120')
  await type(page, 'B2', '=A2*3')
  await saved(page)

  const coming = page.waitForEvent('download')
  await fileMenu(page).click()
  await page.getByRole('menuitem', { name: 'Export as XLSX' }).click()
  const download = await coming
  const path = await download.path()
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/)

  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New sheet' }).click()
  await page.getByRole('menuitem', { name: 'Import a spreadsheet' }).click()
  await page.locator('input[type="file"]').setInputFiles({
    name: download.suggestedFilename(),
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: readFileSync(path),
  })

  await page.waitForURL(/\/one\/sheets\//, { timeout: 60_000 })
  await ready(page)
  const imported = page.url().split('/one/sheets/')[1]
  await select(page, 'A2')
  await expect(formulaBar(page)).toHaveValue('120')

  // The formula, not the number it came to. This is the whole point.
  await select(page, 'B2')
  await expect(formulaBar(page)).toHaveValue('=A2*3')
  // No `saved` here: the import wrote the whole workbook before it navigated,
  // so there is nothing pending and the chip never appears.
  await expectComputed(page, imported, 'B2').toBe('360')
})

/**
 * Where a document's rows came from, and locking so the sheet stops feeding it.
 *
 * The thing being checked is not the two buttons — it is that the refusal is
 * the *server's*. A lock that only hid a control would be a lock, right up
 * until somebody with the endpoint replaced a quotation that had been
 * corrected by hand.
 */
test('a filled table says where its rows came from, and can be locked', async ({ page }) => {
  const title = `Locked ${Date.now()}`
  const table = { doctype: 'Event', docname: 'EV00001', into: 'event_participants' }

  // The fixture is shared and this test locks it. A run that failed after the
  // lock would leave the next one with nothing to press, so the state is
  // normalised first rather than assumed.
  await page.goto('/one/files')
  const csrf = await page.evaluate(() => window.csrf_token)
  const signed = { 'X-Frappe-CSRF-Token': csrf }
  await page.request.post('/api/method/oneapp.oneapp_core.sheets.unlock', {
    form: table, headers: signed,
  })

  const id = await attendeeSheet(page, title)

  await openParticipants(page)

  // Scoped to this table's panel: an Event has two child tables and the other
  // one has a Fill control of its own.
  const panel = page.getByRole('tabpanel', { name: 'Participants' })
  await panel.getByRole('button', { name: /^Fill/ }).click()
  await page.getByLabel('Sheet', { exact: true }).click()
  await page.getByRole('option', { name: title, exact: true }).click()
  await page.getByLabel('Named range').click()
  await page.getByRole('option', { name: 'Attendees — Sheet1!A1:B2', exact: true }).click()
  await page.getByRole('button', { name: 'Replace these rows with 1' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await openParticipants(page)
  const note = page.locator('[data-slot="sheet-feed"]')
  await expect(note).toContainText(title)
  await expect(note).toContainText('Attendees')

  // Locked: the control that would replace them is gone, and so is the right.
  await note.getByRole('button', { name: 'Lock these rows' }).click()
  await expect(note).toContainText('Locked')
  await expect(page.getByRole('tabpanel', { name: 'Participants' })
    .getByRole('button', { name: /^Fill/ })).toHaveCount(0)

  // The real sheet and the real range, signed. A made-up sheet name would be
  // refused for not existing, and an unsigned POST for being unsigned — either
  // would "pass" this without the lock existing at all.
  const refused = await page.request.post('/api/method/oneapp.oneapp_core.sheets.pull', {
    form: { sheet: id, label: 'Attendees', ...table },
    headers: signed,
  })
  expect(refused.ok()).toBe(false)
  expect(await refused.text()).toContain('locked')

  await note.getByRole('button', { name: 'Follow the sheet again' }).click()
  await expect(page.getByRole('tabpanel', { name: 'Participants' })
    .getByRole('button', { name: 'Fill again' })).toBeVisible()

  // Nothing pushes. Typing in the sheet does not touch the document — what it
  // does is make the note say so, with the control that would act on it
  // already beside it.
  await expect(note).not.toContainText('has changed')
  await page.goto(`/one/sheets/${id}`)
  await ready(page)

  // Waiting for the request rather than for the word "Saved": the header says
  // Saved before anything has been typed too, so it is true immediately and
  // proves nothing.
  const written = page.waitForResponse((one) => one.url().includes('save_sheet'))
  await type(page, 'B2', 'Guest')
  await written

  await openParticipants(page)
  await expect(page.locator('[data-slot="sheet-feed"]')).toContainText('has changed')
  // And the rows are still what they were until somebody presses it.
  await expect(page.getByRole('row', { name: /Administrator/ }).first()).toBeVisible()
})
