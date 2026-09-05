// A screen read as a hierarchy.
//
// The disclosure and the keyboard are frappe-ui's; what is ours is the nesting
// — which field a screen nests by, and the fact that it is built out of the
// page rather than a query per node. So this asserts the shape and the click,
// on the compliance register's own renewal lineage.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const LINEAGE = ['Trade Licence — 2024', 'Trade Licence', 'Trade Licence — 2027']

test('a screen can be read as a tree, and a renewal sits under what it renewed', async ({
  page,
  baseURL,
}) => {
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=compliance&type=tree')

  const tree = page.locator('[data-slot="tree"]')
  await tree.waitFor({ timeout: 25_000 })
  await expect(tree.getByText(LINEAGE[0], { exact: true })).toBeVisible({ timeout: 15_000 })

  // Three years of one licence, each pointing at the one it replaced. Nested
  // and not merely present: the rows are indented against each other, which is
  // the only thing that distinguishes this from the list.
  const boxes = []
  for (const title of LINEAGE) {
    boxes.push(await tree.getByText(title, { exact: true }).boundingBox())
  }
  expect(boxes[1].x).toBeGreaterThan(boxes[0].x)
  expect(boxes[2].x).toBeGreaterThan(boxes[1].x)

  // And a document that renews nothing is a root, at the same depth as the
  // oldest licence rather than under it.
  const alone = await tree.getByText('Memorandum of Association', { exact: true }).boundingBox()
  expect(alone.x).toBe(boxes[0].x)

  expectNoRealErrors(errors)
})

test('a name in the tree opens the record it is', async ({ page, baseURL }) => {
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=compliance&type=tree')
  const tree = page.locator('[data-slot="tree"]')
  await tree.waitFor({ timeout: 25_000 })

  // The name opens; the rest of the row expands. Same surface and same URL as
  // the list's row — a view type is a way of reading a screen, never a
  // separate place.
  await tree.getByText('Trade Licence — 2027', { exact: true }).click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 15_000 })
  await expect(page).toHaveURL(/record=/)

  expectNoRealErrors(errors)
})
