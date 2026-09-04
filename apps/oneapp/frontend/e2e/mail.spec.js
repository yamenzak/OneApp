// Mail: an address is a delivery point, and reading it is a filtered list.
//
// Three things worth a browser, and none of them is "does the list render".
//
// That a conversation is a *place*: the thread is in the URL, so the back
// button closes it and a reload keeps it open — which is the difference between
// a mail reader somebody can send a link from and a widget.
//
// That two messages one subject apart are one row. `Communication` has no
// thread key, so the grouping is the subject with its `Re:` stripped, and the
// fixture seeds exactly that pair.
//
// And that the settings panel offers to connect a mailbox to anybody, not only
// to an owner — a mailbox somebody connects with their own password is theirs.
import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// What `_seed_mail` puts on the site.
const SUBJECT = 'Quotation for the Al Reem tower'
// The local part only. The domain is the workspace's own — `addresses.domain()`
// on whichever site this runs against — so pinning the whole address would pin
// a site's configuration into a spec about mail.
const ADDRESS = 'sales@'

const threads = (page) => page.locator('[data-slot="mail-thread"]')
const messages = (page) => page.locator('[data-slot="mail-message"]')

test('a conversation is one row, and opening it is a place you can link to', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')

  // One row for two messages, and it says so — the count beside the subject is
  // what tells somebody there is more than one without opening it.
  const row = threads(page).filter({ hasText: SUBJECT })
  await expect(row).toHaveCount(1)
  await expect(row).toContainText('(2)')

  await row.click()

  // The thread is in the query string, not in a ref beside it.
  await expect(page).toHaveURL(/thread=/)
  await expect(messages(page)).toHaveCount(2)

  // Oldest first — the order it happened, which is the only order a reply
  // makes sense read in.
  await expect(messages(page).first()).toContainText('revised cladding quote')
  await expect(messages(page).last()).toContainText('glazing line moved')

  // A reload keeps it open, because the URL is the state.
  await page.reload()
  await expect(messages(page)).toHaveCount(2)

  // And the back button closes it rather than leaving the page.
  await page.goBack()
  await expect(messages(page)).toHaveCount(0)
  await expect(threads(page).first()).toBeVisible()

  expectNoRealErrors(errors)
})

test('the rail lists the addresses this person holds', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')

  const folders = page.locator('[data-slot="mail-folder"]')
  await expect(folders.filter({ hasText: ADDRESS })).toHaveCount(1)
  // Sent is a pseudo-folder and is always last, because it is the one thing in
  // the rail that is not an address.
  await expect(folders.last()).toContainText('Sent')

  expectNoRealErrors(errors)
})

test('anybody may connect the mailbox they already have', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the settings dialog has its own spec')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: 'Email' }).click()

  // The address the fixture granted, with its signature, is the top half.
  await expect(
    page.locator('[data-slot="mail-address"]').filter({ hasText: ADDRESS }),
  ).toHaveCount(1)

  // Typing an address fills in the servers. Somebody who says `gmail.com` has
  // told us where their mail lives, and asking them for `imap.gmail.com`
  // afterwards is asking them to look up something we know.
  await page.getByLabel('Mailbox address').fill('someone@gmail.com')

  await page.getByRole('button', { name: 'Change the servers' }).click()
  await expect(page.getByLabel('Incoming (IMAP)')).toHaveValue('imap.gmail.com')
  await expect(page.getByLabel('Outgoing (SMTP)')).toHaveValue('smtp.gmail.com')

  expectNoRealErrors(errors)
})
