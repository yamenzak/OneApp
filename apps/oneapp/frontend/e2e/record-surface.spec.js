import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// What surrounds a record, and what a person can do to a list.
//
// All of it renders without throwing when it is broken — an empty picker, a tab
// that loads nothing, a filter that quietly does not apply — so only looking
// catches it.
//
// The fixture is Frappe's own ToDo: a Select (badge colours), a Link (the
// picker), a Date and a Color, which has no frappe-ui counterpart and so must
// show without ever being offered.

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

// The one carrying a Link, a Colour and the seeded comments.
const SEEDED = 'Book the van for Thursday'

const openList = async (page) => {
  await page.goto('/one/app/zztasks')
  await page.waitForTimeout(1800)
}

const openRecord = async (page) => {
  await openList(page)
  await page.getByText(SEEDED).first().click()
  await page.waitForTimeout(1200)
}

// What each column's fieldtype maps to. A phone shows two of the six, so the
// assertion is per rendered header rather than a fixed count.
const HEADER_ICONS = {
  Description: 'lucide-pilcrow',
  Status: 'lucide-list',
  Priority: 'lucide-list',
  'Allocated To': 'lucide-link',
  'Due Date': 'lucide-calendar',
  Color: 'lucide-palette',
}

test('every list header carries the icon its fieldtype maps to', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const found = await page
    .locator('[data-slot="list-header-cell"]')
    .evaluateAll((cells) =>
      cells.map((cell) => [
        cell.innerText.trim(),
        [...(cell.querySelector('[class*="lucide-"]')?.classList || [])].find((c) =>
          c.startsWith('lucide-'),
        ),
      ]),
    )
  console.log('header icons:', found)

  expect(found.length).toBeGreaterThanOrEqual(2)
  for (const [label, icon] of found) {
    expect(icon, `${label} has no icon`).toBe(HEADER_ICONS[label])
  }

  await info.attach(`headers-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('a Link field offers the records it may point at', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  const asked = []
  page.on('request', (r) => {
    if (r.url().includes('appview.link_options')) asked.push(r.url())
  })
  await openRecord(page)

  // The options came from the server, bounded by the screen — not from a list
  // the SPA made up.
  expect(asked.length).toBeGreaterThan(0)

  // frappe-ui's Combobox is a text input with role=combobox and a chevron that
  // opens the list — not a Select's listbox button.
  const dialog = page.locator('[role="dialog"]')
  const combo = dialog.locator('input[role="combobox"]')
  await expect(combo).toHaveCount(1)
  // It shows what the record already points at, not a raw id in a text box.
  await expect(combo).toHaveValue('Administrator')
  await dialog.getByRole('button', { name: 'Show popup' }).click()
  await page.waitForTimeout(900)

  await info.attach(`link-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  await expect(page.getByRole('option', { name: 'Administrator' }).first()).toBeVisible()
  expectNoRealErrors(errors)
})

