import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * The grid, in a browser.
 *
 * The engine is tested in node — a thousand cells pasted, a cycle caught, a
 * chain of four thousand rebuilt from its head. None of that says whether a
 * person can type into this thing. What only a browser can answer: whether
 * clicking a cell selects it, whether typing starts an edit, whether a formula
 * typed into one cell changes another, whether what was typed survives a
 * reload — which is the only proof the write actually reached the server — and
 * whether the Drive can get you here at all.
 *
 * A sheet is made by the test rather than seeded, because a test that shares a
 * fixture with another test is a test that fails when the other one is edited.
 */

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/** The cell at this reference. Cells are labelled by ref, which is why. */
const cell = (page, ref) => page.getByRole('gridcell', { name: ref, exact: true })

/**
 * Make an empty sheet from the Drive and land in it. Returns its id.
 *
 * Two clicks, not one: New sheet is a menu, because a workspace with an
 * estimator template starts from it far more often than from a blank grid.
 */
async function newSheet(page) {
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New sheet' }).click()
  await page.getByRole('menuitem', { name: 'Blank sheet' }).click()
  await page.waitForURL(/\/one\/sheets\//)
  await expect(page.locator('[data-slot="sheet-grid"]')).toBeVisible()
  return page.url().split('/one/sheets/')[1]
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

/** Type into a cell the way a person does: click it, type, press Enter. */
async function type(page, ref, text) {
  await cell(page, ref).click()
  await page.keyboard.type(text)
  await page.keyboard.press('Enter')
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
  await expect(page.locator('[data-slot="sheet-grid"]')).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(id).toBeTruthy()
})

test('a sheet is made from the Drive and opens on an empty grid', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await newSheet(page)

  await expect(page.locator('[data-slot="sheet-toolbar"]')).toBeVisible()
  await expect(page.locator('[data-slot="sheet-tabs"]')).toBeVisible()
  // A1 through to a column header: the grid drew, rather than drawing nothing
  // and leaving a toolbar over it.
  await expect(cell(page, 'A1')).toBeVisible()
  await expect(page.getByRole('grid')).toContainText('ABCDEF')
  await expect(page.locator('[data-slot="sheet-tabs"]')).toContainText('Sheet1')

  expectNoRealErrors(errors)
})

test('typing into a cell puts a value in it, and a formula reads it back', async ({
  page,
}) => {
  const errors = collectConsoleErrors(page)
  await newSheet(page)

  await type(page, 'A1', '6')
  await type(page, 'A2', '7')
  await type(page, 'A3', '=A1*A2')

  await expect(cell(page, 'A3')).toHaveText('42')

  // The point of the whole engine: changing what a formula reads changes the
  // formula, without anybody touching the formula.
  await type(page, 'A1', '10')
  await expect(cell(page, 'A3')).toHaveText('70')

  expectNoRealErrors(errors)
})

test('the formula bar shows the formula, and the cell shows the number', async ({
  page,
}) => {
  await newSheet(page)
  await type(page, 'B1', '4')
  await type(page, 'B2', '=B1+1')

  await cell(page, 'B2').click()
  await expect(page.getByRole('textbox', { name: 'Formula bar' })).toHaveValue('=B1+1')
  await expect(cell(page, 'B2')).toHaveText('5')
})

test('what was typed is still there after a reload', async ({ page }) => {
  const id = await newSheet(page)
  await type(page, 'C1', '3')
  await type(page, 'C2', '=C1*3')
  await expect(cell(page, 'C2')).toHaveText('9')

  // The header says so before we trust it: the queue settles on a timer, and
  // reloading inside that window would prove nothing.
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()

  await page.goto(`/one/sheets/${id}`)
  await expect(cell(page, 'C1')).toHaveText('3')
  await expect(cell(page, 'C2')).toHaveText('9')
})

test('an unknown function says so the way Excel does', async ({ page }) => {
  await newSheet(page)
  await type(page, 'A1', '=NOSUCHFUNCTION(1)')
  await expect(cell(page, 'A1')).toHaveText('#NAME?')

  // And the toolbar explains it, which is where the explanation lives: a
  // tooltip per cell would be a component per cell.
  await cell(page, 'A1').click()
  await expect(page.locator('[data-slot="sheet-toolbar"]')).toContainText('not implemented')
})

test('a formula that reads itself is caught rather than hanging the grid', async ({
  page,
}) => {
  await newSheet(page)
  await type(page, 'A1', '=A1+1')
  await expect(cell(page, 'A1')).toHaveText('#CIRCULAR!')
})

test('arrow keys move the selection and the formula bar follows', async ({ page }) => {
  await newSheet(page)
  await cell(page, 'A1').click()
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowDown')
  await expect(page.locator('[data-slot="sheet-toolbar"]')).toContainText('Sheet1!B2')
})

test('a tab is added and the grid switches to it', async ({ page }) => {
  await newSheet(page)
  await type(page, 'A1', 'first tab')

  await page.locator('[data-slot="sheet-tabs"]').getByRole('button', { name: 'Add a tab' }).click()
  await expect(page.locator('[data-slot="sheet-tabs"]')).toContainText('Sheet2')
  // The new tab is empty, which is the thing worth checking: a tab that showed
  // the first tab's cells would be one table pretending to be two.
  await expect(cell(page, 'A1')).toHaveText('')
})

