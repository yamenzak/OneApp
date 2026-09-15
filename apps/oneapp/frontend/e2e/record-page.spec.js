import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

const openRecord = async (page) => {
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
  await page.getByText('Chase the Halloway invoice').first().click()
  await expect(page.locator('[data-slot="object-pane"]')).toBeVisible()
}

test('a record is the whole area, and has no width to choose', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a phone has one width and always did')
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  // It was a resizable column beside the list, and `docs/DESKTOP.md` says why
  // that stopped paying for itself: a record is a *place* now — a person with a
  // photograph, a day drawn as a day — and every one of those had to survive
  // 480 pixels. So it is the page, at one width, everywhere.
  const pane = await page.locator('[data-slot="object-pane"]').boundingBox()
  const inset = await page.locator('[data-slot="shell-inset"]').boundingBox()
  expect(Math.round(pane.x)).toBe(Math.round(inset.x))
  expect(Math.round(pane.width)).toBe(Math.round(inset.width))

  // Nothing to drag and nothing to choose: the handle is gone and so is the
  // control that offered the other surface.
  await expect(page.locator('[data-slot="record-resizer"]')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Show beside the list' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Fill the window' })).toHaveCount(0)

  await info.attach(`record-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('the list is not gone, it is one press away', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'a phone has one surface and no desk')
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  // What the pane was actually for — mark this one done, glance at the next,
  // come back — is the breadcrumb's job now. `pip.spec.js` is the whole of it;
  // this is the witness that the way in is where the pane used to be.
  const crumb = page.locator('[data-slot="crumb-peek"]')
  await expect(crumb).toBeVisible({ timeout: 20_000 })
  await crumb.click()

  const window_ = page.locator('[data-window="pip"]')
  await expect(window_).toBeVisible()
  const rows = window_.locator('[data-slot="list-row"]')
  await expect(rows.first()).toBeVisible()
  expect(await rows.count()).toBeGreaterThan(1)

  // And over the record rather than beside it: nothing gave up any width.
  const inset = await page.locator('[data-slot="shell-inset"]').boundingBox()
  const pane = await page.locator('[data-slot="object-pane"]').boundingBox()
  expect(Math.round(pane.width)).toBe(Math.round(inset.width))

  expectNoRealErrors(errors)
})

test('on a phone the record is the page', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'this is the phone layout')
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  // No room to keep both, so it does not pretend to: full width, its own
  // header, and the way back at the top of it. A phone always worked this way;
  // what changed is that a desktop does too.
  const pane = await page.locator('[data-slot="object-pane"]').boundingBox()
  const view = page.viewportSize()
  expect(pane.width).toBe(view.width)
  await expect(page.locator('[data-slot="record-resizer"]')).toHaveCount(0)

  // The identity is here rather than in a trail, because the trail is behind
  // the page.
  //
  // `.first()` because the title legitimately appears twice now: once as the
  // record's identity in the pane header, and once inside the Text Editor that
  // is the field it comes from.
  await expect(
    page.locator('[data-slot="object-pane"]').getByText('Chase the Halloway invoice').first(),
  ).toBeVisible()

  await info.attach(`record-page-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  await page.getByRole('button', { name: 'Close the record' }).click()
  await expect(page.locator('[data-slot="object-pane"]')).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('a record is made in a dialog and opens into the page', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  // Creating is the one place a modal is right: nothing behind it to refer to
  // yet, a short decision, and cancelling leaves nothing behind.
  await page.getByRole('button', { name: 'New' }).click()
  const dialog = page.locator('[role="dialog"]')
  await expect(dialog).toBeVisible()

  const made = `ZZ From the dialog ${Date.now() % 10000}`
  await dialog.getByLabel('Description').fill(made)
  // `exact`, because the dialog now offers "Create" *and* "Create another" —
  // a substring match finds both and Playwright's strict mode refuses.
  await dialog.getByRole('button', { name: 'Create', exact: true }).click()

  // And it opens into the record, because the point of making one is to be in
  // it — a dialog that closes onto a list leaves you hunting for the row.
  await expect(dialog).toHaveCount(0)
  const pane = page.locator('[data-slot="object-pane"]')
  await expect(pane).toBeVisible()
  // `toContainText`, not `toHaveValue`: a Text Editor field is a
  // contenteditable rather than an input, so it has no value to read — and the
  // text it holds is wrapped in whatever markup the editor produced.
  await expect(pane.getByLabel('Description')).toContainText(made)
  await expect(page).toHaveURL(/at=record:/)

  // Put the fixture back.
  await page.getByRole('button', { name: 'Close the record' }).click()
  await page.getByPlaceholder('ID').fill('')
  expectNoRealErrors(errors)
})

test('a record says who made it and what is filed against it', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)
  const pane = page.locator('[data-slot="object-pane"]')

  // Who made this and when it last changed: the question every desk sidebar
  // answers, and the one thing on a record that no field carries. On the Meta
  // tab, with the id and the picture, because none of the three is a field on
  // the doctype and a form that ends in its own provenance puts the least
  // interesting thing where the eye stops.
  await pane.getByRole('tab', { name: 'Meta' }).click()
  await expect(pane.getByText('Created by')).toBeVisible()
  await expect(pane.getByText('Administrator').first()).toBeVisible()
  await expect(pane.locator('[data-slot="record-id"]')).toBeVisible()

  // Files are Frappe's own File rows, so a file uploaded through an Attach
  // field and a file dropped on the record are one list rather than two.
  await pane.getByRole('tab', { name: 'Files' }).click()
  await expect(pane.getByText('Nothing is filed against this one yet.')).toBeVisible()
  await expect(pane.getByRole('button', { name: 'Attach a file' })).toBeVisible()

  await info.attach(`files-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test("the doctype's own rules decide what a form shows", async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)
  const pane = page.locator('[data-slot="object-pane"]')

  // `depends_on` — the fixture hides Sender until the task is closed, and the
  // rule is read against the record as it stands rather than as it was saved.
  // Hidden and not absent: unmounting the control would drop what was typed
  // into it the moment the rule flips.
  // Not an exact label: once the rule makes it required its accessible name
  // grows the marker, and matching exactly would report a field that is right
  // there as missing.
  const ruled = pane.getByLabel(/^Sender/)
  await expect(ruled).toBeHidden()
  // `read_only_depends_on` the other way: the reference is a control while the
  // task is open, and becomes a value once it is closed.
  await expect(pane.getByLabel('Reference Type', { exact: true })).toBeEnabled()

  // The Select is frappe-ui's, not a native one: a trigger and a listbox.
  await pane.getByLabel('Status', { exact: true }).click()
  await page.getByRole('option', { name: 'Closed', exact: true }).click()

  // It appears the moment the field it depends on says so, without a save.
  await expect(ruled).toBeVisible()
  // And `mandatory_depends_on` marks it the way `reqd` would — the control
  // reads one flag, so the doctype's two answers become one here.
  await expect(ruled).toHaveAccessibleName('Sender (required)')
  // And a locked field is not a disabled control — §B5. It is the value, as
  // text, with no box and no placeholder: there is nothing left to type into,
  // which is what the rule means and what a greyed-out input never said.
  await expect(pane.getByLabel('Reference Type', { exact: true })).toHaveCount(0)
  await expect(
    pane.locator('[data-slot="read-value"]').filter({ hasText: 'Reference Type' }),
  ).toBeVisible()

  // Put it back without saving: closing the record throws the change away,
  // which is what not pressing Save means.
  await page.getByRole('button', { name: 'Close the record' }).click()
  expectNoRealErrors(errors)
})
