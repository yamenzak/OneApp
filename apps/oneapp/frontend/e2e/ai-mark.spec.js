// Which values on a record a model wrote.
//
// The mark is a sparkle beside the field's label and a sentence in its
// tooltip. What a browser pass is for is that it lands on the field that
// carries a mark and on no other: the label is built in two places — most
// fieldtypes through `FieldLabel`, the prose editor by hand — and that is
// exactly the kind of seam a unit test does not see. When a mark goes is
// server behaviour and is tested in `tests/test_ai_written.py`.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// The fixture's one marked field: `zzmock-halloway`'s description. See
// `written_by_ai` in `scripts/seed_dev_space.py`.
const MARKED = '/one/space/zzmock?screen=tasks&record=zzmock-halloway'
const UNMARKED = '/one/space/zzmock?screen=tasks&record=zzmock-q3'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('a field a model wrote says so, and the fields beside it do not', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  await page.goto(MARKED)
  const mark = page.locator('[data-slot="ai-mark"]')
  await expect(mark).toHaveCount(1)

  // The sentence names the assistant and the model, in the words the model
  // picker uses rather than the key the row stores.
  await expect(mark).toHaveAttribute('aria-label', /Flash/)

  await page.goto(UNMARKED)
  await page.locator('[data-slot="record-controls"]').waitFor({ timeout: 20_000 })
  await expect(page.locator('[data-slot="ai-mark"]')).toHaveCount(0)

  expectNoRealErrors(errors)
})
