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

// Waiting on the thing, not on a number. Playwright's expect() retries, so a
// fixed sleep is both slower than it needs to be and flakier than it looks —
// too short on a loaded machine, wasted on a fast one.
const openList = async (page) => {
  await page.goto('/one/app/zztasks')
  await expect(page.getByRole('button', { name: /^Filter/ })).toBeVisible()
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
}

const openRecord = async (page) => {
  await openList(page)
  await page.getByText(SEEDED).first().click()
  await expect(page.locator('[role="dialog"]')).toBeVisible()
}

// What each column's fieldtype maps to. A phone shows two of the six, so the
// assertion is per rendered header rather than a fixed count.
const HEADER_ICONS = {
  Description: 'lucide-pilcrow',
  // The title column is the title field, so it carries that field's icon.
  Status: 'lucide-list',
  Priority: 'lucide-list',
  'Allocated To': 'lucide-link',
  'Due Date': 'lucide-calendar',
  Color: 'lucide-palette',
}

// The three boxes of one filter row in the panel, in order: field, operator,
// value. Scoped to the popover, because the quick boxes above are the same kind
// of control and come first in the DOM.
const box = (page, at) => page.locator('[data-slot="content-body"] button[role="combobox"]').nth(at)

const pick = async (page, at, option) => {
  await box(page, at).click()
  // click() waits for the option to be actionable, so the listbox opening is
  // already covered.
  await page.getByRole('option', { name: option, exact: true }).click()
  await expect(box(page, at)).toContainText(option)
}

