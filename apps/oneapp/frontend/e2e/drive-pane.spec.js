// The Drive's pane: a way out of it, and a grid that fits the room it has.
//
// Three complaints, one surface. A document opened in the pane had no chrome
// at all — its own identity bar teleports to the shell's header, so the pane
// held an editor and nothing to close it with. The grid counted its columns
// from the viewport rather than from the column it is drawn in, so opening
// anything beside it ran the cards into each other. And a text file too big
// for an editor reached the editor anyway and got "that document did not
// open" where its name, kind and size would have done.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a document opened in the pane can be closed again', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'on a phone the pane is a page and the row is a link')
  const errors = collectConsoleErrors(page)

  // Made here rather than found: the fixture's documents are not guaranteed,
  // and what is being tested is the pane's chrome rather than any one file.
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Document' }).click()
  await page.waitForURL(/\/one\/docs\//, { timeout: 25_000 })

  // Back to the Drive, and open the same document from the list — which on a
  // desktop opens it in the pane rather than on its page.
  await page.goto('/one/files?place=all')
  const row = page.locator('[data-slot="drive-file"]').first()
  await row.waitFor({ timeout: 25_000 })
  await row.locator('[data-slot="drive-open"]').first().click()

  const pane = page.locator('[data-slot="object-pane"]')
  await expect(pane).toBeVisible({ timeout: 20_000 })
  // An editor and not the previewer, or this proves nothing: the previewer
  // always had a header with a close in it.
  await expect(pane.locator('.ProseMirror').first()).toBeVisible({ timeout: 20_000 })

  // The one control only the host can offer: the editors know how to go back
  // to a route and cannot know they are in a pane.
  const close = page.locator('[data-slot="file-pane-close"]')
  await expect(close).toBeVisible()
  await close.click()
  await expect(pane).toHaveCount(0)
  // And the list is still the list, at the place it was — which is what a
  // route would have taken away.
  await expect(page).toHaveURL(/place=all/)

  expectNoRealErrors(errors)
})

test('the grid lays out against the column it is in, not the window', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'there is no pane beside the list on a phone')
  await page.goto('/one/files?place=all')
  await page.locator('[data-slot="drive-file"]').first().waitFor({ timeout: 25_000 })

  await page.getByRole('button', { name: 'Show as a grid' }).click()
  const cards = page.locator('[data-slot="drive-file"]')
  await expect(cards.first()).toBeVisible()

  /** How many cards share the topmost row, which is the column count. */
  const across = async () => {
    return page.evaluate(() => {
      const all = [...document.querySelectorAll('[data-slot="drive-file"]')]
      if (!all.length) return 0
      const top = Math.round(all[0].getBoundingClientRect().top)
      return all.filter((el) => Math.round(el.getBoundingClientRect().top) === top).length
    })
  }

  const wide = await across()
  expect(wide, 'the grid is not laying out in rows').toBeGreaterThan(1)

  // Open a file beside it. The list keeps less than half the window now, so a
  // grid that counted from the viewport would keep every column it had.
  await page.locator('[data-slot="drive-open"]').first().click()
  await expect(page.locator('[data-slot="object-pane"]')).toBeVisible({ timeout: 20_000 })
  await page.waitForTimeout(400)

  const narrow = await across()
  expect(narrow, 'the grid kept its columns when the room for them halved')
    .toBeLessThan(wide)
  expect(narrow).toBeGreaterThan(0)

  // And no card is narrower than the floor, which is what "collapsed into each
  // other" looked like.
  const thinnest = await page.evaluate(() => {
    const all = [...document.querySelectorAll('[data-slot="drive-file"]')]
    return Math.min(...all.map((el) => el.getBoundingClientRect().width))
  })
  expect(thinnest).toBeGreaterThanOrEqual(140)
})
