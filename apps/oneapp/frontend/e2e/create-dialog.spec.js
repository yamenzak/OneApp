// The create dialog: it keeps what you typed, and Create is always reachable.
//
// Two failures, one of them reported and one found while looking for it.
//
// The reported one is the dialog closing on its own and taking the form with
// it. The mechanism was never pinned down — driving Enter, paste, every Select,
// the date picker and the link picker did not reproduce it — but the dialog was
// dismissible, so Escape and anything reaching reka-ui's `interact-outside`
// discarded a filled-in form without asking. It is not dismissible while it
// holds something now, whatever the trigger was.
//
// The other: frappe-ui's Dialog renders `#actions` as an ordinary block after
// the content, inside a `fixed inset-0 overflow-y-auto` scroll container. On a
// doctype with twenty fields, Create was below the fold.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const DIALOG = '[data-oneapp="form-dialog"]'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

// The doctype's own required field, and a real text one. Not "the first text
// input": that is the Due Date box, and filling it with prose produced the year
// 93624 and three tests that failed for a reason that had nothing to do with
// what they were testing.
const BODY_FIELD = 'Description'

async function openNew(page) {
  await page.goto('/one/space/zzmock')
  const button = page.getByRole('button', { name: 'New', exact: true }).first()
  await button.waitFor({ timeout: 15_000 })
  await button.click()
  await expect(page.locator(DIALOG)).toBeVisible()
}

test('Create is on screen without scrolling the form', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await openNew(page)
  const dialog = page.locator(DIALOG)
  const create = dialog.getByRole('button', { name: 'Create', exact: true })

  await expect(create).toBeInViewport()

  // And it stays there once the body has been scrolled to the end, which is the
  // state the old dialog could not reach: there, the button had scrolled away.
  const body = dialog.locator('div.overflow-y-auto').first()
  await body.evaluate((el) => el.scrollTo(0, el.scrollHeight))
  await page.waitForTimeout(300)
  await expect(create).toBeInViewport()
  await info.attach(`create-${info.project.name}`, {
    body: await page.screenshot(), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

test('a filled-in form does not vanish on Escape or an outside click', async ({ page }) => {
  await openNew(page)
  const dialog = page.locator(DIALOG)
  await dialog.getByLabel(BODY_FIELD).fill('worth keeping')

  await page.keyboard.press('Escape')
  await page.waitForTimeout(400)
  await expect(dialog, 'Escape discarded a filled-in form').toBeVisible()

  // The backdrop: the one place a click is unambiguously outside the content.
  await page.mouse.click(4, 4)
  await page.waitForTimeout(400)
  await expect(dialog, 'a click outside discarded a filled-in form').toBeVisible()

  // The typed value survived both.
  await expect(dialog.getByLabel(BODY_FIELD)).toContainText('worth keeping')
})

test('an empty form still closes freely, on one Escape', async ({ page }) => {
  // A dialog opened by mistake should not argue about it.
  //
  // "One" is load-bearing. The close button is the first tabbable thing in the
  // dialog, so reka's FocusScope lands on it — and while it carried a tooltip,
  // that tooltip opened on focus as its own dismissable layer and ate the first
  // Escape. The dialog took two presses to close and nothing said why.
  await openNew(page)
  await page.keyboard.press('Escape')
  await expect(page.locator(DIALOG)).toBeHidden()
})

test('the explicit close always works, dirty or not', async ({ page }) => {
  await openNew(page)
  const dialog = page.locator(DIALOG)
  await dialog.getByLabel(BODY_FIELD).fill('discard me')
  await dialog.getByRole('button', { name: /close/i }).first().click()
  await expect(dialog).toBeHidden()
})

test('Create another keeps the dialog and empties the form', async ({ page }) => {
  await openNew(page)
  const dialog = page.locator(DIALOG)
  const box = dialog.getByLabel(BODY_FIELD)
  await box.fill(`probe ${Date.now() % 100000}`)

  await dialog.getByRole('button', { name: 'Create another' }).click()
  await expect(dialog, 'Create another closed the dialog').toBeVisible()
  await expect(box, 'the form kept the last record, so the next one is a copy')
    .not.toContainText('probe')
  // ...and it did not navigate into the record it just made.
  await expect(page).not.toHaveURL(/[?&]record=/)
})
