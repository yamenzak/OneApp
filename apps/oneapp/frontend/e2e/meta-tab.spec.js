// The Meta tab: what the record *is*, as opposed to what it says.
//
// Three things that are not fields on the doctype and never belonged among
// them — the picture, the id, and who made it when. The rename is Frappe's
// own `update_document_title`, behind Frappe's own `allow_rename`.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

const meta = (page) => page.getByRole('tab', { name: 'Meta' })

/** Open the first record on a screen, whichever shell we are in. */
const openFirst = async (page, baseURL, screen) => {
  await signIn(page, baseURL)
  await page.goto(`/one/space/zzmock?screen=${screen}&type=list`)
  await page.locator('[data-slot="list-row"]').first().click()
  await page.locator('[data-slot="record-pane"]').waitFor({ timeout: 15_000 })
}

test('the record says who made it, and when, on its own tab', async ({
  page,
  baseURL,
}) => {
  const errors = collectConsoleErrors(page)
  await openFirst(page, baseURL, 'notes')

  // Not in Details any more: a form that ends in its own provenance puts the
  // least interesting thing where the eye stops.
  await expect(page.getByText('Created by')).toHaveCount(0)

  await meta(page).click()
  await expect(page.getByText('Created by')).toBeVisible()
  await expect(page.getByText('Created', { exact: true })).toBeVisible()
  await expect(page.locator('[data-slot="record-id"]')).toBeVisible()

  // Note names its records by hash, so `allow_rename` is off and the desk
  // hides its rename for the same reason. So do we.
  await expect(page.locator('[data-slot="rename"]')).toHaveCount(0)

  expectNoRealErrors(errors)
})

test('a doctype that allows it can be renamed, and the URL follows', async ({
  page,
  baseURL,
}) => {
  // Contact is the fixture that declares `allow_rename` — and an image field,
  // so this is also the record where the picture control exists.
  await openFirst(page, baseURL, 'people')
  await meta(page).click()

  await expect(page.getByText('Picture')).toBeVisible()
  const rename = page.locator('[data-slot="rename"]')
  await expect(rename).toBeVisible()

  const was = (await page.locator('[data-slot="record-id"]').innerText()).trim()
  const now = `zzmeta-${Date.now() % 100000}`

  // In a `finally`, because this fixture is shared with every other spec and
  // the first version of this test failed halfway and left a contact called
  // `zzmeta-85902` behind for the rest of the suite to trip over.
  try {
    await rename.click()
    await page.getByLabel('New id').fill(now)
    await page.getByRole('button', { name: 'Rename', exact: true }).last().click()

    // The id on the page, and the id in the URL.
    await expect(page.locator('[data-slot="record-id"]')).toHaveText(now, {
      timeout: 15_000,
    })
    await expect(page).toHaveURL(new RegExp(`record=${now}`))
  } finally {
    await restore(page, was)
  }
})

/** Give the fixture its id back, whatever state the test got to. */
const restore = async (page, was) => {
  const id = page.locator('[data-slot="record-id"]')
  if ((await id.count()) && (await id.innerText()).trim() === was) return
  await page.locator('[data-slot="rename"]').click()
  await page.getByLabel('New id').fill(was)
  await page.getByRole('button', { name: 'Rename', exact: true }).last().click()
  await expect(id).toHaveText(was, { timeout: 15_000 })
}
