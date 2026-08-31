// A Link fills in the fields that say they come from it.
//
// `fetch_from` on a docfield is `<link fieldname>.<field on the target>`, and
// Frappe applies it on save whatever wrote the record. So this changes no
// outcome — only when you see it. Before, the field showed a note saying "From
// Assigned By", stayed empty while you filled the form, and was quietly
// overwritten on save by the value it was always going to hold. Somebody who
// typed into it watched their own text disappear.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const DIALOG = '[data-oneapp="form-dialog"]'

test('choosing a link fills the field that fetches from it', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'one viewport is enough for a round trip')
  const errors = collectConsoleErrors(page)
  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock')

  const button = page.getByRole('button', { name: 'New', exact: true }).first()
  await button.waitFor({ timeout: 15_000 })
  await button.click()
  const dialog = page.locator(DIALOG)
  await expect(dialog).toBeVisible()

  // ToDo declares `assigned_by_full_name` as `assigned_by.full_name`. It is the
  // one real fetch_from on this screen, and it is Frappe's own — which is the
  // point: nothing about this had to be declared in our manifest.
  // `exact`, or this also matches the very field it fills in.
  const target = dialog.getByLabel('Assigned By', { exact: true })
  await expect(target, 'the mock screen no longer shows Assigned By').toBeVisible()
  await target.click()
  await page.waitForTimeout(400)

  const option = page.locator('[role="option"]:visible').first()
  if (!(await option.count())) test.skip(true, 'no user to pick on this site')
  const chosen = (await option.innerText()).trim()
  await option.click()

  // The round trip is a request, so the value arrives after the pick rather
  // than with it.
  const filled = dialog.getByLabel('Assigned By Full Name', { exact: true })
  await expect(filled).not.toHaveValue('', { timeout: 5_000 })
  const got = await filled.inputValue()
  expect(chosen, `the fetched name ${got} is not part of the record picked`)
    .toContain(got)

  expectNoRealErrors(errors)
})
