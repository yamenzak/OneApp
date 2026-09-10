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

  test('somebody who may only read still watches it happen', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a socket')

    // The case that was silently broken until a stranger on a read link found
    // it: a reader may not *send* into a room, and asking for the file as it
    // stands used to be a send — so a reader who arrived after somebody else
    // was never handed the document and sat on the last save while the other
    // person typed. `oneapp_ask` is the fix and this is the claim.
    const owner = await browser.newContext()
    const guest = await browser.newContext()
    const ownerPage = await owner.newPage()
    const guestPage = await guest.newPage()

    await signIn(ownerPage, baseURL)
    await signIn(guestPage, baseURL, COLLEAGUE)

    const id = await newSheet(ownerPage)

    try {
      await api(ownerPage, 'oneapp.onestorage.share_with', {
        file: id, user: COLLEAGUE.user, level: 'read',
      })

      // Typed *before* the reader opens it and before any autosave, so what
      // arrives can only have come through the room.
      await clickCell(ownerPage, 0, 0)
      await ownerPage.keyboard.type('613')
      await ownerPage.keyboard.press('Enter')

      await openSheet(guestPage, id)
      await expect
        .poll(() => shows(guestPage, 0, 0), { timeout: 20_000 })
        .toBe('613')
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

test.describe('what people say about a file', () => {
  test.describe.configure({ mode: 'serial' })

  const prose = (page) => page.locator('.ProseMirror').first()
  const chat = (page) => page.locator('[data-slot="file-chat"]')

  test('a note in one browser lands in the other, and notifies who it names', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'the notes rail is a desktop control')

    const owner = await browser.newContext()
    const guest = await browser.newContext()
    const ownerPage = await owner.newPage()
    const guestPage = await guest.newPage()

    await signIn(ownerPage, baseURL)
    await signIn(guestPage, baseURL, COLLEAGUE)

    await ownerPage.goto('/one/files')
    await ownerPage.getByRole('button', { name: 'New', exact: true }).click()
    await ownerPage.getByRole('menuitem', { name: 'Document' }).click()
    await ownerPage.waitForURL(/\/one\/docs\//, { timeout: 30_000 })
    await expect(prose(ownerPage)).toBeVisible({ timeout: 30_000 })
    const id = nameInUrl(ownerPage, '/one/docs/')

    try {
      await api(ownerPage, 'oneapp.onestorage.share_with', {
        file: id, user: COLLEAGUE.user, level: 'write',
      })
      await guestPage.goto(`/one/docs/${id}`)
      await expect(prose(guestPage)).toBeVisible({ timeout: 30_000 })

      // Both open the rail. Closed by default, because a document nobody has
      // said anything about is most of them.
      await ownerPage.locator('[data-slot="notes-toggle"]').click()
      await guestPage.locator('[data-slot="notes-toggle"]').click()
      await expect(chat(ownerPage)).toBeVisible()
      await expect(chat(guestPage)).toBeVisible()

      const asked = `Are these March rates? ${Date.now() % 100000}`
      await chat(ownerPage).getByPlaceholder('Say something about this file').fill(asked)
      await chat(ownerPage).getByRole('button', { name: 'Send' }).click()

      // In the other browser, without a reload and without a refetch.
      await expect(chat(guestPage).locator('[data-slot="note"]'))
        .toContainText(asked, { timeout: 20_000 })

      // And it is a real `Comment` on the File, which is the whole reason it
      // is stored this way: the same feed, the same timeline, and mentions
      // that notify for nothing.
      const rows = await ownerPage.request.get(
        `/api/method/oneapp.onestorage.notes?file=${id}`,
      )
      const found = (await rows.json()).message
      expect(found.count).toBe(1)
      expect(found.notes[0].content).toContain(asked)
    } finally {
      await api(ownerPage, 'oneapp.onestorage.unshare_with', {
        file: id, user: COLLEAGUE.user,
      })
      await api(ownerPage, 'oneapp.onestorage.trash', { names: id }).catch(() => {})
      await owner.close()
      await guest.close()
    }
  })

  test('a note on a cell turns up in the other person\'s grid', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'the note panel is a desktop control')

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

      // Shift+F2 on the selected cell is the note. The engine is Frappe's and
      // so is the panel; what is being checked is the binding under them.
      await clickCell(ownerPage, 0, 0)
      await ownerPage.keyboard.press('Shift+F2')
      const said = `Check this against the survey ${Date.now() % 100000}`
      await ownerPage.locator('.sn-comment-panel textarea, .sn-comment-panel input').first().fill(said)
      await ownerPage.keyboard.press('Enter')

      // The other grid, on the same cell.
      await clickCell(guestPage, 0, 0)
      await guestPage.keyboard.press('Shift+F2')
      await expect(guestPage.locator('.sn-comment-panel'))
        .toContainText(said, { timeout: 20_000 })
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

/**
 * A file somebody was sent, opened by somebody with no account here.
 *
 * The only surface in this product a stranger can reach, so it is the only
 * one where "the permission check is somewhere else" is not an answer. Both
 * browsers below are real: the owner is signed in and the other context has
 * never seen a login form, which is the whole point — a spec that signed the
 * second browser in would exercise the ordinary editor through a different
 * URL and prove nothing.
 */
test.describe('a link somebody was sent', () => {
  test.describe.configure({ mode: 'serial' })

  const prose = (page) => page.locator('.ProseMirror').first()
  const bar = (page) => page.locator('[data-slot="link-bar"]')

  /** A link on this file, and the secret out of the URL it came back with. */
  async function makeLink(page, file, level) {
    const row = await api(page, 'oneapp.onestorage.make_link', {
      file, days: 7, label: 'For the consultant', level,
    })
    // The url, not the secret: `make_link` answers with the door rather than
    // the key, and for a workbook or a document that door is this page.
    return String(row.url).split('/one/link/')[1]
  }

  /** A document of this spec's own, with a sentence already in it. */
  async function newDocument(page) {
    await page.goto('/one/files')
    await page.getByRole('button', { name: 'New', exact: true }).click()
    await page.getByRole('menuitem', { name: 'Document' }).click()
    await page.waitForURL(/\/one\/docs\//, { timeout: 30_000 })
    await expect(prose(page)).toBeVisible({ timeout: 30_000 })
    return nameInUrl(page, '/one/docs/')
  }

  test('a stranger with a write link edits it, and the owner watches', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a socket')

    const owner = await browser.newContext()
    // No `signIn`. This context has no cookie, no session and no account, and
    // that is the claim.
    const street = await browser.newContext()
    const ownerPage = await owner.newPage()
    const strangerPage = await street.newPage()
    const errors = collectConsoleErrors(strangerPage)

    await signIn(ownerPage, baseURL)
    const id = await newDocument(ownerPage)

    try {
      await prose(ownerPage).click()
      await ownerPage.keyboard.type('The rate is under review.')

      const secret = await makeLink(ownerPage, id, 'write')
      await strangerPage.goto(`/one/link/${secret}`)

      // The file, the label whoever shared it typed, and what the link allows.
      await expect(bar(strangerPage)).toBeVisible({ timeout: 30_000 })
      await expect(bar(strangerPage)).toContainText('You can edit this')
      await expect(prose(strangerPage)).toContainText('The rate is under review.', {
        timeout: 30_000,
      })

      // None of the workspace came with it.
      await expect(strangerPage.locator('[data-slot="shell-topbar"]')).toHaveCount(0)

      // And the stranger has the pen — live, into the owner's open editor,
      // through the same relay two colleagues use.
      await prose(strangerPage).click()
      await strangerPage.keyboard.press('End')
      await strangerPage.keyboard.type(' Please confirm by Friday.')
      await expect(prose(ownerPage)).toContainText('Please confirm by Friday.', {
        timeout: 20_000,
      })

      // Written down, not merely on two screens.
      await expect
        .poll(async () => {
          const res = await ownerPage.request.get(
            `/api/method/oneapp.onedoc.get_doc?name=${id}`,
          )
          return (await res.json()).message?.content || ''
        }, { timeout: 30_000 })
        .toContain('Please confirm by Friday.')

      expectNoRealErrors(errors)
    } finally {
      await api(ownerPage, 'oneapp.onestorage.trash', { names: id }).catch(() => {})
      await owner.close()
      await street.close()
    }
  })

  test('a read link opens the same document and hands over no pen', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a socket')

    const owner = await browser.newContext()
    const street = await browser.newContext()
    const ownerPage = await owner.newPage()
    const strangerPage = await street.newPage()

    await signIn(ownerPage, baseURL)
    const id = await newDocument(ownerPage)

    try {
      await prose(ownerPage).click()
      await ownerPage.keyboard.type('Final, do not change.')

      const secret = await makeLink(ownerPage, id, 'read')
      await strangerPage.goto(`/one/link/${secret}`)

      await expect(bar(strangerPage)).toContainText('Read only', { timeout: 30_000 })
      await expect(prose(strangerPage)).toContainText('Final, do not change.', {
        timeout: 30_000,
      })
      // Not a hidden toolbar or a disabled button — the editor itself.
      await expect(prose(strangerPage)).toHaveAttribute('contenteditable', 'false')

      // And the endpoint says the same thing, which is where it matters: a
      // page can be got at with a console open.
      const refused = await strangerPage.request.post(
        '/api/method/oneapp.onestorage.save_file',
        { data: { secret, payload: '{}' }, failOnStatusCode: false },
      )
      expect(refused.status()).toBe(403)
    } finally {
      await api(ownerPage, 'oneapp.onestorage.trash', { names: id }).catch(() => {})
      await owner.close()
      await street.close()
    }
  })
})
