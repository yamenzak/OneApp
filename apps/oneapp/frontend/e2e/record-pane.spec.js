import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

const openRecord = async (page) => {
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
  await page.getByText('Chase the Halloway invoice').first().click()
  await expect(page.locator('[data-slot="record-pane"]')).toBeVisible()
}

test('the list is still there beside the record', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'there is no room to keep both on a phone')
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  // The whole point of a pane over a dialog: a record is something you read
  // *against* the list — mark this one done, glance at the next, come back.
  const rows = page.locator('[data-slot="list-row"]')
  await expect(rows.first()).toBeVisible()
  expect(await rows.count()).toBeGreaterThan(1)

  // Beside, not over. The row's own box is wider than what is on screen — the
  // grid scrolls sideways inside its pane — so what is asserted is that the
  // list starts to the left of the record and the record runs to the edge.
  const list = await rows.first().boundingBox()
  const pane = await page.locator('[data-slot="record-pane"]').boundingBox()
  expect(list.x).toBeLessThan(pane.x)
  expect(Math.round(pane.x + pane.width)).toBe(page.viewportSize().width)

  await info.attach(`pane-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('the pane can be resized, and it stays that way', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the pane is the page there, and pages have one width')
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  const pane = page.locator('[data-slot="record-pane"]')
  const before = (await pane.boundingBox()).width

  // The keyboard, not a drag: the same handle, and the half of it that a
  // pointer test cannot cover. Left is wider — the handle is on the pane's
  // left edge.
  const handle = page.locator('[data-slot="record-resizer"]')
  await handle.focus()
  await page.keyboard.press('Shift+ArrowLeft')
  await expect.poll(async () => (await pane.boundingBox()).width).toBeGreaterThan(before)

  // Remembered in this browser, because how wide somebody likes a pane is a
  // property of the screen they are sitting at.
  const widened = (await pane.boundingBox()).width
  await page.reload()
  await expect(pane).toBeVisible()
  expect(Math.abs((await pane.boundingBox()).width - widened)).toBeLessThan(2)
  expectNoRealErrors(errors)
})

test('on a phone the record is the page', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', 'this is the phone layout')
  const errors = collectConsoleErrors(page)
  await openRecord(page)

  // No room to keep both, so it does not pretend to: full width, its own
  // header, and the way back at the top of it.
  const pane = await page.locator('[data-slot="record-pane"]').boundingBox()
  const view = page.viewportSize()
  expect(pane.width).toBe(view.width)
  await expect(page.locator('[data-slot="record-resizer"]')).toHaveCount(0)

  // The identity is here rather than in a trail, because the trail is behind
  // the page.
  await expect(
    page.locator('[data-slot="record-pane"]').getByText('Chase the Halloway invoice'),
  ).toBeVisible()

  await info.attach(`record-page-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })

  await page.getByRole('button', { name: 'Close the record' }).click()
  await expect(page.locator('[data-slot="record-pane"]')).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('a record is made in a dialog and opens into the pane', async ({ page }) => {
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
  await dialog.getByRole('button', { name: 'Create' }).click()

  // And it opens into the record, because the point of making one is to be in
  // it — a dialog that closes onto a list leaves you hunting for the row.
  await expect(dialog).toHaveCount(0)
  const pane = page.locator('[data-slot="record-pane"]')
  await expect(pane).toBeVisible()
  await expect(pane.getByLabel('Description')).toHaveValue(made)
  await expect(page).toHaveURL(/record=/)

  // Put the fixture back.
  await page.getByRole('button', { name: 'Close the record' }).click()
  await page.getByPlaceholder('ID').fill('')
  expectNoRealErrors(errors)
})

test('a record says who made it and what is filed against it', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openRecord(page)
  const pane = page.locator('[data-slot="record-pane"]')

  // Who made this and when it last changed: the question every desk sidebar
  // answers, and the one thing on a record that no field carries.
  await expect(pane.getByText('Created by')).toBeVisible()
  await expect(pane.getByText('Administrator').first()).toBeVisible()

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
  const pane = page.locator('[data-slot="record-pane"]')

  // `depends_on` — the fixture hides Sender until the task is closed, and the
  // rule is read against the record as it stands rather than as it was saved.
  // Hidden and not absent: unmounting the control would drop what was typed
  // into it the moment the rule flips.
  // Not an exact label: once the rule makes it required its accessible name
  // grows the marker, and matching exactly would report a field that is right
  // there as missing.
  const ruled = pane.getByLabel(/^Sender/)
  await expect(ruled).toBeHidden()
  // `read_only_depends_on` the other way: the reference is editable while it
  // is open.
  await expect(pane.getByLabel('Reference Type', { exact: true })).toBeEnabled()

  // The Select is frappe-ui's, not a native one: a trigger and a listbox.
  await pane.getByLabel('Status', { exact: true }).click()
  await page.getByRole('option', { name: 'Closed', exact: true }).click()

  // It appears the moment the field it depends on says so, without a save.
  await expect(ruled).toBeVisible()
  // And `mandatory_depends_on` marks it the way `reqd` would — the control
  // reads one flag, so the doctype's two answers become one here.
  await expect(ruled).toHaveAccessibleName('Sender (required)')
  await expect(pane.getByLabel('Reference Type', { exact: true })).toBeDisabled()

  // Put it back without saving: closing the record throws the change away,
  // which is what not pressing Save means.
  await page.getByRole('button', { name: 'Close the record' }).click()
  expectNoRealErrors(errors)
})
