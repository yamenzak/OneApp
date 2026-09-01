// A board is the reader's, not the manifest's.
//
// A screen declares the field a board *opens* on — that is what makes it
// offerable at all — and from there "show me this by assignee instead" is the
// same kind of question as "sort by this column", answered the same way:
// changed in the settings dialog, kept in a saved view.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const BOARD = '[data-oneapp-column]'

const openBoard = async (page) => {
  await page.goto('/one/space/zzmock?screen=tasks&type=board')
  await page.locator(BOARD).first().waitFor({ timeout: 15_000 })
}

const openSettings = async (page) => {
  await page.getByRole('button', { name: 'Board settings' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
}

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

test('the gear opens the board rather than the column picker', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the settings gear is desktop chrome')
  const errors = collectConsoleErrors(page)
  await openBoard(page)

  // One gear, and what it opens is whatever the body is.
  await openSettings(page)
  await expect(page.getByLabel('Columns of')).toBeVisible()

  // On the list it is still the columns.
  await page.keyboard.press('Escape')
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'Choose columns' })).toBeVisible()
  expectNoRealErrors(errors)
})

test('a board can be made of any Select or Link the screen shows', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the settings gear is desktop chrome')
  const errors = collectConsoleErrors(page)
  await openBoard(page)

  // It opens on the field the manifest named.
  await expect(page.locator('[data-oneapp-column="Open"]')).toBeVisible()

  await openSettings(page)
  // Only fields a board can be made of: a Date wants a calendar and a Text is a
  // column per sentence. frappe-ui's Select is a combobox with a popover, not
  // a native `<select>`, so the options are read by opening it.
  await page.getByRole('combobox', { name: 'Columns of' }).click()
  const offered = await page.getByRole('option').allInnerTexts()
  expect(offered).toContain('Status')
  expect(offered).toContain('Priority')
  expect(offered).toContain('Allocated To')
  expect(offered).not.toContain('Due Date')
  expect(offered).not.toContain('Description')

  // A second Select, whose options become the columns.
  await page.getByRole('option', { name: 'Priority', exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-oneapp-column="High"]')).toBeVisible()
  await expect(page.locator('[data-oneapp-column="Low"]')).toBeVisible()
  await expect(page.locator('[data-oneapp-column="Open"]')).toHaveCount(0)

  // A Link: the columns are whoever is on the page, drawn as records rather
  // than as ids.
  await openSettings(page)
  await page.getByRole('combobox', { name: 'Columns of' }).click()
  await page.getByRole('option', { name: 'Allocated To', exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-oneapp-column="Administrator"]')).toBeVisible()

  // Back to what the screen says.
  await openSettings(page)
  await page.getByRole('button', { name: 'Reset' }).click()
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-oneapp-column="Open"]')).toBeVisible()
  expectNoRealErrors(errors)
})

test('a card shows the fields the reader picked', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the settings gear is desktop chrome')
  await openBoard(page)

  const card = page.locator('[data-oneapp-column="Open"] article', {
    hasText: 'Book the van for Thursday',
  })
  await expect(card).toBeVisible()

  await openSettings(page)
  await page.getByRole('button', { name: 'On each card' }).click()
  await page.getByRole('option', { name: 'Due Date', exact: true }).click()
  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')

  // One field, and it is the one chosen — not the columns the list happens to
  // be showing.
  await expect(card).toContainText('Aug')
  await expect(card).not.toContainText('Medium')

  await openSettings(page)
  await page.getByRole('button', { name: 'Reset' }).click()
  await page.keyboard.press('Escape')
  await expect(card).toContainText('Medium')
})
