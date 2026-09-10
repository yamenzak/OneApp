import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, nameInUrl, signIn } from './auth.js'

/**
 * Documents, in a browser.
 *
 * The editor is frappe-ui's and comes with its own tests; none of them says
 * whether a person can get to a document from the Drive, whether what they
 * typed reaches our server, or whether the version that was kept can be put
 * back. That is what this asks.
 *
 * A document is made by the test rather than seeded, for the reason the sheets
 * spec gives: a test that shares a fixture with another test is a test that
 * fails when the other one is edited.
 */

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

const prose = (page) => page.locator('.ProseMirror').first()

/** What the server holds for this document, whatever the browser thinks. */
async function stored(page, name) {
  const res = await page.request.get(
    `/api/method/oneapp.onedoc.get_doc?name=${name}`,
  )
  expect(res.ok()).toBe(true)
  return (await res.json()).message
}

/** What a text file's bytes say, straight from the server. */
async function storedText(page, name) {
  const res = await page.request.get(
    `/api/method/oneapp.onedoc.get_text?name=${name}`,
  )
  expect(res.ok()).toBe(true)
  return (await res.json()).message.content || ''
}

/** Make one through the New menu, and answer with the id it landed on. */
async function newDocument(page) {
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Document' }).click()
  await page.waitForURL(/\/one\/docs\//)
  await expect(prose(page)).toBeVisible()
  return nameInUrl(page, '/one/docs/')
}

test('a document is made from the Drive and opens in an editor', async ({ page }) => {
  const errors = collectConsoleErrors(page)

  const name = await newDocument(page)
  expect(name).toBeTruthy()

  // The trail says where you are, the way it does on every other page. Scoped
  // to the breadcrumb: the rail has a Files link too, and both are correct.
  await expect(
    page.locator('[data-slot="breadcrumb"]').getByRole('link', { name: 'Files' }),
  ).toBeVisible()

  expectNoRealErrors(errors)
})

test('what was typed reaches the server', async ({ page }) => {
  const name = await newDocument(page)

  await prose(page).click()
  await page.keyboard.type('Retention is five per cent.')

  // The save is debounced, so this is polled rather than read once.
  await expect
    .poll(async () => (await stored(page, name)).content, { timeout: 20_000 })
    .toContain('Retention is five per cent.')

  // And it survives the page going away, which is the only proof the save
  // reached us rather than sitting in a ref.
  await page.reload()
  await expect(prose(page)).toContainText('Retention is five per cent.')
})

test('a heading shows up in the outline and the count counts', async ({ page }) => {
  await newDocument(page)

  // Two, because the rail does not draw itself for one: a table of contents
  // listing a single heading says nothing the heading does not already say.
  await prose(page).click()
  await page.keyboard.type('# Scope of works')
  await page.keyboard.press('Enter')
  await page.keyboard.type('Two padel courts.')
  await page.keyboard.press('Enter')
  await page.keyboard.type('## Programme')
  await page.keyboard.press('Enter')
  await page.keyboard.type('Eight weeks.')

  // A rail on a laptop, a dropdown on a phone — the same headings either way,
  // from one composable. Which one is on screen is the viewport's business, so
  // the test asks whichever is showing.
  const rail = page.getByRole('navigation', { name: 'Outline' })
  if (await rail.isVisible()) {
    await expect(rail).toContainText('Scope of works')
    await expect(rail).toContainText('Programme')
  } else {
    await page.getByRole('button', { name: 'Outline' }).click()
    await expect(page.getByRole('menuitem', { name: 'Scope of works' })).toBeVisible()
    await expect(page.getByRole('menuitem', { name: 'Programme' })).toBeVisible()
    await page.keyboard.press('Escape')
  }
  await expect(page.getByText(/\d+ words/)).toBeVisible()
})

test('a version can be kept by name and put back', async ({ page }) => {
  const name = await newDocument(page)

  await prose(page).click()
  await page.keyboard.type('Five per cent.')
  await expect
    .poll(async () => (await stored(page, name)).content, { timeout: 20_000 })
    .toContain('Five per cent.')

  await page.getByRole('button', { name: 'Version history' }).click()
  await page.getByRole('button', { name: 'Save this version' }).click()
  await page.getByLabel('What this version is').fill('Signed off')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByText('Signed off')).toBeVisible()

  // Now move on, and put the named one back.
  await prose(page).click()
  await page.keyboard.press('Control+a')
  await page.keyboard.type('Ten per cent.')
  await expect
    .poll(async () => (await stored(page, name)).content, { timeout: 20_000 })
    .toContain('Ten per cent.')

  await page
    .getByRole('button', { name: 'What to do with this version' })
    .first()
    .click()
  await page.getByRole('menuitem', { name: 'Restore this version' }).click()

  await expect
    .poll(async () => (await stored(page, name)).content, { timeout: 20_000 })
    .toContain('Five per cent.')
})

