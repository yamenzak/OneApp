// Which values on a record a model wrote.
//
// The mark is a sparkle beside the field's label and a sentence in its
// tooltip. What a browser pass is for is that it lands on the field that
// carries a mark and on no other: the label is built in two places — most
// fieldtypes through `FieldLabel`, the prose editor by hand — and that is
// exactly the kind of seam a unit test does not see. When a mark goes is
// server behaviour and is tested in `tests/test_ai_written.py`.
//
// The marked row is one of the backlog tail rather than one of the three named
// tasks, and deliberately: a mark is *meant* to expire when a person rewrites
// the value, so a record another spec types into is the one place this can
// never be asserted twice in the same pass. See `WRITTEN_BY_AI` in
// `scripts/seed_dev_space.py`.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const TASKS = '/one/space/zzmock?screen=tasks'
const DRAWN = 'zzmock-drawn.svg'
const MARKED = 'Backlog item 01'
const UNMARKED = 'Backlog item 02'

const open = async (page, text) => {
  await page.goto(TASKS)
  await page.locator('[data-slot="list-row"]', { hasText: text }).first().click()
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 20_000 })
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a field a model wrote says so, and the fields beside it do not', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  await open(page, MARKED)
  const mark = page.locator('[data-slot="ai-mark"]')
  await expect(mark).toHaveCount(1)

  // The sentence names the model in the words the picker uses rather than the
  // key the row stores.
  await expect(mark).toHaveAttribute('aria-label', /Flash/)

  await open(page, UNMARKED)
  await expect(page.locator('[data-slot="ai-mark"]')).toHaveCount(0)

  expectNoRealErrors(errors)
})

test('a file a model made says so, in the list', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  await page.goto('/one/files')
  await page.getByPlaceholder('Search files').fill(DRAWN)

  const row = page.locator('[data-slot="drive-file"]', { hasText: DRAWN })
  await expect(row).toHaveCount(1, { timeout: 20_000 })

  // Said on the file's face — the one component the list, the grid and the
  // picker all draw a file's identity through — so the mark reaches every one
  // of them from one place. See `drive/FileFace.vue`.
  await expect(row.locator('[data-slot="ai-mark"]')).toHaveAttribute(
    'aria-label', /Flux/,
  )

  // And in the pane it opens in, which is the surface that face did *not*
  // reach: the previewer took its title as a string, so a generated image
  // opened unmarked until the title became something a mark could sit in.
  await row.locator('[data-slot="drive-open"]').click()
  const pane = page.locator('[data-slot="object-pane"]')
  await expect(pane).toContainText(DRAWN)
  await expect(pane.locator('[data-slot="ai-mark"]')).toHaveAttribute(
    'aria-label', /Flux/,
  )

  expectNoRealErrors(errors)
})