test('every list header carries the icon its fieldtype maps to', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  // Not one icon repeated: the map is keyed by fieldtype, so a Select and a
  // Link and a Date are told apart at a glance.
  const found = await page
    .locator('[data-slot="list-header-cell"]')
    .evaluateAll((cells) =>
      cells
        .filter((cell) => cell.querySelector('button')?.innerText.trim())
        .map((cell) => [
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

test('the first column is what the row is, with its id underneath', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const first = page
    .locator('[data-slot="list-row"]')
    .first()
    .locator('[data-slot="list-cell"]')
    .first()
  // The title from the doctype's own `title_field`, and the id quietly below
  // it — what a person reads, and what they quote on the phone.
  await expect(first).toContainText(SEEDED)
  await expect(first).toContainText('kosfpdsaqg')
  // An avatar, drawn from the id when the doctype declares no image field.
  await expect(first.locator('[data-slot="avatar"], img, span').first()).toBeVisible()
  expectNoRealErrors(errors)
})

test('every row carries its age, its comments and a heart', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const meta = page
    .locator('[data-slot="list-row"]')
    .first()
    .locator('[data-slot="list-cell"]')
    .last()
  // Relative, and without the "ago": a column of ages, not a sentence repeated
  // down the page.
  await expect(meta).toContainText(/hours|minutes|days|seconds/)
  await expect(meta.getByRole('button', { name: /favourites/ })).toBeVisible()
  expectNoRealErrors(errors)
})

test('a row can be liked from the list, and the heart filters to it', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const rows = () => page.locator('[data-slot="list-row"]')
  const heart = page.getByRole('button', { name: 'Only my favourites' })

  // Start from nothing liked rather than assuming it: this runs against a real
  // site, and an earlier run that failed half way leaves its likes behind.
  for (const row of await rows().all()) {
    const remove = row.getByRole('button', { name: 'Remove from favourites' })
    if (await remove.count()) {
      await remove.click()
    }
  }
  await expect(rows()).toHaveCount(2)

  // With nothing liked the filter empties the list, and the list header goes
  // with it — so the way back out is in the empty state.
  await heart.click()
  await expect(page.getByText('Nothing you have liked is on this screen.')).toBeVisible()
  await expect(heart).toHaveCount(0)

  await page.getByRole('button', { name: 'Show everything' }).click()

  await rows().first().getByRole('button', { name: 'Add to favourites' }).click()
  await expect(rows().first().getByRole('button', { name: 'Remove from favourites' })).toBeVisible()

  await heart.click()
  await expect(rows()).toHaveCount(1)
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  await info.attach(`favourites-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })

  // Put it back, so the next test starts where this one did.
  await rows().first().getByRole('button', { name: 'Remove from favourites' }).click()
  await page.getByRole('button', { name: 'Show everything' }).click()
  expectNoRealErrors(errors)
})

test('clicking a header sorts by it and says which way', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  // Two columns a phone also renders, so this holds at either width.
  const header = page.getByRole('columnheader', { name: 'Description' })
  await expect(header).not.toHaveAttribute('aria-sort', /ascending|descending/)

  await header.getByRole('button').click()
  // Descending first: "show me the newest" is what a column usually means.
  await expect(header).toHaveAttribute('aria-sort', 'descending')

  await header.getByRole('button').click()
  await expect(header).toHaveAttribute('aria-sort', 'ascending')

  // And only one column is the sort key at a time.
  const other = page.getByRole('columnheader', { name: 'Status' })
  await other.getByRole('button').click()
  await expect(other).toHaveAttribute('aria-sort', 'descending')
  await expect(header).not.toHaveAttribute('aria-sort', /ascending|descending/)
  expectNoRealErrors(errors)
})

test('the column picker offers the whole doctype, not the manifest', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  await page.getByRole('button', { name: 'Choose columns' }).click()
  const picker = page.locator('[role="dialog"]')

  await info.attach(`columns-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  // The manifest named six. ToDo has more, and wanting one of them on your list
  // is a choice rather than a deploy.
  await expect(picker.getByRole('button', { name: 'Reference Type' })).toBeVisible()
  await expect(picker.getByRole('button', { name: 'Assigned By', exact: true })).toBeVisible()

  await picker.getByRole('button', { name: 'Reference Type' }).click()
  await expect(picker.getByRole('button', { name: 'Remove Reference Type' })).toBeVisible()
  await page.keyboard.press('Escape')
  expectNoRealErrors(errors)
})

test('columns can be reordered and removed', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const headers = () => page.getByRole('columnheader').allInnerTexts()
  await expect.poll(headers).toContain('Status')

  await page.getByRole('button', { name: 'Choose columns' }).click()

  // The arrows are not a nicety: a pointer drag reaches neither a keyboard nor
  // a phone, and order is the point of this dialog.
  await page.getByRole('button', { name: 'Move Status up' }).click()
  await page.getByRole('button', { name: 'Remove Status' }).click()
  await page.keyboard.press('Escape')

  await expect.poll(headers).not.toContain('Status')

  // Put it back: these run against one shared site, and the next test should
  // not have to know what this one did.
  await page.getByRole('button', { name: 'Choose columns' }).click()
  await page.getByRole('button', { name: 'Status', exact: true }).click()
  await page.keyboard.press('Escape')
  expectNoRealErrors(errors)
})

// --- the quick filter row ---------------------------------------------------

test('a box per field, above the list', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  await info.attach(`quick-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  // Every list gets an ID box, at any width.
  await expect(page.getByPlaceholder('ID')).toBeVisible()

  if (info.project.name === 'mobile') {
    // Five boxes stacked is most of a phone screen before a single row shows,
    // so the rest live in the Filter panel — which is Frappe's call too.
    await expect(page.getByPlaceholder('Description')).toBeHidden()
    expectNoRealErrors(errors)
    return
  }

  // Which fields get one is Frappe's own answer: `in_standard_filter` plus the
  // title field.
  await expect(page.getByPlaceholder('Description')).toBeVisible()
  expect(await page.locator('button[role="combobox"]').allInnerTexts()).toEqual(
    expect.arrayContaining(['Status', 'Priority']),
  )

  await page.getByPlaceholder('Description').fill('van')
  await page.getByPlaceholder('Description').press('Enter')
  await expect(page.getByText(SEEDED).first()).toBeVisible()
  await expect(page.getByText('Chase the Halloway invoice')).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('a quick box can be exact or roughly', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  // Frappe's `≈` toggle, on the one box every viewport has. Both ids start
  // "kos", so Like finds them and Equals finds neither.
  await page.getByPlaceholder('ID').fill('kos')
  await page.getByPlaceholder('ID').press('Enter')
  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(2)

  await page.getByRole('button', { name: 'How ID matches' }).click()
  await page.getByRole('menuitem', { name: 'Equals' }).click()
  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('a quick box and the panel both apply', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  await page.getByPlaceholder('ID').fill('kos')
  await page.getByPlaceholder('ID').press('Enter')
  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(2)

  await page.getByRole('button', { name: /^Filter/ }).click()
  await page.getByRole('button', { name: 'Add filter' }).click()
  await pick(page, 0, 'Priority')
  await pick(page, 2, 'High')
  await page.getByRole('button', { name: 'Apply' }).click()

  // Neither cleared the other.
  await expect(page.getByText('Chase the Halloway invoice').first()).toBeVisible()
  await expect(page.getByText(SEEDED)).toHaveCount(0)
  await expect(page.getByPlaceholder('ID')).toHaveValue('kos')
  expectNoRealErrors(errors)
})

test('the filter count is a badge, not a word', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  const filter = page.getByRole('button', { name: /^Filter/ })
  await expect(filter).toHaveText('Filter')

  await filter.click()
  await page.getByRole('button', { name: 'Add filter' }).click()
  await page.getByRole('button', { name: 'Apply' }).click()

  // The number is beside the word rather than inside it: the label span still
  // reads exactly "Filter", and the count is its own element.
  await expect(filter.locator('span.truncate')).toHaveText('Filter')
  await expect(filter).toContainText('1')
  expectNoRealErrors(errors)
})

// --- the record ------------------------------------------------------------

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

  const dialog = page.locator('[role="dialog"]')
  // frappe-ui's Combobox is a text input with role=combobox and a chevron that
  // opens the list — not a Select's listbox button.
  const combo = dialog.locator('input[role="combobox"]').first()
  await expect(combo).toHaveValue('Administrator')
  await dialog.getByRole('button', { name: 'Show popup' }).first().click()

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
  expect(await dialog.locator('textarea').count()).toBeGreaterThanOrEqual(1)
  // Selects -> listbox buttons, showing the record's own values.
  const selects = dialog.locator('button[role="combobox"]')
  expect(await selects.count()).toBeGreaterThanOrEqual(2)
  await expect(selects.first()).toContainText('Open')
  // Links -> Comboboxes.
  expect(await dialog.locator('input[role="combobox"]').count()).toBeGreaterThanOrEqual(1)

  // Date -> DatePicker, which is not a bare text input: it opens a calendar.
  // The calendar renders in a portal outside the dialog, as a role=grid.
  await dialog.getByLabel('Due Date').click()
  await expect(page.getByRole('grid').first()).toBeVisible()

  await info.attach(`controls-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('the record shows every field, not the columns someone chose', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  // Drop a column, then open a record: the field is still there. Hiding a
  // column is a statement about the list; the record still has the field.
  await page.getByRole('button', { name: 'Choose columns' }).click()
  await page.getByRole('button', { name: 'Remove Priority' }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('columnheader', { name: 'Priority' })).toHaveCount(0)

  await page.getByText(SEEDED).first().click()
  await expect(page.locator('[role="dialog"]').getByText('Priority', { exact: true })).toBeVisible()
  expectNoRealErrors(errors)
})

test('comments and history are there without an app asking for them', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  const dialog = page.locator('[role="dialog"]')
  await dialog.getByRole('tab', { name: /^Comments/ }).click()
  await expect(dialog.getByPlaceholder('Add a comment')).toBeVisible()
  // Either comments or the empty state; both are the tab working against real
  // data. That the round trip works is the next test's job.
  await expect(dialog.getByText(/No comments|[A-Za-z]/).first()).toBeVisible()

  await info.attach(`comments-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  await dialog.getByRole('tab', { name: 'History' }).click()
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
  const note = `From the browser pass ${Date.now()}`
  await dialog.getByPlaceholder('Add a comment').fill(note)
  await dialog.getByRole('button', { name: 'Comment' }).click()

  await expect(dialog.getByText(note)).toBeVisible()
  // The count is a badge beside the word, so the tab's text changes with it.
  await expect.poll(() => tab.innerText()).not.toBe(before)
  expectNoRealErrors(errors)
})

test('a record can be liked and unliked from the dialog', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  // By its icon, not by its text: the comment count beside it is also a bare
  // number, and which of the two comes first is a layout detail.
  const heart = page.locator('[role="dialog"] button:has(.lucide-heart)')
  const before = (await heart.innerText()).trim()
  await heart.click()
  await expect.poll(async () => (await heart.innerText()).trim()).not.toBe(before)

  await heart.click()
  await expect.poll(async () => (await heart.innerText()).trim()).toBe(before)
  expectNoRealErrors(errors)
})

// --- remembering it ---------------------------------------------------------

test('a view saves, survives a reload, and can be undone', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  await page.getByRole('button', { name: /^Filter/ }).click()
  await page.getByRole('button', { name: 'Add filter' }).click()
  await pick(page, 0, 'Priority')
  await pick(page, 2, 'High')
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.getByText(SEEDED)).toHaveCount(0)

  await page.getByRole('button', { name: 'Save this view' }).click()
  // The save re-resolves the screen, and reloading over that in-flight request
  // aborts it — which the browser reports as "Failed to fetch". Wait for the
  // thing a save produces instead: the button that undoes it.
  await expect(page.getByRole('button', { name: 'Back to the default view' })).toBeVisible()
  await page.reload()

  await expect(page.getByText('Chase the Halloway invoice').first()).toBeVisible()
  await expect(page.getByText(SEEDED)).toHaveCount(0)
  // And it comes back into the controls as what was chosen, not as the query
  // it turned into.
  await page.getByRole('button', { name: /^Filter/ }).click()
  await expect(box(page, 0)).toContainText('Priority')
  await expect(box(page, 2)).toContainText('High')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Back to the default view' }).click()
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  await info.attach(`reset-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})
