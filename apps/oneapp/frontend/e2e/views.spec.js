import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

// The whole arc: make a view, come back to it, and take it away again.
test('a named view is made, opened and deleted', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zztasks')
  await expect(page.getByText('Halloway').first()).toBeVisible()

  // The switcher opens on the screen's own name, because nothing is saved.
  const views = page.getByRole('group', { name: 'Saved views' })
  await expect(views.getByRole('button', { name: /^Open/ })).toBeVisible()
  await views.getByRole('button').click()
  await page.getByRole('menuitem', { name: 'Save as a new view' }).click()

  await page.getByLabel('Name').fill('Only the urgent')
  await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click()

  // It is the view we are in now, and the URL says which.
  await expect(views.getByRole('button', { name: /^Only the urgent/ })).toBeVisible()
  await expect(page).toHaveURL(/layout=/)

  // A reload lands back in it — a view is a link.
  await page.reload()
  await expect(views.getByRole('button', { name: /^Only the urgent/ })).toBeVisible()

  await views.getByRole('button').click()
  await page.getByRole('menuitem', { name: 'Delete this view' }).click()
  await expect(views.getByRole('button', { name: /^Open/ })).toBeVisible()
  expectNoRealErrors(errors)
})
