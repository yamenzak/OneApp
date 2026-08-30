import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a space declared as a manifest renders its screens', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')

  console.log('BODY:', (await page.locator('body').innerText()).slice(0, 700))
  await info.attach(`app-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

  // Rows from the tenant site, through the screen.
  await expect(page.getByText('Halloway').first()).toBeVisible()

  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
  expectNoRealErrors(errors)
})

test('the space brings its own navigation', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')

  // Both declared screens, without a line of SPA code naming either — and two
  // different doctypes under one space, which is the point: a space is not a
  // doctype, and a screen is one item in its navigation.
  await expect(page.getByText('Tasks', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Notes', { exact: true }).first()).toBeVisible()

  await page.getByText('Notes', { exact: true }).first().click()
  await expect(page.getByText('Van hire terms').first()).toBeVisible()

  await info.attach(`nav-${info.project.name}`, {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })
  expectNoRealErrors(errors)
})

test('a screen expands to the ways it can be opened', async ({ page }, info) => {
  // The sidebar is the desktop's answer; a phone has the switcher in the
  // breadcrumb line instead, and no sidebar to expand.
  test.skip(info.project.name === 'mobile', 'there is no sidebar on a phone')
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')

  // Two groups under one screen: how it can be drawn, then the views somebody
  // named. Neither is written into the SPA — the view types come off the
  // screen's manifest and the views out of the tenant's own saved-view table.
  const sidebar = page.locator('[data-slot="sidebar"]')
  await expect(sidebar.getByRole('link', { name: 'List' })).toBeVisible()
  await expect(sidebar.getByText('Views')).toBeVisible()
  await expect(sidebar.getByRole('link', { name: 'High priority' })).toBeVisible()
  await expect(sidebar.getByRole('link', { name: 'Open work' })).toBeVisible()

  // Notes declares one view type and has no saved views, so there is nothing
  // to expand and no chevron claiming otherwise.
  await expect(sidebar.getByRole('button', { name: 'Ways to see Notes' })).toHaveCount(0)

  await sidebar.getByRole('link', { name: 'High priority' }).click()
  // The layout is in the URL, so a view is a link somebody can send.
  await expect(page).toHaveURL(/layout=/)
  // And it is what the breadcrumb says you are looking at.
  await expect(page.getByText('High priority').first()).toBeVisible()

  await info.attach(`sidebar-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('a record opens and saves', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')

  await page.getByText('Halloway').first().click()

  // Labels and a Select's options come from the doctype, not from the manifest.
  // Scoped to the dialog: the quick filter row above the list has a box with
  // the same label, and on a phone that one is hidden.
  await expect(
    page.locator('[role="dialog"]').getByText('Priority', { exact: true }),
  ).toBeVisible()
  await info.attach(`record-${info.project.name}`, {
    body: await page.screenshot(), contentType: 'image/png' })
  expectNoRealErrors(errors)
})
