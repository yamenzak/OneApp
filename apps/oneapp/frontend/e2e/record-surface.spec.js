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
  await page.goto('/one/space/zzmock')
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
  Role: 'lucide-link',
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

  // The seeded row rather than whichever is first: what is being pinned is
  // the shape of the title cell, and the screen's sort is the screen's own
  // business.
  const first = page
    .locator('[data-slot="list-row"]', { hasText: SEEDED })
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

  // At every width. A screen is a saved answer to "what do I look at", so a
  // phone gets the same columns and scrolls the table rather than being handed
  // a different list — see `test_the_app_host_shows_the_same_columns_on_every_screen`.
  const meta = page
    .locator('[data-slot="list-row"]')
    .first()
    .locator('[data-slot="list-cell"]')
    .last()
  // Relative, and without the "ago": a column of ages, not a sentence repeated
  // down the page. Singular included — dayjs says "a minute", and a row this
  // suite edited a moment ago is exactly the row that reads that way.
  await expect(meta).toContainText(/second|minute|hour|day|month|year/)
  await expect(meta.getByRole('button', { name: /favourites/ })).toBeVisible()
  expectNoRealErrors(errors)
})

test('a row can be liked from the list, and the heart filters to it', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  // The row heart lives in the activity column at both widths; on a phone that
  // column is off to the right of the scroller, which is a scroll rather than
  // an absence.
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
  await expect(page.getByRole('button', { name: 'Remove from favourites' })).toHaveCount(0)

  // With nothing liked the filter empties the list, and the list header goes
  // with it — so the way back out is in the empty state.
  await heart.click()
  await expect(page.getByText('Nothing you have liked is on this screen.')).toBeVisible()
  await expect(heart).toHaveCount(0)

  await page.getByRole('button', { name: 'Show everything' }).click()

  // Whichever row is first, not a row named here: the fixture's order is the
  // screen's to decide, and a test that hard-codes one breaks when a manifest
  // changes its sort rather than when the heart breaks.
  const title = () => rows().first().locator('[data-slot="list-cell"]').first()
  const liked = (await title().innerText()).split('\n')[0]
  await rows().first().getByRole('button', { name: 'Add to favourites' }).click()
  await expect(rows().first().getByRole('button', { name: 'Remove from favourites' })).toBeVisible()

  await heart.click()
  await expect(rows()).toHaveCount(1)
  await expect(title()).toContainText(liked)

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

  // Frappe's `≈` toggle, on the one box every viewport has. The three written
  // todos were named in one run, so their ids share a prefix the forty backlog
  // rows do not: Like finds those three and Equals finds none of them.
  await page.getByPlaceholder('ID').fill('kos')
  await page.getByPlaceholder('ID').press('Enter')
  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(3)

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
  await expect(page.locator('[data-slot="list-row"]')).toHaveCount(3)

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

test('an icon-only control names itself on hover', async ({ page }, info) => {
  // A picture is not a label. Every icon-only control carries frappe-ui's own
  // tooltip — `label` alone reaches a screen reader and nobody else, and the
  // gear beside a list is one click from changing what the list shows.
  test.skip(info.project.name === 'mobile', 'hover is a thing pointers do')
  const errors = collectConsoleErrors(page)
  await openList(page)

  await page.getByRole('button', { name: 'Choose columns' }).hover()
  // reka's TooltipContent, which frappe-ui wraps — a bubble in a portal, not
  // the browser's own `title`, which is why it is findable at all.
  await expect(page.locator('[data-slot="bubble"]')).toContainText('Choose columns')
  expectNoRealErrors(errors)
})

test('a link previews the record it points at, on hover', async ({ page }, info) => {
  // `in_preview` is a flag the *target* doctype sets on its own fields, and
  // the fixture sets three on User through a Property Setter. Which fields the
  // card shows is that doctype's answer — no manifest chooses them, and every
  // screen pointing at User gets the same card.
  test.skip(info.project.name === 'mobile', 'hover is a thing pointers do')
  const errors = collectConsoleErrors(page)
  await openList(page)

  await page.getByText('Administrator').first().hover()
  await expect(page.getByText('admin@example.com')).toBeVisible()
  await expect(page.getByText('User Type')).toBeVisible()

  await info.attach(`preview-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('a doctype that says how wide a column wants to be is believed', async ({ page }) => {
  // `columns: 4` on ToDo's description, set by the fixture. Four of Frappe's
  // grid units, and a column that opens at its own default rather than at the
  // one the cell kind guessed.
  const errors = collectConsoleErrors(page)
  await openList(page)

  const header = page.getByRole('columnheader', { name: 'Description' })
  const wide = await header.boundingBox()
  const narrow = await page.getByRole('columnheader', { name: 'Status' }).boundingBox()
  expect(wide.width).toBeGreaterThan(narrow.width * 2)
  expectNoRealErrors(errors)
})

test('a Link field offers the records it may point at', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  const asked = []
  page.on('request', (r) => {
    if (r.url().includes('spaceview.link_options')) asked.push(r.url())
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

test('a link search asks the server, and Create is offered only where it is allowed', async ({
  page,
}, info) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)
  const dialog = page.locator('[role="dialog"]')

  // Role is the second Link on the fixture and the one the space granted, so
  // it is the one that may be created from. `allocated_to` points at User,
  // which the space did not grant — no Create row, whatever this person's own
  // permissions are.
  const roles = dialog.getByLabel('Role', { exact: true })
  await roles.click()
  await expect(page.getByRole('option', { name: /Create a new Role/ })).toBeVisible()

  await dialog.getByLabel('Allocated To', { exact: true }).click()
  await expect(page.getByRole('option', { name: /^Create/ })).toHaveCount(0)
  await page.keyboard.press('Escape')

  // Typing searches the server rather than filtering what is already on
  // screen: the row below is not in the first page of results.
  const asked = []
  page.on('request', (r) => {
    if (r.url().includes('spaceview.link_options')) asked.push(r.url())
  })
  await roles.click()
  await roles.fill('Report')
  await expect(page.getByRole('option', { name: 'Report Manager' })).toBeVisible()
  expect(asked.some((url) => url.includes('query=Report'))).toBe(true)

  // And what was typed is offered as a name rather than thrown away.
  await expect(page.getByRole('option', { name: 'Create "Report"' })).toBeVisible()

  await info.attach(`link-create-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('a record can be created from the picker and is adopted as the value', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  const made = `ZZ Picker ${Date.now()}`
  await openRecord(page)
  const dialog = page.locator('[role="dialog"]').first()

  const roles = dialog.getByLabel('Role', { exact: true })
  await roles.click()
  await roles.fill(made)
  await page.getByRole('option', { name: `Create "${made}"` }).click()

  // The quick form is the doctype's own answer: Role marks `role_name`
  // mandatory and nothing else, and the search text is already in it.
  const quick = page.locator('[role="dialog"]').last()
  await expect(quick.getByLabel('Role Name')).toHaveValue(made)
  await quick.getByRole('button', { name: 'Create' }).click()

  // Created and picked in one move — the point of creating one here was to
  // choose it.
  await expect(roles).toHaveValue(made)
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

test('a screen saves, survives a reload, and can be undone', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  await page.getByRole('button', { name: /^Filter/ }).click()
  await page.getByRole('button', { name: 'Add filter' }).click()
  await pick(page, 0, 'Priority')
  await pick(page, 2, 'High')
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.getByText(SEEDED)).toHaveCount(0)

  await page.getByRole('button', { name: 'Save this screen' }).click()
  // The save re-resolves the screen, and reloading over that in-flight request
  // aborts it — which the browser reports as "Failed to fetch". Wait for the
  // thing a save produces instead: the button that undoes it.
  await expect(page.getByRole('button', { name: 'Back to the default screen' })).toBeVisible()
  await page.reload()

  await expect(page.getByText('Chase the Halloway invoice').first()).toBeVisible()
  await expect(page.getByText(SEEDED)).toHaveCount(0)
  // And it comes back into the controls as what was chosen, not as the query
  // it turned into.
  await page.getByRole('button', { name: /^Filter/ }).click()
  await expect(box(page, 0)).toContainText('Priority')
  await expect(box(page, 2)).toContainText('High')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'Back to the default screen' }).click()
  await expect(page.getByText(SEEDED).first()).toBeVisible()

  await info.attach(`reset-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

// --- selection --------------------------------------------------------------

test('rows can be selected and deleted together', async ({ page, baseURL }, info) => {
  const errors = collectConsoleErrors(page)

  // Made through the API rather than the UI: this test is about deleting, and
  // borrowing a fixture row would leave the ones after it with less to look at.
  const doomed = `Delete me ${Date.now()}`
  // Frappe rejects a POST without its CSRF token, and `page.request` carries
  // the session cookie but not the token — so ask the page for it.
  await page.goto('/one/space/zzmock')
  // Settle before reloading: a reload over the in-flight screen resolve aborts
  // it, which the browser reports as "Failed to fetch".
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
  const csrf = await page.evaluate(() => window.csrf_token)
  const made = await page.request.post(`${baseURL}/api/method/oneapp.oneapp_core.spaceview.save`, {
    headers: { 'X-Frappe-CSRF-Token': csrf },
    form: {
      space_code: 'zzmock',
      screen: 'all',
      values: JSON.stringify({ description: doomed, status: 'Open', priority: 'Low' }),
    },
  })
  expect(made.ok(), await made.text()).toBeTruthy()

  await page.reload()
  await expect(page.getByText(doomed).first()).toBeVisible()

  const row = page.locator('[data-slot="list-row"]').filter({ hasText: doomed })
  await row.locator('[data-slot="list-row-checkbox"]').click()
  await expect(page.getByText('1 selected')).toBeVisible()

  await info.attach(`selection-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  // Deleting is the one thing here that does not come back, so it asks first.
  await page.getByRole('button', { name: 'Delete 1' }).click()
  await expect(page.getByText('This cannot be undone.', { exact: false })).toBeVisible()
  await page.locator('[role="dialog"]').getByRole('button', { name: 'Delete' }).click()

  await expect(page.getByText(doomed)).toHaveCount(0)
  await expect(page.getByText('1 selected')).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('select-all ticks the page', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  // However many rows there are: this runs against a real site, and a test
  // that hard-codes the fixture's size fails for the wrong reason the moment
  // something else adds a row.
  const count = await page.locator('[data-slot="list-row"]').count()
  await page.locator('[data-slot="list-header-checkbox"]').click()
  await expect(page.getByText(`${count} selected`)).toBeVisible()

  await page.getByRole('button', { name: 'Clear' }).click()
  await expect(page.getByText('selected')).toHaveCount(0)
  expectNoRealErrors(errors)
})

// --- grouping ---------------------------------------------------------------

test('rows can be grouped by a column', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  // Chosen where the columns are, because it is a question about the columns.
  await page.getByRole('button', { name: 'Choose columns' }).click()
  await page.getByLabel('Group rows by').click()
  await page.getByRole('option', { name: 'Status', exact: true }).click()
  await page.getByRole('button', { name: 'Done' }).click()

  const headings = page.locator('[data-slot="list-group-header"]')
  await expect(headings.first()).toBeVisible()
  const labels = await headings.allInnerTexts()
  expect(labels).toContain('Open')
  expect(labels).toContain('Closed')
  // Each group appears once: the server sorts by the group column first, so a
  // run of rows is a group.
  expect(new Set(labels).size).toBe(labels.length)

  await info.attach(`grouped-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }),
    contentType: 'image/png',
  })

  // Put it back for whatever runs next.
  await page.getByRole('button', { name: 'Choose columns' }).click()
  await page.getByLabel('Group rows by').click()
  await page.getByRole('option', { name: 'Nothing', exact: true }).click()
  await page.getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('[data-slot="list-group-header"]')).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('the phone puts the box and its three controls on one row', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'this is the phone layout')
  const errors = collectConsoleErrors(page)
  await openList(page)

  // The ID box takes the width; the three controls sit at its end — reveal the
  // rest of the boxes, the list's settings, the filter panel.
  const box = page.getByPlaceholder('ID')
  const controls = [
    page.getByRole('button', { name: 'More filters' }),
    page.getByRole('button', { name: 'Choose columns' }),
    page.getByRole('button', { name: /^Filter/ }),
  ]
  const boxBox = await box.boundingBox()
  for (const control of controls) {
    const rect = await control.boundingBox()
    // Same row, and after the box.
    expect(Math.abs(rect.y + rect.height / 2 - (boxBox.y + boxBox.height / 2))).toBeLessThan(8)
    expect(rect.x).toBeGreaterThan(boxBox.x + boxBox.width - 1)
  }
  expectNoRealErrors(errors)
})

test('a phone can reach the quick filters it does not show', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openList(page)

  if (info.project.name !== 'mobile') {
    // Above the breakpoint they are all showing, so there is nothing to reveal.
    await expect(page.getByRole('button', { name: /More filters/ })).toBeHidden()
    expectNoRealErrors(errors)
    return
  }

  // Five boxes stacked is most of a phone screen, so only the ID box stays —
  // and Frappe's own mobile list puts the rest behind a chevron rather than
  // hiding them outright, which is the half we were missing.
  await expect(page.getByPlaceholder('Description')).toBeHidden()
  await page.getByRole('button', { name: 'More filters' }).click()
  await expect(page.getByPlaceholder('Description')).toBeVisible()

  await info.attach(`expanded-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  await page.getByRole('button', { name: 'Fewer filters' }).click()
  await expect(page.getByPlaceholder('Description')).toBeHidden()
  expectNoRealErrors(errors)
})
