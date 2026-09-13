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

test('the trail is the workspace, the space, and the screen', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock?screen=notes')

  // §C1's shape. The root is the *workspace* — it used to be the space, and
  // every other surface's root used to be itself, so there was no shared
  // first crumb and no way from Mail back to the workspace in one click.
  const trail = page.getByRole('navigation', { name: 'Breadcrumb' })
  await expect(trail.getByRole('link', { name: /home$/ })).toBeVisible()
  await expect(trail.getByText('MockSpace')).toBeVisible()
  await expect(trail.getByText('Notes')).toBeVisible()
  // The view is beside the trail rather than the last crumb in it: it is a
  // control, and a crumb is a place.
  await expect(page.getByRole('group', { name: 'Saved views' })).toContainText('List')

  // The space's crumb goes to its first screen.
  await trail.getByRole('link', { name: 'MockSpace' }).click()
  await expect(page).toHaveURL(/screen=tasks/)

  await info.attach(`crumbs-${info.project.name}`, {
    body: await page.screenshot(),
    contentType: 'image/png',
  })
  expectNoRealErrors(errors)
})

/**
 * The same first crumb, everywhere — `docs/UNIFICATION.md` §C1.
 *
 * Nine surfaces built their own trail and disagreed about its root: the
 * engine's was the space, the Drive's was Files, Mail's was Mail, the
 * assistant's was its own name, and OneDoc's was wherever you happened to
 * have come from. This is the assertion that makes the fix a fact rather
 * than nine coincidences: walk the workspace-level places and find the same
 * house at the front of each, going to the same address.
 */
test('every surface opens with the same root, and it goes home', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  for (const where of ['/one/space/zzmock', '/one/files', '/one/mail', '/one/calendar', '/one/account']) {
    await page.goto(where)
    const trail = page.getByRole('navigation', { name: 'Breadcrumb' })
    const root = trail.getByRole('link', { name: /home$/ })
    await expect(root, `${where} has no root crumb`).toBeVisible()
    await expect(root, `${where}'s root is not a link home`).toHaveAttribute('href', '/one/')
  }

  // And it is a link somebody can actually press.
  await page.getByRole('navigation', { name: 'Breadcrumb' })
    .getByRole('link', { name: /home$/ })
    .click()
  await expect(page).toHaveURL(/\/one\/$/)

  expectNoRealErrors(errors)
})

test('an open record is in the URL, and in the trail', async ({ page }, info) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  await page.getByText('Chase the Halloway invoice').first().click()
  await expect(page.locator('[data-slot="record-pane"]')).toBeVisible()
  await expect(page).toHaveURL(/at=record:/)

  // Where the record's trail is, which is not the same place on both. On a
  // desktop the chrome splits when a record opens — the left half keeps saying
  // where you are in the space and a second half, the width of the pane and
  // sitting over it, says which record. A phone has no pane and no room for
  // two halves, so the record goes into the one trail there is.
  //
  // Located by slot rather than by role either way, because a modal takes the
  // rest of the page out of the accessibility tree.
  const trail = page.locator(
    info.project.name === 'mobile' ? '[data-slot="breadcrumb"]' : '[data-slot="pane-header"]',
  )
  await expect(trail).toContainText('Chase the Halloway invoice')
  await expect(trail).toContainText('zzmock-halloway')

  // Two lines under one face, and the status beside the name: "where does this
  // stand" is the second thing anybody asks about a record. Which field that
  // is comes from the manifest; the colour is ToDo's own.
  await expect(trail.locator('[data-slot="record-status"]')).toHaveText('Open')
  const name = await trail.getByText('Chase the Halloway invoice').boundingBox()
  const id = await trail.getByText('zzmock-halloway').boundingBox()
  expect(id.y).toBeGreaterThan(name.y + name.height - 1)
  expect(Math.abs(id.x - name.x)).toBeLessThan(2)

  // A record is a link: a reload comes back to it, without the list it was
  // opened from.
  await page.reload()
  await expect(page.locator('[data-slot="record-pane"]')).toBeVisible()

  // And closing it puts the URL back. The X and not Escape: a pane is not
  // modal, and the controls inside it do not mark their own Escape as handled
  // — so closing a link picker with it closed the record underneath.
  await page.getByRole('button', { name: 'Close the record' }).click()
  await expect(page.locator('[data-slot="record-pane"]')).toHaveCount(0)
  await expect(page).not.toHaveURL(/at=record:/)
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

  // One row saying where you are, and a menu behind it — a list of every
  // space, most of which you are not in, is a list to read rather than a
  // control.
  const switcher = page.getByRole('button', { name: 'MockSpace' })
  await expect(switcher).toBeVisible()
  // The sheet is the phone's navigation, so it lists every screen — not only
  // the ones the bottom bar had no room for.
  await expect(page.getByRole('link', { name: 'Tasks' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Notes' })).toBeVisible()

  await switcher.click()
  await page.getByRole('menuitem', { name: 'All spaces' }).click()
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
    page.locator('[data-slot="record-pane"]').getByText('Priority', { exact: true }),
  ).toBeVisible()
  await info.attach(`record-${info.project.name}`, {
    body: await page.screenshot(), contentType: 'image/png' })

  // And it saves. Worth exercising rather than assuming: the rename left this
  // calling a `workspace.saveAppRecord` that no longer existed, so Save threw
  // where nothing was watching — a dialog test that only reads the form would
  // never have noticed.
  const dialog = page.locator('[data-slot="record-pane"]')
  // The fields are in the pane; Save is not. A record's actions teleport into
  // the top bar with the rest of the page's header, so a pane-scoped lookup
  // waits out the test on a button that is on screen and outside the pane.
  const save = page.getByRole('button', { name: 'Save', exact: true })
  const changed = `Chase the Halloway invoice ${Date.now() % 1000}`
  await dialog.getByLabel('Description').fill(changed)
  await save.click()

  // Save going away is the round trip landing: it is offered only while the
  // form holds something the server has not seen. Waited for rather than
  // assumed, because the second edit below would otherwise race the refetch —
  // type into the form, have the arriving record overwrite it, and press a
  // button that is no longer there.
  await expect(save).toHaveCount(0)

  // The pane stays open — a record you just saved is a record you are still
  // reading — and what it shows is what came back from the server rather than
  // what was typed into it.
  // `toContainText`, not `toHaveValue`: a Text Editor field is a
  // contenteditable rather than an input, so it has no value to read — and the
  // text it holds is wrapped in whatever markup the editor produced.
  await expect(dialog.getByLabel('Description')).toContainText(changed)

  // Put it back, so the next run starts where this one did.
  await dialog.getByLabel('Description').fill(SEEDED)
  await save.click()
  await expect(save).toHaveCount(0)
  await expect(dialog.getByLabel('Description')).toContainText(SEEDED)
  expectNoRealErrors(errors)
})