test('a selection can be named, and the name is offered back', async ({ page }) => {
  await newSheet(page)
  await type(page, 'A1', 'Item')
  await type(page, 'B1', 'Rate')

  await cell(page, 'A1').click()
  await page.keyboard.down('Shift')
  await page.keyboard.press('ArrowRight')
  await page.keyboard.up('Shift')

  await page.getByRole('button', { name: 'Name this range' }).click()
  await page.getByRole('textbox', { name: 'Name' }).fill('LineItems')
  await page.getByRole('button', { name: 'Name it' }).click()

  await expect(page.getByRole('button', { name: /LineItems/ })).toBeVisible()
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

  await newSheet(page)

  // Named, so the picker on the record can find this run's sheet rather than
  // one of the "Untitled sheet"s every other run left behind.
  await page.getByRole('button', { name: 'Rename this sheet' }).click()
  await page.getByRole('textbox', { name: 'Name' }).fill(title)
  await page.getByRole('button', { name: 'Rename', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await type(page, 'A1', 'Reference Document Type')
  await type(page, 'B1', 'Reference Docname')
  await type(page, 'A2', 'User')
  await type(page, 'B2', 'Administrator')

  await cell(page, 'A1').click()
  await page.keyboard.down('Shift')
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.up('Shift')

  await page.getByRole('button', { name: 'Name this range' }).click()
  await page.getByRole('textbox', { name: 'Name' }).fill('Attendees')
  await page.getByRole('button', { name: 'Name it' }).click()
  await expect(page.getByRole('button', { name: /Attendees/ })).toBeVisible()
  await page.keyboard.press('Escape')

  // The queue settles on a timer. Leaving before it does is exactly what the
  // beacon exists for, and a test that relied on the beacon would be testing
  // the browser rather than the read-back.
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()

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
 * rows. What is worth checking in a browser is the loop rather than the copy:
 * marking one, finding it in the New sheet menu, and landing in a grid that
 * already has the template's cells in it.
 */
test('a sheet can be made a template, and a new sheet starts from it', async ({ page }) => {
  const title = `Estimator ${Date.now()}`

  await newSheet(page)
  await page.getByRole('button', { name: 'Rename this sheet' }).click()
  await page.getByRole('textbox', { name: 'Name' }).fill(title)
  await page.getByRole('button', { name: 'Rename', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await type(page, 'A1', 'Rate card')
  await type(page, 'B1', '250')
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'More', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Use as a template' }).click()
  await expect(page.getByText('Template', { exact: true })).toBeVisible()

  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New sheet' }).click()
  await page.getByRole('menuitem', { name: title, exact: true }).click()

  await page.waitForURL(/\/one\/sheets\//)
  await expect(cell(page, 'A1')).toHaveText('Rate card')
  await expect(cell(page, 'B1')).toHaveText('250')
})

/**
 * Excel, both ways, as one round trip.
 *
 * No committed `.xlsx` fixture: the test exports one and imports what it
 * exported, which checks both halves against each other and cannot drift from
 * a binary nobody can read in a diff. What it is really asking is whether a
 * formula survives — a spreadsheet that exports numbers and imports numbers is
 * a CSV with more steps.
 */
test('a sheet exports to Excel and comes back with its formulas', async ({ page }) => {
  await newSheet(page)
  await type(page, 'A1', 'Rate')
  await type(page, 'A2', '120')
  await type(page, 'B2', '=A2*3')
  await expect(cell(page, 'B2')).toHaveText('360')
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()

  const coming = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download' }).click()
  await page.getByRole('menuitem', { name: /Excel workbook/ }).click()
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
  await expect(cell(page, 'A2')).toHaveText('120')
  await expect(cell(page, 'B2')).toHaveText('360')

  // The formula, not the number it came to. This is the whole point.
  await cell(page, 'B2').click()
  await expect(page.getByRole('textbox', { name: 'Formula bar' })).toHaveValue('=A2*3')
})

test('printing builds its own document rather than the windowed grid', async ({ page }) => {
  await newSheet(page)
  await type(page, 'A1', 'Item')
  await type(page, 'B1', '42')

  await page.getByRole('button', { name: 'More', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Print this tab' }).click()

  // The iframe is written and then printed from; asserting the document it was
  // given is the only half a headless browser can see, and it is the half that
  // breaks — the grid windows its rows, so printing the page prints whichever
  // forty are in the DOM.
  // Not `toBeVisible`: the frame is a zero-sized, transparent one — it exists
  // to be printed from, not to be looked at.
  const printed = page.frameLocator('iframe[title="Print preview"]')
  await expect(printed.locator('h1')).toContainText('Untitled sheet')
  await expect(printed.locator('table')).toContainText('Item')
  await expect(printed.locator('table')).toContainText('42')
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

  const id = await newSheet(page)
  await page.getByRole('button', { name: 'Rename this sheet' }).click()
  await page.getByRole('textbox', { name: 'Name' }).fill(title)
  await page.getByRole('button', { name: 'Rename', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await type(page, 'A1', 'Reference Document Type')
  await type(page, 'B1', 'Reference Docname')
  await type(page, 'A2', 'User')
  await type(page, 'B2', 'Administrator')

  await cell(page, 'A1').click()
  await page.keyboard.down('Shift')
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.up('Shift')
  await page.getByRole('button', { name: 'Name this range' }).click()
  await page.getByRole('textbox', { name: 'Name' }).fill('Attendees')
  await page.getByRole('button', { name: 'Name it' }).click()
  await expect(page.getByRole('button', { name: /Attendees/ })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByText('Saved', { exact: true })).toBeVisible()

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

  // Waiting for the request rather than for the word "Saved": the header says
  // Saved before anything has been typed too, so it is true immediately and
  // proves nothing.
  const written = page.waitForResponse((one) => one.url().includes('write_cells'))
  await type(page, 'B2', 'Guest')
  await written

  await openParticipants(page)
  await expect(page.locator('[data-slot="sheet-feed"]')).toContainText('has changed')
  // And the rows are still what they were until somebody presses it.
  await expect(page.getByRole('row', { name: /Administrator/ }).first()).toBeVisible()
})
