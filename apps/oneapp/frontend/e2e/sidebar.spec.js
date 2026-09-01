// The sidebar collapses, and remembers.
//
// On a laptop running a data grid, a fixed 224px of chrome sits between the
// reader and their columns. frappe-ui's Sidebar already knew how to shrink —
// SidebarItem collapses to its icon on its own — so what was missing was the
// state, the toggle, and somewhere to remember it.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const SIDEBAR = '[data-slot="sidebar"]'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the sidebar collapses to its icons and comes back', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone has a bar, not a sidebar')
  const errors = collectConsoleErrors(page)
  await page.goto('/one/space/zzmock')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  const sidebar = page.locator(SIDEBAR)
  const open = (await sidebar.boundingBox()).width
  expect(open).toBeGreaterThan(150)
  await expect(sidebar).toHaveAttribute('data-state', 'expanded')

  await page.getByRole('button', { name: 'Collapse' }).click()
  await expect(sidebar).toHaveAttribute('data-state', 'collapsed')
  await expect.poll(async () => (await sidebar.boundingBox()).width).toBeLessThan(80)

  // Remembered in this browser: a sidebar you shut on every page load is a
  // sidebar you shut once and then fight.
  await page.reload()
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })
  await expect(page.locator(SIDEBAR)).toHaveAttribute('data-state', 'collapsed')

  await page.getByRole('button', { name: 'Expand' }).click()
  await expect(page.locator(SIDEBAR)).toHaveAttribute('data-state', 'expanded')
  expectNoRealErrors(errors)
})

test('the sidebar can be resized, and the handle goes when it shuts', async ({
  page,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the phone has a bar, not a sidebar')
  await page.goto('/one/space/zzmock')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  const sidebar = page.locator(SIDEBAR)
  const before = (await sidebar.boundingBox()).width

  // The same component the record pane uses, and the same keyboard half of it.
  // Right is wider here: the handle is on the sidebar's right edge.
  const handle = page.locator('[data-slot="sidebar-resizer"]')
  await handle.focus()
  await page.keyboard.press('Shift+ArrowRight')
  await expect.poll(async () => (await sidebar.boundingBox()).width).toBeGreaterThan(before)

  // A collapsed sidebar is one width by definition, so there is nothing to
  // drag.
  await page.getByRole('button', { name: 'Collapse' }).click()
  await expect(handle).toHaveCount(0)

  await page.getByRole('button', { name: 'Expand' }).click()
  await expect(handle).toBeVisible()
  // And the width it was dragged to is still the width it is.
  await expect.poll(async () => (await sidebar.boundingBox()).width).toBeGreaterThan(before)
})
