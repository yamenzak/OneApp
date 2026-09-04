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
  // Sent belongs to an address rather than to the workspace: one outbox per
  // address, holding both what was written here and what the mailbox's own
  // Sent folder already had.
  await expect(folders.filter({ hasText: 'Sent' })).toHaveCount(1)

  expectNoRealErrors(errors)
})

test('the folders a mailbox already has come across, Sent included', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')

  const rail = page.locator('[data-slot="mail-folder"]')

  // Somebody's own filing, not a flat list. `INBOX` is deliberately absent —
  // the address row above it already is the inbox.
  await expect(rail.filter({ hasText: 'Applicants' })).toHaveCount(1)
  await expect(rail.filter({ hasText: 'Documents' })).toHaveCount(1)
  // Neither INBOX nor the server's own Sent folder gets a row of its own: the
  // address is the inbox, and the Sent row above already is that outbox.
  await expect(rail.filter({ hasText: 'INBOX' })).toHaveCount(0)
  await expect(rail.filter({ hasText: 'Sent Items' })).toHaveCount(0)

  // Junk is mirrored and folded away, because a rail that opens on somebody's
  // spam is a rail nobody wants.
  await expect(rail.filter({ hasText: 'Junk' })).toHaveCount(0)
  await page.locator('[data-slot="mail-more-folders"]').click()
  await expect(rail.filter({ hasText: 'Junk' })).toHaveCount(1)

  // A folder somebody made holds what they filed in it, and nothing else.
  await rail.filter({ hasText: 'Applicants' }).click()
  await expect(threads(page)).toHaveCount(1)
  await expect(threads(page).first()).toContainText('Fabricator')

  // And the Sent folder is not empty, which is the whole reason the framework's
  // "your own mail in your own inbox" guard is off inside one.
  await rail.filter({ hasText: 'Sent' }).click()
  await expect(threads(page).first()).toContainText('revised elevations')

  expectNoRealErrors(errors)
})

test('a sender is a person, with a card behind the name', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')

  // The Contact's name, not the raw address and not the header — a Contact is
  // what this workspace decided the person is called.
  const row = threads(page).filter({ hasText: SUBJECT })
  await expect(row.locator('[data-slot="mail-sender"]')).toContainText('Hala Nasser')
  await expect(row).not.toContainText('hala@client.test')

  await row.click()
  // Hovering a name in a message opens the card; the list does not have one,
  // because fifty of them is a card that opens while somebody is scanning.
  await messages(page).first().locator('[data-slot="mail-sender"]').hover()
  await expect(page.getByText('Al Reem Consultants')).toBeVisible()
  await expect(page.getByText('hala@client.test')).toBeVisible()

  expectNoRealErrors(errors)
})

test('a conversation can be filed into a folder', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')

  const rail = page.locator('[data-slot="mail-folder"]')
  await threads(page).filter({ hasText: SUBJECT }).click()

  // The conversation, not the message: filing a reply and leaving the
  // original in the inbox is the behaviour every client got complained about.
  await page.locator('[data-slot="mail-move"]').click()
  await page.getByRole('menuitem', { name: 'Documents' }).click()

  await rail.filter({ hasText: 'Documents' }).click()
  const filed = threads(page).filter({ hasText: SUBJECT })
  await expect(filed).toHaveCount(1)
  await filed.click()
  await expect(messages(page)).toHaveCount(2)

  // Put it back, so the fixture is as the next run found it.
  await page.locator('[data-slot="mail-move"]').click()
  await page.getByRole('menuitem', { name: 'Applicants' }).click()

  expectNoRealErrors(errors)
})

test('a folder is made in the mailbox it belongs to', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')

  // The button is on the address, not at the foot of the rail with a dropdown
  // asking which mailbox — a folder belongs to a mailbox.
  const address = page.locator('[data-slot="mail-folder"]').filter({ hasText: ADDRESS }).first()
  await address.hover()
  await address.locator('[data-slot="mail-new-folder"]').click()

  // And the dialog says which of the two kinds of folder this will be, before
  // it is made rather than after.
  await expect(page.getByText(/no mailbox server|other mail apps/)).toBeVisible()
  await page.keyboard.press('Escape')

  expectNoRealErrors(errors)
})

test('a tracking pixel does not load itself', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  // If the browser asks for it, the sender learns the message was opened, by
  // whom and from where. So: refuse the request, and prove it by watching.
  const reached = []
  await page.route('**://tracker.invalid/**', (route) => {
    reached.push(route.request().url())
    return route.abort()
  })

  await signIn(page, baseURL)
  await page.goto('/one/mail')
  await threads(page).filter({ hasText: 'Fabricator' }).click()

  const notice = page.locator('[data-slot="mail-blocked-images"]')
  await expect(notice).toContainText('1 image not loaded')
  expect(reached).toEqual([])

  // And asking for them puts them back — at which point the request is made,
  // because that is what the reader just chose.
  await notice.getByRole('button', { name: 'Show images' }).click()
  await expect(notice).toHaveCount(0)
  await expect
    .poll(() => reached.length, { timeout: 5_000 })
    .toBeGreaterThan(0)

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
