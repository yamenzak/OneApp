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

test('a view can carry an icon, and it is the offered set or an emoji', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.getByText('Halloway').first()).toBeVisible()

  // The seeded "Open work" view has one, and it reaches both places a view is
  // named: the sidebar and the switcher in the breadcrumb line.
  const sidebar = page.locator('[data-slot="sidebar"]')
  if (await sidebar.count()) {
    await expect(sidebar.locator('.lucide-clock')).toBeVisible()
  }

  await page.getByRole('group', { name: 'Saved views' }).getByRole('button').click()
  await page.getByRole('menuitem', { name: 'Open work' }).click()
  await expect(
    page.getByRole('group', { name: 'Saved views' }).locator('.lucide-clock'),
  ).toBeVisible()

  // The picker offers the set the build can actually draw — an arbitrary
  // lucide name emits no CSS — plus a box for an emoji, which needs none.
  await page.getByRole('group', { name: 'Saved views' }).getByRole('button').click()
  await page.getByRole('menuitem', { name: 'Rename' }).click()
  await page.getByRole('button', { name: /Change the icon|Pick an icon/ }).click()
  await expect(page.getByRole('button', { name: 'shield', exact: true })).toBeVisible()
  await expect(page.getByPlaceholder('📦')).toBeVisible()
  expectNoRealErrors(errors)
})

test('an unsaved change saves into the view you are in', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  // On the screen itself, the change goes into this person's own default.
  await page.getByRole('columnheader', { name: 'Status' }).click()
  await expect(page.getByRole('button', { name: 'Save this screen' })).toBeVisible()
  await page.getByRole('button', { name: 'Discard these changes' }).click()
  await expect(page.getByRole('button', { name: 'Save this screen' })).toHaveCount(0)

  // In a named view you may write, it goes into that view instead — which is
  // the line Frappe CRM draws too, and the alternative is a Save that either
  // makes a silent private copy or quietly rewrites what others are using.
  await page.getByRole('group', { name: 'Saved views' }).getByRole('button').click()
  await page.getByRole('menuitem', { name: 'High priority' }).click()
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
  await page.getByRole('columnheader', { name: 'Status' }).click()
  await expect(page.getByRole('button', { name: 'Save changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Discard these changes' }).click()
  await expect(page.getByRole('button', { name: 'Save changes' })).toHaveCount(0)
  expectNoRealErrors(errors)
})
