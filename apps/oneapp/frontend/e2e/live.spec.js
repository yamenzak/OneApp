import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, nameInUrl, signIn } from './auth.js'

/**
 * Two people in one workbook.
 *
 * The Yjs layer has Frappe's own unit suite behind it and the relay has
 * `src/shared/lib/live/relay.test.js`; neither says whether a keystroke in one
 * browser reaches a grid in another one, which is the only claim anybody
 * cares about. So: two contexts, two accounts, one file, and the second
 * browser reads the cell back off its own engine rather than off the server —
 * the server would prove the save worked, which is a different thing and is
 * already tested.
 *
 * The other person is seeded by `scripts/seed_dev_space.py`. One account
 * cannot test this: the relay never echoes a message back to the socket that
 * sent it, which is exactly what stops a cursor from jumping under its owner.
 */

const COLLEAGUE = { user: 'robin@zzmock.test', password: 'Dev-Loop-2026!x' }

// The canvas's geometry, from `lib/sheets/canvas/constants.js` — same
// constants `sheets.spec.js` states, and stated again rather than shared so a
// change there fails both loudly.
const ROW_HEADER_W = 50
const COL_HEADER_H = 24
const COL_W = 100
const ROW_H = 24

const grid = (page) => page.locator('canvas').first()
const formulaBar = (page) => page.locator('input[name="formula-bar"]')
const cellRef = (page) => page.locator('.sn-cell-ref')

/** Click the middle of the cell at this zero-based row and column. */
const clickCell = (page, row, col) =>
  grid(page).click({
    position: {
      x: ROW_HEADER_W + col * COL_W + COL_W / 2,
      y: COL_HEADER_H + row * ROW_H + ROW_H / 2,
    },
  })

/**
 * The grid is drawn, the workbook is in it, and the room has been joined.
 *
 * All three are the same signal, which is worth knowing: collaboration does
 * not start until `get_sheet` has answered, because the first person into a
 * room seeds it and an editor that has not loaded yet would seed an empty
 * workbook over everybody else's. The loading overlay going is that moment.
 */
async function ready(page) {
  await expect(page.locator('.sn-toolbar')).toBeVisible({ timeout: 30_000 })
  await expect(grid(page)).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.sn-canvas-loading')).toHaveCount(0, { timeout: 30_000 })
}

async function openSheet(page, id) {
  await page.goto(`/one/sheets/${id}`)
  await ready(page)
}

/** A sheet of this spec's own; sharing one with another spec is how a suite
 *  starts failing for reasons that have nothing to do with it. */
