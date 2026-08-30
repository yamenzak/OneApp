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

test('sort offers every column in both directions', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  await page.getByRole('button', { name: 'Sort' }).click()
  await page.waitForTimeout(600)
  const items = await page.getByRole('menuitem').allInnerTexts()
  // Six columns, ascending and descending, named as the screen names them.
  expect(items).toContain('Due Date ↑')
  expect(items).toContain('Description ↓')
  expect(items.length).toBe(12)

  await page.getByRole('menuitem', { name: 'Due Date ↑' }).click()
  await page.waitForTimeout(1500)
  await expect(page.getByRole('button', { name: /Sorted by Due Date/ })).toBeVisible()
  expectNoRealErrors(errors)
})

test('columns can be dropped and the list follows', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const headers = () => page.locator('[data-slot="list-header-cell"]').allInnerTexts()
  expect(await headers()).toContain('Status')

  await page.getByRole('button', { name: 'Columns' }).click()
  await page.waitForTimeout(600)
  // All six are offered whatever the viewport: which columns a person wants is
  // about the screen, not about the width of their phone.
  expect(await page.getByRole('checkbox').count()).toBe(6)
  await page.getByRole('checkbox', { name: 'Status' }).click()
  await page.waitForTimeout(1500)

  expect(await headers()).not.toContain('Status')
  expectNoRealErrors(errors)
})

test('a filter narrows the list, saves, and can be undone', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  await page.getByRole('button', { name: 'Filter' }).click()
  await page.waitForTimeout(700)
  await info.attach(`filters-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  // Priority is the second Select in the popover; frappe-ui renders one as a
  // listbox button rather than a native <select>.
  await page.locator('button[role="combobox"]').nth(1).click()
  await page.waitForTimeout(400)
  await page.getByRole('option', { name: 'High', exact: true }).click()
  await page.getByRole('button', { name: 'Apply' }).click()
  await page.waitForTimeout(1500)

  await expect(page.getByText('Chase the Halloway invoice').first()).toBeVisible()
  await expect(page.getByText(SEEDED)).toHaveCount(0)

  // Saved, it is the view this person lands on next time.
  await page.getByRole('button', { name: 'Save this view' }).click()
  await page.waitForTimeout(1500)
  await page.reload()
  await page.waitForTimeout(2200)
  await expect(page.getByText('Chase the Halloway invoice').first()).toBeVisible()
  await expect(page.getByText(SEEDED)).toHaveCount(0)

  // And the way back is one button.
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
