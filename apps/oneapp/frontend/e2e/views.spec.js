import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

// The whole arc: make a view, come back to it, and take it away again.
test('a named view is made, opened and deleted', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.getByText('Halloway').first()).toBeVisible()

  // The switcher opens on the *view type*, because nothing this person saved
  // is what the screen opens with — and the crumb before it already says which
  // screen this is, so repeating the screen's name here would be one word
  // twice.
  const views = page.getByRole('group', { name: 'Saved views' })
  await expect(views.getByRole('button', { name: /^List/ })).toBeVisible()
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
  await expect(views.getByRole('button', { name: /^List/ })).toBeVisible()
  expectNoRealErrors(errors)
})
