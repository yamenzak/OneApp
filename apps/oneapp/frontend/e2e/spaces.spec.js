import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

// The seeded row this file points at, by its own words.
const SEEDED = 'Chase the Halloway invoice'

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

test('a sub-item says it is active by weight, not by a second pill', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'there is no sidebar on a phone')
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')

  const sidebar = page.locator('[data-slot="sidebar"]')
  const screen = sidebar.locator('[data-slot="sidebar-item"]', { hasText: 'Tasks' }).first()
  const view = sidebar.locator('[data-slot="sidebar-item"]', { hasText: 'List' }).first()

  // The fill belongs to the screen. A second one nested under it competes with
  // its parent for the eye rather than saying something more.
  await expect(screen).toHaveAttribute('data-state', 'active')
  await expect(view).toHaveAttribute('data-state', 'inactive')
  // The sub-item still says it is the one you are looking at.
  await expect(view.locator('.font-medium')).toBeVisible()
  expectNoRealErrors(errors)
})

test('the trail is a house, a screen, and what you are looking at', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock?screen=notes')

  // Frappe CRM's shape. The space is the house's tooltip rather than a word:
  // the rail already says which space this is, and the line has one place to
  // spend.
  const trail = page.getByRole('navigation', { name: 'Breadcrumb' })
  await expect(page.getByRole('link', { name: 'MockSpace home' })).toBeVisible()
  await expect(trail.getByText('Notes')).toBeVisible()
  // The last crumb is the view, not the screen's name a second time.
  await expect(page.getByRole('group', { name: 'Saved views' })).toContainText('List')

  // The house goes to the space's first screen.
  await page.getByRole('link', { name: 'MockSpace home' }).click()
  await expect(page).toHaveURL(/screen=tasks/)

  await info.attach(`crumbs-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

test('an open record is in the URL, and in the trail', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  await page.getByText('Chase the Halloway invoice').first().click()
  await expect(page.locator('[role="dialog"]')).toBeVisible()
  await expect(page).toHaveURL(/record=/)

  // Located by its slot, not its role: a modal takes the rest of the page out
  // of the accessibility tree, so while the dialog is open the trail is there
  // to read and not to reach.
  const trail = page.locator('[data-slot="breadcrumb"]')
  await expect(trail).toContainText('Chase the Halloway invoice')
  await expect(trail).toContainText('kosp1csf48')

  // A record is a link: a reload comes back to it, without the list it was
  // opened from.
  await page.reload()
  await expect(page.locator('[role="dialog"]')).toBeVisible()

  // And closing it puts the URL back.
  await page.keyboard.press('Escape')
  await expect(page.locator('[role="dialog"]')).toHaveCount(0)
  await expect(page).not.toHaveURL(/record=/)
  expectNoRealErrors(errors)
})

test('the phone can switch space from the More sheet', async ({ page }, info) => {
  // A desktop switches space on the rail; a phone has no rail, so this sheet
  // is the only way — and it was hidden entirely on a workspace with one
  // space, which is exactly the workspace that needs the way out to find a
  // second one.
  test.skip(info.project.name !== 'mobile', 'the sheet is the phone shell')
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  await page.getByRole('button', { name: 'More', exact: true }).click()
  await expect(page.getByText('Spaces', { exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: 'MockSpace' })).toBeVisible()

  await page.getByRole('link', { name: 'All spaces' }).click()
  // The launcher, which is where a space that is not on the bar gets opened.
  await expect(page).toHaveURL(/\/one\/?$/)
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

  // And it saves. Worth exercising rather than assuming: the rename left this
  // calling a `workspace.saveAppRecord` that no longer existed, so Save threw
  // where nothing was watching — a dialog test that only reads the form would
  // never have noticed.
  const dialog = page.locator('[role="dialog"]')
  const changed = `Chase the Halloway invoice ${Date.now() % 1000}`
  await dialog.getByLabel('Description').fill(changed)
  await dialog.getByRole('button', { name: 'Save' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText(changed).first()).toBeVisible()

  // Put it back, so the next run starts where this one did.
  await page.getByText(changed).first().click()
  await page.locator('[role="dialog"]').getByLabel('Description').fill(SEEDED)
  await page.locator('[role="dialog"]').getByRole('button', { name: 'Save' }).click()
  expectNoRealErrors(errors)
})
