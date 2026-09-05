// Message templates: a reply written once and sent again.
//
// Frappe's `Email Template` does the storing. What this asserts is the pair of
// audiences the panel exists to separate — writing one is an admin deciding
// what the workspace says to a customer, using one is anybody answering an
// email — and that the two ends are the same list rather than an admin screen
// and a picker that drifted apart.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test('a template written in settings is one the composer offers', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'settings tabs scroll on a phone; covered on desktop')
  const errors = collectConsoleErrors(page)
  const title = `Lead time ${Date.now()}`

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: 'Templates' }).click()

  // The fixture's own, and not the six ERPNext and HRMS ship on every site.
  await expect(page.locator('[data-slot="mail-template"]')).toHaveCount(1)
  await expect(page.getByText('Delivery update')).toBeVisible()
  await expect(page.getByText('Interview Reminder')).toHaveCount(0)

  await page.getByRole('button', { name: 'New template' }).first().click()
  const editor = page.getByRole('dialog').filter({ hasText: 'New template' })
  await editor.getByLabel('Name').fill(title)
  await editor.getByLabel('Subject').fill('Two weeks from order')
  await editor.locator('.ProseMirror').click()
  await page.keyboard.type('Our current lead time is two weeks.')
  await editor.getByRole('button', { name: 'Save' }).click()

  await expect(page.getByText(title)).toBeVisible()

  // And it is in the composer, which reads the same list rather than a copy.
  await page.keyboard.press('Escape')
  await page.goto('/one/mail')
  await page.locator('[data-slot="mail-thread"]').first().waitFor({ timeout: 15_000 })
  await page.keyboard.press('c')
  await page.locator('[data-slot="mail-templates"]').click()
  await page.getByRole('menuitem', { name: title }).click()
  await expect(page.getByRole('dialog').getByLabel('Subject')).toHaveValue(
    'Two weeks from order',
  )

  expectNoRealErrors(errors)
})
