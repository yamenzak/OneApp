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
  // What is in it, not how many: a browser pass files things, so a count here
  // is an assertion about every other spec in the file.
  await expect(threads(page).filter({ hasText: 'Fabricator' })).toHaveCount(1)

  // And the Sent folder is not empty, which is the whole reason the framework's
  // "your own mail in your own inbox" guard is off inside one.
  //
  // That it is *there*, not that it is first — the same reason the Applicants
  // check counts nothing. A browser pass sends mail: `record-mail.spec.js`
  // writes from a record, and its messages are newer than the fixture's, so an
  // assertion on the first row was an assertion about which spec ran last.
  await rail.filter({ hasText: 'Sent' }).click()
  await expect(threads(page).filter({ hasText: 'revised elevations' })).toHaveCount(1)

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

  // Not put back here: the inbox is the address row, not a folder, so there is
  // nothing in this menu to move it to. `_seed_mail` restores the folder on
  // every run, which is the fixture's job rather than a spec's.

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

test('a forward carries the message, its files and nobody on the To', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')
  await threads(page).filter({ hasText: SUBJECT }).click()
  await page.locator('[data-slot="mail-forward"]').click()

  // Scoped to the dialog: `getByLabel('To')` also finds "Reply to all" and
  // "Move to" behind it, which is a lesson about aria-labels rather than about
  // mail. Recipients are addressed by their own slot because they are a
  // `MultiSelect` — a trigger showing who is on the field, not an input with a
  // value.
  const compose = page.getByRole('dialog')

  // Built on the server — quoting in the browser would quote the copy with its
  // remote images held back and send somebody a reply full of empty `<img>`.
  await expect(compose.getByRole('textbox', { name: 'Subject' }))
    .toHaveValue(`Fwd: ${SUBJECT}`)
  // A forward goes to nobody until somebody says who, which is what stops the
  // reflex reply-to-all from becoming a reflex forward-to-all. Empty here is
  // the trigger still showing its placeholder — asserting "no @ anywhere"
  // would only be asserting that the placeholder is not an address.
  const to = compose.locator('[data-slot="mail-recipients-to"]')
  await expect(to).toContainText('somebody@example.com')
  await expect(to).not.toContainText('client.test')
  await expect(compose).toContainText('wrote:')
  // The message being forwarded is the newest one in the thread, which is the
  // one on screen — not the one that started it.
  await expect(compose).toContainText('glazing line moved')

  await page.keyboard.press('Escape')
  expectNoRealErrors(errors)
})

test('a reply goes to the sender, and carries Cc when it is to all', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')
  await threads(page).filter({ hasText: SUBJECT }).click()

  await page.locator('[data-slot="mail-reply-all"]').click()
  const compose = page.getByRole('dialog')
  await expect(compose.locator('[data-slot="mail-recipients-to"]'))
    .toContainText('hala@client.test')
  // Cc and Bcc are behind a toggle, opened here because reply-to-all filled
  // one in — a field with something in it must not be hidden.
  const cc = compose.locator('[data-slot="mail-recipients-cc"]')
  await expect(cc).toBeVisible()
  // And never back to an address this person holds: answering yourself is the
  // oldest bug in mail.
  await expect(cc).not.toContainText(ADDRESS)

  await page.keyboard.press('Escape')
  expectNoRealErrors(errors)
})

test('the composer writes prose, not a textarea', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'three columns are a desktop layout')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')
  await page.getByRole('button', { name: 'Write' }).click()

  // A real editor: the thing typed into is ProseMirror's, and it has a
  // toolbar. A paragraph of plain text arrives at the other end as one long
  // line, which is what a textarea sends.
  const body = page.getByRole('dialog').locator('.ProseMirror')
  await expect(body).toBeVisible()
  await body.click()
  await page.keyboard.type('Bold this')
  await page.keyboard.press('Control+A')
  await page.getByRole('dialog').getByRole('button', { name: /bold/i }).first().click()
  await expect(body.locator('strong')).toHaveText('Bold this')

  // And a place to put a file on it.
  await expect(page.locator('[data-slot="mail-attach"]')).toBeVisible()

  await page.keyboard.press('Escape')
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

test('what you typed survives closing the composer', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the composer is the same dialog on both')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')
  await threads(page).first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Write' }).click()
  const compose = page.getByRole('dialog')
  await compose.getByLabel('Subject').fill('Half a thought')

  // Closing a composer is not a decision to throw the message away — it is
  // usually a misclick, and the one thing that must not happen is losing it.
  // The keep is debounced, so this waits for it rather than racing it.
  await page.waitForTimeout(1200)
  await page.keyboard.press('Escape')
  await expect(compose).toBeHidden()

  await page.getByRole('button', { name: 'Write' }).click()
  await expect(page.getByRole('dialog').getByLabel('Subject')).toHaveValue('Half a thought')

  await page.keyboard.press('Escape')
  expectNoRealErrors(errors)
})

