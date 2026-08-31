// The field's type icon lives inside its label.
//
// It used to sit in a gutter to the left of the whole row — its own column,
// aligned to the control rather than the label, indenting every label and every
// input past the section heading and leaving a ragged empty channel down the
// side of the form.
//
// The thing that made that the easy answer was the accessible name: most of
// this suite is written in `getByLabel`, and moving the icon into the label
// naively means rendering the label ourselves and losing the `for`/`id` pair.
// It goes through frappe-ui's own `label` **slot** instead, which renders
// inside its `<label for=…>` — so the pairing is untouched. That is what this
// checks, because it is the part that would break silently.
import { expect, test } from '@playwright/test'
import { signIn } from './auth.js'

const DIALOG = '[data-oneapp="form-dialog"]'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock')
  const button = page.getByRole('button', { name: 'New', exact: true }).first()
  await button.waitFor({ timeout: 15_000 })
  await button.click()
  await expect(page.locator(DIALOG)).toBeVisible()
})

test('a label still names its control', async ({ page }) => {
  // The whole reason the icon was in a gutter. If this breaks, every
  // `getByLabel` in the suite is one refactor from meaning nothing.
  await expect(page.locator(DIALOG).getByLabel('Description')).toBeVisible()
  await expect(page.locator(DIALOG).getByLabel('Due Date')).toBeVisible()
})

test('the icon is inside the label, not in a column beside the field', async ({ page }) => {
  const inside = await page.locator(DIALOG).evaluate((dialog) => {
    const labels = [...dialog.querySelectorAll('label')]
    const withIcon = labels.filter((l) => l.querySelector('[class*="lucide-"]'))
    return { labels: labels.length, withIcon: withIcon.length }
  })
  expect(inside.labels, 'no labels rendered at all').toBeGreaterThan(0)
  expect(inside.withIcon, 'no label carries its type icon').toBeGreaterThan(0)
})

test('the form no longer indents past its own section heading', async ({ page }) => {
  // The gutter pushed the label and the control right by the icon's width plus
  // its gap, so nothing in the form lined up with the heading above it.
  const offset = await page.locator(DIALOG).evaluate((dialog) => {
    const label = [...dialog.querySelectorAll('label')].find((l) => l.textContent.trim())
    const field = label?.closest('div')?.parentElement
    if (!label || !field) return null
    return Math.round(label.getBoundingClientRect().left - field.getBoundingClientRect().left)
  })
  expect(offset, 'could not measure').not.toBeNull()
  expect(offset, `the label is still inset ${offset}px from its field row`).toBeLessThanOrEqual(2)
})
