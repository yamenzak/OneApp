import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

const switcher = (page) => page.getByRole('group', { name: 'Saved views' })

// Opening the menu, and then one view's own submenu. Every view is a submenu
// now — this menu is the only place a view is managed, so a row that only
// opened one left renaming any other view unreachable.
const openMenu = async (page) => {
  await switcher(page).getByRole('button').click()
  await expect(page.getByRole('menuitem', { name: 'Save as a new view' })).toBeVisible()
}

const openSubmenu = async (page, view) => {
  await openMenu(page)
  await page.getByRole('menuitem', { name: view }).click()
}

// The whole arc: make a view, come back to it, and take it away again.
test('a named view is made, opened and deleted', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.getByText('Halloway').first()).toBeVisible()

  // The switcher opens on the *view type*, because nothing this person saved
  // is what the screen opens with — and the crumb before it already says which
  // screen this is, so repeating the screen's name here would be one word
  // twice.
  await expect(switcher(page).getByRole('button', { name: /^List/ })).toBeVisible()
  await openMenu(page)
  await page.getByRole('menuitem', { name: 'Save as a new view' }).click()

  await page.getByLabel('Name').fill('Only the urgent')
  await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click()

  // It is the view we are in now, and the URL says which.
  await expect(switcher(page).getByRole('button', { name: /^Only the urgent/ })).toBeVisible()
  await expect(page).toHaveURL(/layout=/)

  // A reload lands back in it — a view is a link.
  await page.reload()
  await expect(switcher(page).getByRole('button', { name: /^Only the urgent/ })).toBeVisible()

  await openSubmenu(page, 'Only the urgent')
  await page.getByRole('menuitem', { name: 'Delete it' }).click()
  await expect(switcher(page).getByRole('button', { name: /^List/ })).toBeVisible()
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

  await openSubmenu(page, 'Open work')
  await page.getByRole('menuitem', { name: 'Open it' }).click()
  await expect(switcher(page).locator('.lucide-clock')).toBeVisible()

  // The picker offers the set the build can actually draw — an arbitrary
  // lucide name emits no CSS — plus a box for an emoji, which needs none.
  await openSubmenu(page, 'Open work')
  await page.getByRole('menuitem', { name: 'Rename' }).click()
  await page.getByRole('button', { name: /Change the icon|Pick an icon/ }).click()
  await expect(page.getByRole('button', { name: 'shield', exact: true })).toBeVisible()
  await expect(page.getByPlaceholder('📦')).toBeVisible()

  // Grouped, and searchable by what an icon is *for* rather than by its lucide
  // name. Nobody looking for the sales app types "chart line".
  await expect(page.getByRole('heading', { name: 'Money' })).toBeVisible()
  await page.getByPlaceholder('Search').fill('reports')
  await expect(page.getByRole('button', { name: 'chart line', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'shield', exact: true })).toHaveCount(0)

  // And a word nothing answers to says so rather than showing an empty grid.
  await page.getByPlaceholder('Search').fill('zzzz')
  await expect(page.getByText('No icon by that name')).toBeVisible()
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
  await openSubmenu(page, 'High priority')
  await page.getByRole('menuitem', { name: 'Open it' }).click()
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
  await page.getByRole('columnheader', { name: 'Status' }).click()
  await expect(page.getByRole('button', { name: 'Save changes' })).toBeVisible()
  await page.getByRole('button', { name: 'Discard these changes' }).click()
  await expect(page.getByRole('button', { name: 'Save changes' })).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('an unsaved change can be put into a view you are not in', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  // Nothing to save into until there is something unsaved.
  await openSubmenu(page, 'Open work')
  await expect(page.getByRole('menuitem', { name: 'Save the changes here' })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')

  // With a change on screen, every view you may write offers to take it —
  // which is what "either override an existing view or make a new one" means
  // when the view you want is not the one you are looking at.
  await page.getByRole('columnheader', { name: 'Status' }).click()
  await openSubmenu(page, 'Open work')
  await page.getByRole('menuitem', { name: 'Save the changes here' }).click()

  // Saving into it opens it: the change is now that view's, and staying on the
  // screen would leave the same rows looking unsaved.
  await expect(switcher(page).getByRole('button', { name: /^Open work/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /^Save/ })).toHaveCount(0)
  expectNoRealErrors(errors)
})

test('a shared view can be hidden, and every hidden one comes back at once', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()

  // Hiding is not deleting, and is only for a view somebody shared: it stays
  // where it is for everyone else, and this says only that one reader would
  // rather not see it.
  await openSubmenu(page, 'High priority')
  await page.getByRole('menuitem', { name: 'Hide it from my menu' }).click()

  await openMenu(page)
  await expect(page.getByRole('menuitem', { name: 'High priority' })).toHaveCount(0)

  // A hidden view is not in the menu, so the menu is the wrong place to pick
  // one out of — they come back together.
  await page.getByRole('menuitem', { name: /^Show the hidden view$|^Show \d+ hidden views$/ }).click()
  await openMenu(page)
  await expect(page.getByRole('menuitem', { name: 'High priority' })).toBeVisible()
  expectNoRealErrors(errors)
})
