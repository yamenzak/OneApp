// Print formats, the letter head and the builder.
//
// The rendering is Frappe's — our layout goes to `PrintFormatGenerator`, the
// same renderer the desk uses — so what this asserts is the seam: that the
// builder writes a format the server accepts, that the format then turns up
// where a record is printed from, and that the preview is the generator's own
// output rather than a drawing of it.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const FORMAT = 'zzmock Task Sheet'

const openSettings = async (page, tab) => {
  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: tab }).click()
}

/**
 * Leave nothing behind: every other spec shares this site.
 *
 * It asks what is there before deleting, because a delete of something absent
 * answers 404 — and the console watcher treats any failed request as a broken
 * page, which is exactly what it is for.
 */
const clean = (page) =>
  page.evaluate(async (format) => {
    const call = (method, body) =>
      fetch(`/api/method/oneapp.oneapp_core.workspace.${method}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': window.csrf_token || '',
        },
        body: JSON.stringify(body),
      }).then((r) => r.json())

    const found = await fetch(
      '/api/method/oneapp.oneapp_core.workspace.print_formats',
    ).then((r) => r.json())
    if ((found.message?.formats || []).some((one) => one.name === format)) {
      await call('delete_print_format', { name: format })
    }
  }, FORMAT)

test('a format drawn in the builder prints the record', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the builder is a three-column desktop surface')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await openSettings(page, 'Print formats')
  await clean(page)

  // The doctypes offered are the ones this workspace's own screens show —
  // never every doctype on the site.
  const records = page.getByRole('combobox', { name: 'Records' })
  await expect(records).toBeVisible()

  await page.getByRole('button', { name: 'New format' }).click()
  await page.getByRole('textbox', { name: 'Name' }).fill(FORMAT)

  // Clicking a palette entry drops it on the page; dragging it is the same
  // path with a different pointer.
  await page.getByRole('button', { name: 'Status', exact: true }).first().click()
  await page.getByRole('button', { name: 'Divider' }).click()

  // The preview is rendered by Frappe against a real record, so a layout the
  // generator cannot walk fails here rather than at the printer.
  await page.getByRole('button', { name: 'Preview' }).click()
  const frame = page.frameLocator('iframe[title="Print preview"]')
  await expect(frame.locator('body')).toContainText(/./, { timeout: 20_000 })

  await page.getByRole('button', { name: 'Back to the canvas' }).click()
  await page.getByRole('button', { name: 'Save', exact: true }).click()

  await expect(page.locator('[data-slot="print-format"]').filter({ hasText: FORMAT })).toBeVisible()

  await clean(page)
  expectNoRealErrors(errors)
})

test('the print dialog on a record offers what the workspace has', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the record header collapses on a phone')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=tasks&record=zzmock-q3')
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })

  // Behind the three dots with the record's other verbs, rather than a
  // permanent printer button beside the step the record is waiting for.
  await page.locator('[data-slot="record-more"]').click()
  await page.getByRole('menuitem', { name: 'Print' }).click()
  // Standard is Frappe's own fallback and is always there, so the picker has
  // something to offer even on a workspace that has drawn nothing.
  await expect(page.getByRole('combobox', { name: 'Format' })).toBeVisible()

  const frame = page.frameLocator('iframe[title="Print preview"]')
  await expect(frame.locator('body')).toContainText(/./, { timeout: 20_000 })

  // Print calls `frame.contentWindow.print()`, which needs the frame to be
  // same-origin. A `sandbox=""` srcdoc frame gets an opaque origin instead, so
  // the button threw a SecurityError and did nothing — reachable from the page
  // is the thing to assert, not the print dialog, which blocks.
  const reachable = await page.evaluate(() => {
    const found = document.querySelector('iframe[title="Print preview"]')
    try {
      return Boolean(found.contentWindow.document)
    } catch {
      return false
    }
  })
  expect(reachable).toBe(true)

  await page.keyboard.press('Escape')
  expectNoRealErrors(errors)
})
