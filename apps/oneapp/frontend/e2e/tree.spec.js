// A screen read as a hierarchy.
//
// The disclosure and the keyboard are frappe-ui's; what is ours is the nesting
// — which field a screen nests by, and the fact that it is built out of the
// page rather than a query per node. So this asserts the shape and the click,
// on the compliance register's own renewal lineage.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const LINEAGE = ['Trade Licence — 2024', 'Trade Licence', 'Trade Licence — 2027']

const TREE = '/one/space/zzmock?screen=compliance&type=tree'

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

test('a record can be dragged under another, and back out', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'a drag needs a pointer')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto(TREE)

  const visa = () => page.getByRole('treeitem', { name: /Residence Visa/ }).first()
  // The *row*, not the treeitem: an `<li>` contains its whole subtree, so its
  // centre — which is where `dragTo` aims — is over one of its descendants.
  // The first version of this dropped two levels down and said so.
  const row = (title) => page.getByRole('button', { name: title, exact: true }).first()

  /** Put it back at the root, wherever the last run left it. */
  const toRoot = async () => {
    if ((await visa().getAttribute('aria-level')) === '1') return
    // The top edge of the first row is "before" it, at that row's own level,
    // and it is the only way back out of a hierarchy by dragging.
    await visa().dragTo(page.getByRole('treeitem').first(), {
      targetPosition: { x: 40, y: 2 },
    })
    await expect(visa()).toHaveAttribute('aria-level', '1', { timeout: 20_000 })
  }

  await visa().waitFor({ timeout: 20_000 })
  await toRoot()

  // Dropped on the middle of a row, which is what "inside" means to the
  // component — the top and bottom thirds are before and after.
  await visa().dragTo(row('Trade Licence — 2024'))

  // One field written, through the same `save` a form uses. The list is
  // re-read afterwards, so what comes back is the server's answer rather than
  // the browser's guess.
  await expect(visa()).toHaveAttribute('aria-level', '2', { timeout: 20_000 })

  await toRoot()
  expectNoRealErrors(errors)
})
