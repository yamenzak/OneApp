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

test('a record has its own correspondence, and writing one files it there', async ({
  page,
  baseURL,
}) => {
  const errors = collectConsoleErrors(page)
  await signIn(page, baseURL)
  await openMail(page)

  const before = await page.locator('[data-slot="record-message"]').count()

  const subject = `Cladding schedule ${Date.now()}`
  await page.getByRole('button', { name: 'Write' }).first().click()
  await page.getByPlaceholder('To').fill('hala@client.test')
  await page.getByPlaceholder('Subject').fill(subject)
  await page.locator('[contenteditable="true"]').first().fill('The revised schedule is attached.')
  await page.getByRole('button', { name: 'Send' }).click()

  // It comes back on the record rather than only in the Mail screen, which is
  // the whole point: the link is made by the sending.
  const message = page.locator('[data-slot="record-message"]', { hasText: subject })
  await expect(message).toBeVisible({ timeout: 20_000 })
  await expect(page.locator('[data-slot="record-message"]')).toHaveCount(before + 1)

  // And it says how it got here. A link nobody can explain is a link nobody
  // will trust, and this one was made by a person.
  await expect(message.getByText('manual', { exact: true })).toBeVisible()

  expectNoRealErrors(errors)
})

test('a message can be taken off a record it is not about', async ({ page, baseURL }) => {
  await signIn(page, baseURL)
  await openMail(page)

  const subject = `Wrong record ${Date.now()}`
  await page.getByRole('button', { name: 'Write' }).first().click()
  await page.getByPlaceholder('To').fill('hala@client.test')
  await page.getByPlaceholder('Subject').fill(subject)
  await page.locator('[contenteditable="true"]').first().fill('Filed by mistake.')
  await page.getByRole('button', { name: 'Send' }).click()

  const message = page.locator('[data-slot="record-message"]', { hasText: subject })
  await expect(message).toBeVisible({ timeout: 20_000 })

  await message.getByRole('button', { name: 'Not about this record' }).click()
  await expect(message).toHaveCount(0)

  // And it is gone after a reload, not only out of the list in this tab.
  await page.reload()
  await page.getByRole('tab', { name: 'Mail' }).click()
  await expect(
    page.locator('[data-slot="record-message"]', { hasText: subject }),
  ).toHaveCount(0)
})
