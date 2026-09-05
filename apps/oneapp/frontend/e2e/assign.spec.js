// Assignment: who a record is for.
//
// Frappe's own model, unchanged — `_assign` is a list of user ids on the
// document and a ToDo sits beside each one, so assigning is how a record
// reaches somebody's own list rather than only their avatar. What is ours is
// that it is a row of faces on the record rather than a field on the form:
// assignment is not on the doctype, there is no column for it, and it is a
// thing you do to a record.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * Open the fixture and go to the tab assignment lives on.
 *
 * One place, not two: the header used to carry the same control, which made it
 * the eighth button in a row beside the one that mattered. "Who is this for" is
 * a thing you set, so it sits with the other three of those — attach, tag,
 * share — on Meta.
 */
const openTask = async (page) => {
  await page.goto('/one/space/zzmock?screen=tasks&record=zzmock-halloway')
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })
  await page.getByRole('tab', { name: 'Meta' }).click()
  await page.locator('[data-slot="assign"]').waitFor({ timeout: 15_000 })
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a record can be assigned, and says so in faces', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone opens a record as a page')
  const errors = collectConsoleErrors(page)
  await openTask(page)

  const control = page.locator('[data-slot="assign"]')
  // Nobody yet: the outline of a person, which is the affordance the desk uses.
  await expect(control.locator('.lucide-user-round-plus')).toBeVisible()

  await control.click()
  // The list is fetched on the first open rather than with the record — a
  // workspace's user list is not part of reading one row.
  await page.getByRole('option', { name: /Administrator/ }).click()

  // A face, not an email address.
  await expect(control.locator('.lucide-user-round-plus')).toHaveCount(0)
  await expect(control.locator('[data-slot="avatar"], img, span').first()).toBeVisible()

  // And it survives a reload, because it is on the document rather than in
  // this component.
  await page.keyboard.press('Escape')
  await page.reload()
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })
  await page.getByRole('tab', { name: 'Meta' }).click()
  await page.locator('[data-slot="assign"]').waitFor({ timeout: 15_000 })
  await expect(
    page.locator('[data-slot="assign"]').locator('.lucide-user-round-plus'),
  ).toHaveCount(0)

  // Put the fixture back.
  await page.locator('[data-slot="assign"]').click()
  await page.getByRole('option', { name: /Administrator/ }).click()
  await page.keyboard.press('Escape')
  await expect(
    page.locator('[data-slot="assign"]').locator('.lucide-user-round-plus'),
  ).toBeVisible()

  // And take away what assigning left behind.
  //
  // Frappe's assignment *is* a ToDo — that is the whole point of it, and it is
  // why the record turns up in somebody's own list — but this screen lists
  // ToDo, so every run of this test adds two rows to the fixture it shares
  // with every other spec. Unassigning cancels them rather than deleting them,
  // so they are deleted here.
  await sweepAssignments(page)
  expectNoRealErrors(errors)
})

const sweepAssignments = async (page) =>
  page.evaluate(async () => {
    const ask = async (method, options) => {
      const res = await fetch(`/api/method/oneapp.oneapp_core.spaceview.${method}`, options)
      return (await res.json()).message
    }
    const page1 = await ask(
      'rows?space_code=zzmock&screen=tasks&limit=500',
      { headers: { Accept: 'application/json' } },
    )
    const doomed = (page1?.rows || [])
      .filter((row) => String(row.description || '').includes('Assignment for'))
      .map((row) => row.name)
    if (!doomed.length) return 0
    await ask('remove', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-Frappe-CSRF-Token': window.csrf_token,
      },
      body: JSON.stringify({ space_code: 'zzmock', screen: 'tasks', name: doomed }),
    })
    return doomed.length
  })