test('a fieldtype with no counterpart is shown and never offered', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  const dialog = page.locator('[role="dialog"]')
  await expect(dialog.getByText('Color is shown here but edited elsewhere.')).toBeVisible()
  // The value is readable; there is nothing to type into.
  await expect(dialog.getByText('#2490EF')).toBeVisible()
  await expect(dialog.locator('input[type="color"]')).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('comments and history are there without an app asking for them', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  const dialog = page.locator('[role="dialog"]')
  await dialog.getByRole('tab', { name: /^Comments/ }).click()
  await page.waitForTimeout(800)
  await expect(dialog.getByPlaceholder('Add a comment')).toBeVisible()
  // Either comments or the empty state; both are the tab working against real
  // data. That the round trip works is the next test's job.
  await expect(dialog.getByText(/No comments|[A-Za-z]/).first()).toBeVisible()

  await info.attach(`comments-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  await dialog.getByRole('tab', { name: 'History' }).click()
  await page.waitForTimeout(700)
  // Either recorded changes or the empty state; both are the tab working.
  await expect(dialog.getByText(/No changes recorded|→/).first()).toBeVisible()
  expectNoRealErrors(errors)
})

test('a comment can be added and shows up in the count', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  const dialog = page.locator('[role="dialog"]')
  const tab = dialog.getByRole('tab', { name: /^Comments/ })
  const before = await tab.innerText()

  await tab.click()
  await page.waitForTimeout(700)
  const note = `From the browser pass ${Date.now()}`
  await dialog.getByPlaceholder('Add a comment').fill(note)
  await dialog.getByRole('button', { name: 'Comment' }).click()
  await page.waitForTimeout(1600)

  await expect(dialog.getByText(note)).toBeVisible()
  expect(await tab.innerText()).not.toBe(before)
  expectNoRealErrors(errors)
})

test('a record can be liked and unliked', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  // By its icon, not by its text: the comment count beside it is also a bare
  // number, and which of the two comes first is a layout detail.
  const heart = page.locator('[role="dialog"] button:has(.lucide-heart)')
  const before = (await heart.innerText()).trim()
  await heart.click()
  await page.waitForTimeout(1000)
  expect((await heart.innerText()).trim()).not.toBe(before)

  await heart.click()
  await page.waitForTimeout(1000)
  expect((await heart.innerText()).trim()).toBe(before)
  expectNoRealErrors(errors)
})

test('sort is a field and a direction, not every field twice', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  // Frappe's shape. Six columns as twelve menu entries is a menu nobody reads.
  await page.getByRole('button', { name: /^Sorted by|^Sort$/ }).click()
  await page.waitForTimeout(600)
  const items = await page.getByRole('menuitem').allInnerTexts()
  expect(items).toContain('Due Date')
  expect(items).toContain('Description')
  // Sorting by when a row changed is useful even where nothing shows it, and
  // these three are exactly what the server allows beyond the columns.
  expect(items).toContain('Last Updated')
  expect(items).toContain('Created')
  expect(items.some((i) => i.includes('↓') || i.includes('↑'))).toBe(false)

  await page.getByRole('menuitem', { name: 'Due Date', exact: true }).click()
  await page.waitForTimeout(1500)
  await expect(page.getByRole('button', { name: 'Sorted by Due Date' })).toBeVisible()

  // The direction is its own button, and it says which way it will go.
  const flip = page.getByRole('button', { name: /^Sort (ascending|descending)$/ })
  const before = await flip.getAttribute('aria-label')
  await flip.click()
  await page.waitForTimeout(1200)
  expect(await flip.getAttribute('aria-label')).not.toBe(before)
  expectNoRealErrors(errors)
})

test('columns can be reordered and removed, and the list follows', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const headers = () => page.locator('[data-slot="list-header-cell"]').allInnerTexts()
  expect(await headers()).toContain('Status')

  await page.getByRole('button', { name: 'Columns' }).click()
  await page.waitForTimeout(600)
  await info.attach(`columns-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  // Order is the point of this picker, and the buttons are the only way a
  // keyboard or a phone can set it — a pointer drag reaches neither.
  await page.getByRole('button', { name: 'Move Status up' }).click()
  await page.waitForTimeout(1400)
  expect((await headers())[0]).toBe('Status')

  await page.getByRole('button', { name: 'Remove Status' }).click()
  await page.waitForTimeout(1400)
  expect(await headers()).not.toContain('Status')

  // And what was removed can come back. It lands at the end of the order, which
  // on a phone is past the two columns that fit — so the panel is what says it
  // is back, not the header row.
  await page.getByRole('button', { name: 'Add a column' }).click()
  await page.waitForTimeout(500)
  await page.getByRole('menuitem', { name: 'Status', exact: true }).click()
  await page.waitForTimeout(1400)
  await expect(page.getByRole('button', { name: 'Remove Status' })).toBeVisible()
  expectNoRealErrors(errors)
})

// --- filters, in Frappe's own shape -----------------------------------------

const addFilter = async (page) => {
  await page.getByRole('button', { name: /^Filter/ }).click()
  await page.waitForTimeout(500)
  await page.getByRole('button', { name: 'Add filter' }).click()
  await page.waitForTimeout(600)
}

// The three boxes of a filter row, in order: field, operator, value.
const box = (page, at) => page.locator('button[role="combobox"]').nth(at)

const pick = async (page, at, option) => {
  await box(page, at).click()
  await page.waitForTimeout(400)
  await page.getByRole('option', { name: option, exact: true }).click()
  await page.waitForTimeout(500)
}

test('a filter is a field, an operator and a value', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await addFilter(page)

  await info.attach(`filter-row-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  // It opens on Frappe's own default for the first field: a Data-ish column is
  // almost always a substring search.
  await expect(box(page, 1)).toContainText('Like')
  await expect(page.getByPlaceholder('Contains…')).toBeVisible()

  await page.getByPlaceholder('Contains…').fill('van')
  await page.getByRole('button', { name: 'Apply' }).click()
  await page.waitForTimeout(1500)

  await expect(page.getByText(SEEDED).first()).toBeVisible()
  await expect(page.getByText('Chase the Halloway invoice')).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('the operators offered are the ones that fieldtype allows', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await addFilter(page)

  // A Select has no substring search in Frappe's filter and has none here.
  await pick(page, 0, 'Status')
  await box(page, 1).click()
  await page.waitForTimeout(400)
  const forSelect = await page.getByRole('option').allInnerTexts()
  expect(forSelect).toEqual(['Equals', 'Not Equals', 'In', 'Not In', 'Is'])
  await page.keyboard.press('Escape')

  // A date gets the range operators, and Frappe's words for the comparisons.
  await pick(page, 0, 'Due Date')
  await box(page, 1).click()
  await page.waitForTimeout(400)
  const forDate = await page.getByRole('option').allInnerTexts()
  expect(forDate).toContain('Between')
  expect(forDate).toContain('Timespan')
  expect(forDate).toContain('On or Before')
  expect(forDate).not.toContain('Like')
  expectNoRealErrors(errors)
})

test('the value control follows the operator', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await addFilter(page)

  // Picking a date field switches the operator to Between, which needs two
  // dates rather than one box.
  await pick(page, 0, 'Due Date')
  await expect(box(page, 1)).toContainText('Between')
  await expect(page.getByPlaceholder('Pick two dates')).toBeVisible()

  // Timespan is a list of Frappe's own relative dates.
  await pick(page, 1, 'Timespan')
  await box(page, 2).click()
  await page.waitForTimeout(400)
  const spans = await page.getByRole('option').allInnerTexts()
  expect(spans).toContain('Last 7 Days')
  expect(spans).toContain('This Year')
  await page.getByRole('option', { name: 'This Year', exact: true }).click()
  await page.waitForTimeout(400)

  await info.attach(`filter-timespan-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  await page.getByRole('button', { name: 'Apply' }).click()
  await page.waitForTimeout(1500)
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  // `Is` needs no value at all beyond Set or Not Set.
  await page.getByRole('button', { name: /^Filter/ }).click()
  await page.waitForTimeout(500)
  await pick(page, 1, 'Is')
  await expect(box(page, 2)).toContainText('Set')
  expectNoRealErrors(errors)
})

test('is set and is not set split the list', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await addFilter(page)

  await pick(page, 0, 'Allocated To')
  await pick(page, 1, 'Is')
  await pick(page, 2, 'Set')
  await page.getByRole('button', { name: 'Apply' }).click()
  await page.waitForTimeout(1500)
  // Only the seeded one has somebody on it.
  await expect(page.getByText(SEEDED).first()).toBeVisible()
  await expect(page.getByText('Chase the Halloway invoice')).toHaveCount(0)

  await page.getByRole('button', { name: /^Filter/ }).click()
  await page.waitForTimeout(500)
  await pick(page, 2, 'Not Set')
  await page.getByRole('button', { name: 'Apply' }).click()
  await page.waitForTimeout(1500)
  await expect(page.getByText('Chase the Halloway invoice').first()).toBeVisible()
  await expect(page.getByText(SEEDED)).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('two filters both apply', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await addFilter(page)

  await pick(page, 0, 'Priority')
  await pick(page, 2, 'High')
  await page.getByRole('button', { name: 'Add filter' }).click()
  await page.waitForTimeout(600)
  await pick(page, 3, 'Status')
  await pick(page, 5, 'Open')
  await page.getByRole('button', { name: 'Apply' }).click()
  await page.waitForTimeout(1500)

  await expect(page.getByText('Chase the Halloway invoice').first()).toBeVisible()
  await expect(page.getByText(SEEDED)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Filter (2)' })).toBeVisible()
  expectNoRealErrors(errors)
})

test('a filter saves, survives a reload, and can be undone', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  await addFilter(page)
  await pick(page, 0, 'Priority')
  await pick(page, 2, 'High')
  await page.getByRole('button', { name: 'Apply' }).click()
  await page.waitForTimeout(1500)
  await expect(page.getByText(SEEDED)).toHaveCount(0)

  await page.getByRole('button', { name: 'Save this view' }).click()
  await page.waitForTimeout(1500)
  await page.reload()
  await page.waitForTimeout(2200)

  await expect(page.getByText('Chase the Halloway invoice').first()).toBeVisible()
  await expect(page.getByText(SEEDED)).toHaveCount(0)
  // And it comes back into the controls as what was chosen, not as the query
  // it turned into.
  await page.getByRole('button', { name: 'Filter (1)' }).click()
  await page.waitForTimeout(600)
  await expect(box(page, 0)).toContainText('Priority')
  await expect(box(page, 2)).toContainText('High')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Back to the default view' }).click()
  await page.waitForTimeout(2000)
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  await info.attach(`reset-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('every fieldtype reaches its own control, not a text box', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)
  const dialog = page.locator('[role="dialog"]')

  // The regression this pins: FormControl answers a type it does not recognise
  // with a plain TextInput and logs nothing, so a whole form of the wrong
  // controls looks exactly like a form of the right ones. Only the rendered
  // shape tells them apart.
  //
  // Text Editor -> Textarea.
  await expect(dialog.locator('textarea')).toHaveCount(1)
  // Two Selects -> two listbox buttons, showing the record's own values.
  const selects = dialog.locator('button[role="combobox"]')
  await expect(selects).toHaveCount(2)
  await expect(selects.first()).toContainText('Open')
  await expect(selects.nth(1)).toContainText('Medium')
  // Link -> Combobox.
  await expect(dialog.locator('input[role="combobox"]')).toHaveCount(1)
  // Date -> DatePicker, which is not a bare text input: it opens a calendar.
  // The calendar renders in a portal outside the dialog, as a role=grid.
  await dialog.getByLabel('Due Date').click()
  await page.waitForTimeout(700)
  await expect(page.getByRole('grid').first()).toBeVisible()

  await info.attach(`controls-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})
