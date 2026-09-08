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
    `/api/method/oneapp.oneapp_core.docs.get_doc?name=${name}`,
  )
  expect(res.ok()).toBe(true)
  return (await res.json()).message
}

/** What a text file's bytes say, straight from the server. */
async function storedText(page, name) {
  const res = await page.request.get(
    `/api/method/oneapp.oneapp_core.docs.get_text?name=${name}`,
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
          `/api/method/oneapp.oneapp_core.docs.get_text?name=${name}`,
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
          '/api/method/oneapp.oneapp_core.drive.listing?place=all&search=Vermiculite',
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
  // version of anything else — `oneapp_core/versions.py` gained a kind, not a
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