test('a sent message can be taken back, and the taking back is real', async ({
  page,
  baseURL,
}, info) => {
  test.skip(info.project.name === 'mobile', 'the composer is the same dialog on both')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')
  await threads(page).first().waitFor({ timeout: 15_000 })
  const before = await threads(page).count()

  await page.getByRole('button', { name: 'Write' }).click()
  const compose = page.getByRole('dialog')
  await compose.locator('[data-slot="mail-recipients-to"] [data-slot="trigger"]').click()
  await page.getByRole('combobox').fill('nobody@client.test')
  // A typed address that matches nobody is still an address — most mail goes to
  // people who are in no directory.
  await page.getByRole('option', { name: /nobody@client\.test/i }).first().click()
  await page.keyboard.press('Escape')
  await compose.getByLabel('Subject').fill('Sent by mistake')
  await compose.getByRole('button', { name: 'Send' }).click()

  // The window opens on the send, not on a timer the browser owns: the message
  // is really held by `send_after`, which is why undo can promise anything.
  const undo = page.locator('[data-slot="mail-undo"]')
  await expect(undo).toBeVisible()
  await undo.getByRole('button', { name: 'Undo' }).click()
  await expect(undo).toBeHidden()

  // And the proof that it was more than a toast: the message is not in the
  // list, and a reload cannot bring it back.
  //
  // Let the refresh the unsend kicked off finish first. Reloading over an
  // in-flight request aborts it, and an aborted fetch reaches the console as
  // "Failed to fetch" — which the error check cannot tell from a real one.
  await page.waitForLoadState('networkidle')
  await page.reload()
  await threads(page).first().waitFor({ timeout: 15_000 })
  await expect(page.getByText('Sent by mistake')).toHaveCount(0)
  expect(await threads(page).count()).toBe(before)

  expectNoRealErrors(errors)
})

test('a recipient is a person the site already knows', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the composer is the same dialog on both')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/mail')
  await threads(page).first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Write' }).click()
  const compose = page.getByRole('dialog')
  // The fixture's contact. Typing part of a name has to reach an address —
  // nobody remembers `hala@client.test`, and everybody remembers Hala.
  await compose.locator('[data-slot="mail-recipients-to"] [data-slot="trigger"]').click()
  await page.getByRole('combobox').fill('Hala')
  await expect(page.getByRole('option', { name: /hala@client\.test/i }).first()).toBeVisible({
    timeout: 10_000,
  })

  await page.keyboard.press('Escape')
  await page.keyboard.press('Escape')
  expectNoRealErrors(errors)
})

test('a rule files mail, and away answers it', async ({ page, baseURL }, info) => {
  test.skip(info.project.name === 'mobile', 'the settings dialog has its own spec')
  const errors = collectConsoleErrors(page)

  await signIn(page, baseURL)
  await page.goto('/one/space/zzmock?screen=tasks')
  await page.locator('[data-slot="list-row"]').first().waitFor({ timeout: 15_000 })

  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: 'Email' }).click()

  // A rule is four words: look at this field, for this text, and file it there.
  // Anything more is a query builder, which is not what somebody sorting their
  // own mail is asking for.
  //
  // Named for this run and removed at the end. A rule is state somebody keeps,
  // so a spec that counted the whole list would pass once and then fail
  // against its own leavings — and it would race the list's first load, where
  // the count is briefly zero.
  const title = `Applicants ${Date.now()}`
  const mine = page.locator('[data-slot="mail-rule"]').filter({ hasText: title })
  await page.getByLabel('Rule', { exact: true }).fill(title)
  await page.getByLabel('This', { exact: true }).fill('applying')
  await page.getByLabel('File into').fill('Applicants')
  await page.getByRole('button', { name: 'Add rule' }).click()
  await expect(mine).toHaveCount(1)

  // It survives the round trip, which is the half a list in memory would fake.
  await page.reload()
  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: 'Email' }).click()
  await expect(mine).toHaveCount(1)

  await mine.getByRole('button', { name: `Remove ${title}` }).click()
  await expect(mine).toHaveCount(0)

  // Away is a switch and a message, not a rule: it answers, it does not file.
  // By role rather than by slot: `Checkbox` puts the attribute on its wrapper
  // and on the input inside it, so the slot matches two things.
  await page.getByRole('checkbox', { name: /Reply automatically/ }).check()
  await page.getByLabel('What it says').fill('Back on Monday.')
  await page.locator('[data-slot="mail-save-away"]').click()

  await page.reload()
  await page.getByRole('button', { name: 'Administrator' }).click()
  await page.getByRole('menuitem', { name: 'Workspace settings' }).click()
  await page.getByRole('tab', { name: 'Email' }).click()
  await expect(page.getByLabel('What it says')).toHaveValue('Back on Monday.')

  expectNoRealErrors(errors)
})
