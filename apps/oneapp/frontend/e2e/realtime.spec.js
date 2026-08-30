import { expect, test } from '@playwright/test'
import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

// The other person on the workspace, seeded by scripts/seed_dev_space.py.
// Frappe's realtime will not tell you that *you* are looking at a record —
// "dont send update to self", says the handler — so the row of faces cannot
// be shown, or tested, with one user.
const COLLEAGUE = { user: 'robin@zzmock.test', password: 'Dev-Loop-2026!x' }

// Two browsers, one record. Everything here is Frappe's own realtime — the
// list room, the document room, and the open-document room that carries who is
// looking at what — so what is being checked is that we joined the right rooms
// and act on what arrives, not that socket.io works.
//
// The dev server has no socket.io proxy, so `lib/socket.js` addresses the
// bench's port directly in development. That is the same code path production
// uses behind nginx, minus the proxy.
test.describe('realtime', () => {
  test.describe.configure({ mode: 'serial' })

  test('a list follows the site', async ({ browser, baseURL }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a socket')
    const reader = await browser.newContext()
    const writer = await browser.newContext()
    const readerPage = await reader.newPage()
    const writerPage = await writer.newPage()
    const errors = collectConsoleErrors(readerPage)

    await signIn(readerPage, baseURL)
    await signIn(writerPage, baseURL)

    await readerPage.goto('/one/space/zzmock')
    await expect(readerPage.locator('[data-slot="list-row"]').first()).toBeVisible()

    // The other browser renames a task. Nothing tells the first one to look.
    const original = 'Book the van for Thursday'
    const renamed = `ZZ Realtime ${Date.now() % 10000}`
    await writerPage.goto('/one/space/zzmock')
    await writerPage.getByText(original).first().click()
    const pane = writerPage.locator('[data-slot="record-pane"]')

    // In a `finally`, because a rename that is not put back is a fixture the
    // next run cannot find — this test spent one run failing on litter it had
    // left itself.
    try {
      await pane.getByLabel('Description').fill(renamed)
      await pane.getByRole('button', { name: 'Save' }).click()

      // And it turns up, without a reload. The refetch is coalesced, so this
      // is allowed a moment — a bulk import publishes hundreds of these a
      // second and one refetch per event is a list that spends its afternoon
      // reloading.
      await expect(readerPage.getByText(renamed).first()).toBeVisible({ timeout: 15000 })
    } finally {
      await pane.getByLabel('Description').fill(original)
      await pane.getByRole('button', { name: 'Save' }).click()
      await expect(pane.getByLabel('Description')).toHaveValue(original)
    }
    expectNoRealErrors(errors)
    await reader.close()
    await writer.close()
  })

  test('a record says who else is in it, and when it changed under you', async ({
    browser,
    baseURL,
  }, info) => {
    test.skip(info.project.name === 'mobile', 'one viewport is enough for a socket')
    const first = await browser.newContext()
    const second = await browser.newContext()
    const firstPage = await first.newPage()
    const secondPage = await second.newPage()
    const errors = collectConsoleErrors(firstPage)

    await signIn(firstPage, baseURL)
    await signIn(secondPage, baseURL, COLLEAGUE)

    const open = async (page) => {
      await page.goto('/one/space/zzmock')
      await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible()
      await page.getByText('File Q3 returns').first().click()
      await expect(page.locator('[data-slot="record-pane"]')).toBeVisible()
    }

    await open(firstPage)
    await open(secondPage)

    // Frappe's open-document room, and the other person's face in it. One
    // face, not two: a row that told you *you* were looking at this would be
    // telling you nothing.
    const faces = firstPage.locator('[data-slot="viewer"]')
    await expect(faces).toHaveCount(1, { timeout: 15000 })

    // And a save in the other browser says so here rather than doing anything
    // about it: the reader may be halfway through typing.
    const pane = secondPage.locator('[data-slot="record-pane"]')
    await pane.getByLabel('Priority', { exact: true }).click()
    await secondPage.getByRole('option', { name: 'Low', exact: true }).click()
    await pane.getByRole('button', { name: 'Save' }).click()

    await expect(
      firstPage.getByText('Someone else changed this'),
    ).toBeVisible({ timeout: 15000 })

    await info.attach(`realtime-${info.project.name}`, {
      body: await firstPage.screenshot(),
      contentType: 'image/png',
    })

    // Taking their version is asked for, never done.
    await firstPage.getByRole('button', { name: 'Reload it' }).click()
    await expect(firstPage.getByText('Someone else changed this')).toHaveCount(0)
    expectNoRealErrors(errors)
    await first.close()
    await second.close()
  })
})