async function newSheet(page) {
  await page.goto('/one/files')
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('menuitem', { name: 'Blank sheet' }).click()
  await page.waitForURL(/\/one\/sheets\//, { timeout: 30_000 })
  await ready(page)
  return nameInUrl(page, '/one/sheets/')
}

/** What this browser's own engine holds for a cell, via the formula bar. */
async function shows(page, row, col) {
  await clickCell(page, row, col)
  return formulaBar(page).inputValue()
}

const api = (page, method, body) =>
  page.evaluate(
    async ([m, b]) => {
      const res = await fetch(`/api/method/${m}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Frappe-CSRF-Token': window.csrf_token || '',
        },
        body: JSON.stringify(b),
      })
      return (await res.json()).message
    },
    [method, body],
  )

test.describe('a workbook with two people in it', () => {
  test.describe.configure({ mode: 'serial' })

  test('a cell one person types turns up in the other one\'s grid', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a socket')

    const owner = await browser.newContext()
    const guest = await browser.newContext()
    const ownerPage = await owner.newPage()
    const guestPage = await guest.newPage()
    const errors = collectConsoleErrors(guestPage)

    await signIn(ownerPage, baseURL)
    await signIn(guestPage, baseURL, COLLEAGUE)

    const id = await newSheet(ownerPage)

    try {
      await api(ownerPage, 'oneapp.onestorage.share_with', {
        file: id, user: COLLEAGUE.user, level: 'write',
      })

      await openSheet(guestPage, id)

      // Both are in the room now. The owner types; nothing tells the guest.
      await clickCell(ownerPage, 0, 0)
      await ownerPage.keyboard.type('147')
      await ownerPage.keyboard.press('Enter')

      // And it is in the other browser's engine, not merely on the server.
      await expect
        .poll(() => shows(guestPage, 0, 0), { timeout: 20_000 })
        .toBe('147')

      // The other direction, and a second cell, so this is a live connection
      // rather than one lucky delivery.
      await clickCell(guestPage, 1, 0)
      await guestPage.keyboard.type('=A1*2')
      await guestPage.keyboard.press('Enter')

      // The formula crosses, not the answer: the engine on the other side
      // recomputes it. That is the whole reason nothing about the formula
      // engine is ever on the wire.
      await expect
        .poll(() => shows(ownerPage, 1, 0), { timeout: 20_000 })
        .toBe('=A1*2')
      await expect(cellRef(ownerPage)).toHaveText('A2')

      expectNoRealErrors(errors)
    } finally {
      await api(ownerPage, 'oneapp.onestorage.unshare_with', {
        file: id, user: COLLEAGUE.user,
      })
      await api(ownerPage, 'oneapp.onestorage.trash', { names: id }).catch(() => {})
      await owner.close()
      await guest.close()
    }
  })

  test('each person is a face in the other one\'s presence strip', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'the presence strip is a desktop control')

    const owner = await browser.newContext()
    const guest = await browser.newContext()
    const ownerPage = await owner.newPage()
    const guestPage = await guest.newPage()

    await signIn(ownerPage, baseURL)
    await signIn(guestPage, baseURL, COLLEAGUE)

    const id = await newSheet(ownerPage)

    try {
      await api(ownerPage, 'oneapp.onestorage.share_with', {
        file: id, user: COLLEAGUE.user, level: 'write',
      })
      await openSheet(guestPage, id)

      // One face each, and never your own — the strip is who *else* is here.
      await expect(ownerPage.locator('.sn-presence .sn-presence-avatar'))
        .toHaveCount(1, { timeout: 20_000 })
      await expect(guestPage.locator('.sn-presence .sn-presence-avatar'))
        .toHaveCount(1, { timeout: 20_000 })

      // And it goes when they do, rather than leaving a ghost behind.
      await guestPage.close()
      await expect(ownerPage.locator('.sn-presence .sn-presence-avatar'))
        .toHaveCount(0, { timeout: 20_000 })
    } finally {
      await api(ownerPage, 'oneapp.onestorage.unshare_with', {
        file: id, user: COLLEAGUE.user,
      })
      await api(ownerPage, 'oneapp.onestorage.trash', { names: id }).catch(() => {})
      await owner.close()
      await guest.close()
    }
  })
})

test.describe('a document with two people in it', () => {
  test.describe.configure({ mode: 'serial' })

  const prose = (page) => page.locator('.ProseMirror').first()

  /** Make one through the New menu, and answer with the id it landed on. */
  async function newDocument(page) {
    await page.goto('/one/files')
    await page.getByRole('button', { name: 'New', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Document' }).click()
    await page.waitForURL(/\/one\/docs\//, { timeout: 30_000 })
    // The editor does not mount until the room has answered — see
    // `modules/onedoc/lib/live.js`. Waiting for the prose is waiting for that.
    await expect(prose(page)).toBeVisible({ timeout: 30_000 })
    return nameInUrl(page, '/one/docs/')
  }

  test('a sentence one person types appears in the other one\'s prose', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a socket')

    const owner = await browser.newContext()
    const guest = await browser.newContext()
    const ownerPage = await owner.newPage()
    const guestPage = await guest.newPage()
    const errors = collectConsoleErrors(guestPage)

    await signIn(ownerPage, baseURL)
    await signIn(guestPage, baseURL, COLLEAGUE)

    const id = await newDocument(ownerPage)

    try {
      await api(ownerPage, 'oneapp.onestorage.share_with', {
        file: id, user: COLLEAGUE.user, level: 'write',
      })

      await guestPage.goto(`/one/docs/${id}`)
      await expect(prose(guestPage)).toBeVisible({ timeout: 30_000 })

      await prose(ownerPage).click()
      await ownerPage.keyboard.type('The quiet part out loud.')

      await expect(prose(guestPage)).toContainText('The quiet part out loud.', { timeout: 20_000 })

      // The other direction, into the same paragraph — which is the case a
      // CRDT exists for and the reason the document could not take the
      // grid's answer.
      await prose(guestPage).click()
      await guestPage.keyboard.press('End')
      await guestPage.keyboard.type(' And then some.')

      await expect(prose(ownerPage)).toContainText('The quiet part out loud. And then some.', { timeout: 20_000 })

      // And each sees the other at the top of the page. The strip renders
      // nothing at all when nobody else is here, so its being visible is the
      // whole assertion.
      await expect(ownerPage.locator('[data-slot="presence"]'))
        .toBeVisible({ timeout: 20_000 })
      await expect(guestPage.locator('[data-slot="presence"]'))
        .toBeVisible({ timeout: 20_000 })

      expectNoRealErrors(errors)
    } finally {
      await api(ownerPage, 'oneapp.onestorage.unshare_with', {
        file: id, user: COLLEAGUE.user,
      })
      await api(ownerPage, 'oneapp.onestorage.trash', { names: id }).catch(() => {})
      await owner.close()
      await guest.close()
    }
  })

  test('what two people wrote is what the server ends up with', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a socket')

    const owner = await browser.newContext()
    const guest = await browser.newContext()
    const ownerPage = await owner.newPage()
    const guestPage = await guest.newPage()

    await signIn(ownerPage, baseURL)
    await signIn(guestPage, baseURL, COLLEAGUE)

    const id = await newDocument(ownerPage)

    try {
      await api(ownerPage, 'oneapp.onestorage.share_with', {
        file: id, user: COLLEAGUE.user, level: 'write',
      })
      await guestPage.goto(`/one/docs/${id}`)
      await expect(prose(guestPage)).toBeVisible({ timeout: 30_000 })

      await prose(ownerPage).click()
      await ownerPage.keyboard.type('Owner wrote this.')
      await expect(prose(guestPage)).toContainText('Owner wrote this.', { timeout: 20_000 })

      await prose(guestPage).click()
      await guestPage.keyboard.press('End')
      await guestPage.keyboard.type(' Guest wrote this.')

      // The Y.Doc is scratch and the stored document is the store —
      // `docs/WRITER.md` §3 — so the thing worth asserting is not that the
      // two screens agree but that what got written down is both people's
      // work. `content` is the ProseMirror JSON the editor saves; the text
      // is in it whatever the marks around it turn out to be.
      await expect
        .poll(async () => {
          const res = await ownerPage.request.get(
            `/api/method/oneapp.onedoc.get_doc?name=${id}`,
          )
          return (await res.json()).message?.content || ''
        }, { timeout: 30_000 })
        .toContain('Guest wrote this.')
    } finally {
      await api(ownerPage, 'oneapp.onestorage.unshare_with', {
        file: id, user: COLLEAGUE.user,
      })
      await api(ownerPage, 'oneapp.onestorage.trash', { names: id }).catch(() => {})
      await owner.close()
      await guest.close()
    }
  })
})
