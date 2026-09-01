// Tags and sharing.
//
// Both are Frappe's stores — `_user_tags` plus `Tag Link`, and `DocShare` —
// reached through the screen. What this asserts is the two halves that matter:
// that a tag put on from the record turns up in the list as a column and on a
// card without one, and that a share written here is a record the other person
// can actually open.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const COLLEAGUE = { user: 'robin@zzmock.test', password: 'Dev-Loop-2026!x' }
const TASK = 'zzmock-q3'
const TAG = 'zzurgent'

const meta = (page) => page.locator('[data-slot="record-pane"]').getByRole('tab', { name: 'Meta' })

const openTask = async (page, baseURL, who) => {
  await signIn(page, baseURL, who)
  await page.goto(`/one/space/zzmock?screen=tasks&record=${TASK}`)
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })
}

/** Put the record back the way every other spec expects to find it. */
const clean = (page) =>
  page.evaluate(
    async ([task, tag]) => {
      const post = (method, body) =>
        fetch(`/api/method/oneapp.oneapp_core.spaceview.${method}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Frappe-CSRF-Token': window.csrf_token || '',
          },
          body: JSON.stringify({ space_code: 'zzmock', screen: 'tasks', name: task, ...body }),
        })
      await post('set_tag', { tag, on: 0 })
      await post('unshare', { user: 'robin@zzmock.test' })
      await post('unshare', { everyone: 1 })
    },
    [TASK, TAG],
  )

test('a tag put on a record shows up in the list and on a card', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the column picker is a desktop control')
  const errors = collectConsoleErrors(page)

  await openTask(page, baseURL)
  await clean(page)
  await meta(page).click()

  // Tag it. The picker offers the workspace's whole vocabulary and lets a new
  // word be typed, because that is how a vocabulary grows.
  await page.locator('[data-slot="tags"]').click()
  await page.getByPlaceholder('Tag this').fill(TAG)
  await page.getByRole('option', { name: new RegExp(TAG) }).click()
  await page.keyboard.press('Escape')
  // The accessible name rather than the badges: the badges cap at two and
  // count the rest, so a record that already had tags would hide this one
  // behind a "+1" and the assertion would be about the cap.
  await expect(page.locator('[data-slot="tags"]')).toHaveAttribute(
    'aria-label',
    new RegExp(TAG),
  )

  // It survives a reload: this is a row in the database, not a badge in a ref.
  await page.reload()
  await meta(page).click()
  await expect(page.locator('[data-slot="tags"]')).toHaveAttribute(
    'aria-label',
    new RegExp(TAG),
    { timeout: 15_000 },
  )
  expectNoRealErrors(errors)

  // And on a card, with nobody having gone near the column picker: the tags
  // ride on every row, so a board shows them without being configured.
  await page.goto('/one/space/zzmock?screen=tasks&type=board')
  await expect(
    page.locator(`[data-oneapp-card="${TASK}"]`).getByText(TAG),
  ).toBeVisible({ timeout: 15_000 })

  await openTask(page, baseURL)
  await clean(page)
})

test('a record shared with somebody is a record they can open', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the share dialog is wide')

  await openTask(page, baseURL)
  await clean(page)
  await meta(page).click()

  await page.locator('[data-slot="share"]').click()
  await page.getByPlaceholder('Somebody on this workspace').click()
  await page.getByRole('option', { name: /robin/i }).click()
  await page.getByRole('button', { name: 'Share', exact: true }).click()

  // The row lands, at the level it was given.
  const row = page.locator('[data-slot="share-row"]').first()
  await expect(row).toContainText('Robin', { timeout: 15_000 })
  await page.keyboard.press('Escape')

  // Frappe folds shares into the permission condition of every list query, so
  // the person it was shared with can read it with nothing else written
  // anywhere. That is the whole reason `DocShare` was worth using.
  await signIn(page, baseURL, COLLEAGUE)
  await page.goto(`/one/space/zzmock?screen=tasks&record=${TASK}`)
  await expect(
    page.locator('[data-slot="record-pane"]').getByText('File Q3 returns').first(),
  ).toBeVisible({ timeout: 15_000 })

  await openTask(page, baseURL)
  await clean(page)
})
