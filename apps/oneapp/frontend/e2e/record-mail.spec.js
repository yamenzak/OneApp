import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

/**
 * The mail about a record.
 *
 * Sending from a record is the path worth a browser pass: it is the one filing
 * in the product that needs no working out — the person was looking at the
 * record when they wrote it — and it is the half that makes correctly-linked
 * mail exist at all. The two automatic paths are unit-tested, because what they
 * turn on is a database and a series prefix rather than anything you can see.
 */

const messages = (page) => page.locator('[data-slot="record-message"]')

async function openMail(page) {
  await page.goto('/one/space/rua?screen=projects')
  const missing = await page
    .getByText('Nothing here', { exact: false })
    .isVisible()
    .catch(() => false)
  test.skip(missing, 'this tenant has no ERPNext, so the space is not seeded')

  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 25_000 })
  await page.locator('[data-slot="list-row"]').first().click()
  await page.getByRole('tab', { name: 'Mail' }).click()
}

/** Write one from the record. The composer is the Mail screen's, with an `about`. */
async function write(page, subject) {
  await page.getByRole('button', { name: 'Write' }).first().click()
  const compose = page.getByRole('dialog')
  await compose.locator('[data-slot="mail-recipients-to"] [data-slot="trigger"]').click()
  await page.getByRole('combobox').fill('hala@client.test')
  await page.getByRole('option', { name: /hala@client\.test/i }).first().click()
  await page.keyboard.press('Escape')
  await compose.getByLabel('Subject').fill(subject)
  await compose.getByRole('button', { name: 'Send' }).click()
  await expect(compose).toBeHidden()
}

test('a record has its own correspondence, and writing one files it there', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the composer is the same dialog on both')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await openMail(page)

  const subject = `Cladding schedule ${Date.now()}`
  await write(page, subject)

  // It comes back on the record rather than only in the Mail screen, which is
  // the whole point: the link is made by the sending.
  //
  // The subject carries a timestamp and the assertion is on that, not on a
  // count: this record keeps every message any run ever wrote to it, so a
  // count is a fixture assumption rather than a fact about the feature — and
  // it failed once for exactly that reason.
  const message = messages(page).filter({ hasText: subject })
  await expect(message).toBeVisible({ timeout: 20_000 })

  // And it says how it got here. A link nobody can explain is a link nobody
  // will trust, and this one was made by a person.
  await expect(message.getByText('manual', { exact: true })).toBeVisible()

  expectNoRealErrors(errors)
})

test('a message can be taken off a record it is not about', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the composer is the same dialog on both')

  await signIn(page, baseURL)
  await openMail(page)

  const subject = `Wrong record ${Date.now()}`
  await write(page, subject)

  const message = messages(page).filter({ hasText: subject })
  await expect(message).toBeVisible({ timeout: 20_000 })

  await message.getByRole('button', { name: 'Not about this record' }).click()
  await expect(message).toHaveCount(0)

  // Gone after a reload, not only out of the list in this tab — the unfiling is
  // a write, and a control that only tidied the screen would look identical.
  await page.waitForLoadState('networkidle')
  await page.reload()
  await page.getByRole('tab', { name: 'Mail' }).click()
  await expect(messages(page).filter({ hasText: subject })).toHaveCount(0)
})