test('a markdown file is made, edited as text, and downloads as itself', async ({ page }) => {
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Markdown file' }).click()
  await page.waitForURL(/\/one\/docs\//)

  const name = nameInUrl(page, '/one/docs/')

  // A text file is a text editor, not the prose one: the bytes are the file.
  await expect(page.locator('.cm-content')).toBeVisible()
  await expect(prose(page)).toHaveCount(0)

  await page.locator('.cm-content').click()
  await page.keyboard.type('# Notes')

  await expect
    .poll(
      async () => {
        const res = await page.request.get(
          `/api/method/oneapp.onedoc.get_text?name=${name}`,
        )
        return res.ok() ? (await res.json()).message.content : ''
      },
      { timeout: 20_000 },
    )
    .toContain('# Notes')
})

test('a document is found by what it says, not only by its name', async ({ page }) => {
  const name = await newDocument(page)

  await prose(page).click()
  await page.keyboard.type('Vermiculite screed to falls.')

  // Polled on the search itself rather than on the stored HTML: the save is
  // debounced, and what this test is actually about is whether the file
  // manager can find a document by a word inside it.
  await expect
    .poll(
      async () => {
        const found = await page.request.get(
          '/api/method/oneapp.onestorage.listing?place=all&search=Vermiculite',
        )
        if (!found.ok()) return []
        return (await found.json()).message.files.map((one) => one.name)
      },
      { timeout: 20_000 },
    )
    .toContain(name)
})

test('a code file keeps versions too, and an old one goes back', async ({ page }) => {
  // The third store. A version of a `.py` is a blob and a moment like a
  // version of anything else — `shared/versions.py` gained a kind, not a
  // second mechanism — and this is the proof that the panel, the policy and
  // the restore all reach it.
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Code', exact: true }).click()
  await page.locator('[data-slot="language-option"]:has-text("Python")').click()
  await page.waitForURL(/\/one\/docs\//)

  const name = nameInUrl(page, '/one/docs/')
  const cm = page.locator('.cm-content')
  await cm.waitFor({ timeout: 20_000 })

  await cm.click()
  await page.keyboard.type('RATE = 0.05')
  await expect
    .poll(() => storedText(page, name), { timeout: 20_000 })
    .toContain('RATE = 0.05')

  await page.locator('[data-slot="code-history"]').click()
  await page.getByRole('button', { name: 'Save this version' }).click()
  await page.getByLabel('What this version is').fill('Signed off')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByText('Signed off')).toBeVisible()

  // Move on, then put the named one back.
  await cm.click()
  await page.keyboard.press('ControlOrMeta+a')
  await page.keyboard.type('RATE = 0.10')
  await expect
    .poll(() => storedText(page, name), { timeout: 20_000 })
    .toContain('RATE = 0.10')

  await page
    .getByRole('button', { name: 'What to do with this version' })
    .first()
    .click()
  await page.getByRole('menuitem', { name: 'Restore this version' }).click()

  await expect
    .poll(() => storedText(page, name), { timeout: 20_000 })
    .toContain('RATE = 0.05')
})

/**
 * A document written about a record.
 *
 * The claim is not that a token renders — a unit test says that. It is that
 * the whole chain holds in a browser: a document attached to a quotation
 * knows it, the field list is the doctype's own, inserting one puts the
 * record's number in the prose, and fixing the fields turns the number into
 * words that stop moving.
 *
 * The record is found rather than named, for the reason the chat spec learnt
 * the hard way: a spec pinned to an auto-numbered id fails the first time
 * somebody sweeps the fixture.
 */
async function aQuotation(page) {
  const res = await page.request.get(
    '/api/method/frappe.client.get_list'
    + '?doctype=Quotation&limit_page_length=1&fields=["name"]',
  )
  expect(res.ok()).toBe(true)
  const rows = (await res.json()).message || []
  expect(rows.length, 'the fixture has a quotation').toBeGreaterThan(0)
  return rows[0].name
}

test('a document about a record carries that record fields', async ({ page }) => {
  const errors = collectConsoleErrors(page)
  const quote = await aQuotation(page)

  // Attached at creation, which is what binding *is* — see
  // `apps/oneapp/oneapp/shared/binding.py`.
  const made = await page.request.post('/api/method/oneapp.onedoc.make', {
    data: { title: 'Covering letter', doctype: 'Quotation', docname: quote },
  })
  expect(made.ok()).toBe(true)
  const name = (await made.json()).message.name

  await page.goto(`/one/docs/${name}`)
  await expect(prose(page)).toBeVisible()

  // The strip says what it is about. That is the freshness answer, on screen.
  await expect(page.getByText(`About ${quote}`)).toBeVisible()

  await page.locator('[data-slot="fields-insert"]').click()
  // `ID` rather than a money field: every doctype has it, its label is the
  // same everywhere, and what it resolves to is a string this test already
  // knows — so the assertion below is about the *value*, not about a token
  // having appeared.
  await page.getByRole('menuitem', { name: 'ID', exact: true }).click()

  // The record's own id, rendered in the prose.
  await expect(prose(page).getByText(quote, { exact: false })).toBeVisible()

  // And a node rather than typed text, on disk.
  await expect
    .poll(async () => (await stored(page, name)).content, { timeout: 20_000 })
    .toContain('recordField')

  // Fixed: the token becomes words, and the document stops asking. The id
  // is still there — freezing keeps what it says, it does not remove it.
  await page.locator('[data-slot="fields-settle"]').click()
  await expect
    .poll(async () => (await stored(page, name)).content, { timeout: 20_000 })
    .not.toContain('recordField')
  expect((await stored(page, name)).content).toContain(quote)

  expectNoRealErrors(errors)
})
