// The Drive's pane: a way out of it, and a grid that fits the room it has.
//
// **What the pane is now.** It held the editors once, and that is where both
// complaints below came from — an editor in it had no chrome, because its own
// identity bar teleports to the shell's header. `docs/DESKTOP.md` stage 6 took
// the editors out into windows of their own, so what is left in the pane is
// what it was always best at: the files there is nothing to open, shown rather
// than edited. A photograph, a PDF, a zip — name, kind, size and a preview.
//
// So these two tests open something the pane still takes. The grid's complaint
// is unchanged and is the reason this file exists: it counted its columns from
// the viewport rather than from the column it is drawn in, so opening anything
// beside it ran the cards into each other.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/**
 * A file the pane takes, made here rather than found.
 *
 * A `.md` with its name changed to an extension nothing can open:
 * `editorFor` decides from the name, so this is a file the Drive shows and
 * does not edit — which is the whole of what the pane is for now. Made rather
 * than found because the fixture's contents are not guaranteed and a test that
 * shares a file with another test fails when the other one is edited.
 */
async function aFileToLookAt(page) {
  const made = await page.request.post('/api/method/oneapp.onedoc.make_text', {
    data: { kind: 'md', title: `zzPane ${Date.now()}` },
  })
  expect(made.ok()).toBe(true)
  const name = (await made.json()).message.name

  const renamed = await page.request.post('/api/method/frappe.client.set_value', {
    data: {
      doctype: 'File', name, fieldname: 'file_name', value: `zzPane ${Date.now()}.zip`,
    },
  })
  expect(renamed.ok()).toBe(true)
  return name
}

test('a file opened in the pane can be closed again', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'on a phone the pane is a page and the row is a link')
  const errors = collectConsoleErrors(page)

  await aFileToLookAt(page)

  await page.goto('/one/files?place=all')
  const row = page.locator('[data-slot="drive-file"]').first()
  await row.waitFor({ timeout: 25_000 })
  await row.locator('[data-slot="drive-open"]').first().click()

  const pane = page.locator('[data-slot="object-pane"]')
  await expect(pane).toBeVisible({ timeout: 20_000 })

  // The one control only the host can offer.
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
  await aFileToLookAt(page)
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
