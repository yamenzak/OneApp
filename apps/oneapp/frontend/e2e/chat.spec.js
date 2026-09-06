// The workspace assistant, in a browser.
//
// Nothing here asks a model anything. A provider call costs money and returns
// something different every time, which is the wrong shape for a suite that
// runs on every commit — so the transcript is written through the same store
// the loop writes through, and what is checked is the half a browser owns: the
// thread is in the URL, the rail lists what this person asked, an answer shows
// the lookups it came from, and a run that stopped without answering says so
// rather than drawing an empty bubble.
//
// The loop itself is `tests/test_ai_conversation.py`, where a provider can be
// faked exactly.
import { expect, test } from '@playwright/test'

import { collectConsoleErrors, expectNoRealErrors, signIn } from './auth.js'

test.beforeEach(async ({ page, baseURL }) => {
  await signIn(page, baseURL)
})

/**
 * A stored conversation, written server-side.
 *
 * Through `chat.send` would mean a provider call. Through the store means the
 * rows are exactly what a real run would have left behind — including the
 * `tool` row, which is what proves the page hides the working and keeps the
 * lookups.
 */
async function thread(page, turns, { stopped = 'answered', credits = 0.6 } = {}) {
  const res = await page.request.post(
    '/api/method/frappe.client.insert',
    { data: { doc: JSON.stringify({ doctype: 'OneSpace Chat Session',
                                    title: turns[0].content }) } },
  )
  expect(res.ok()).toBe(true)
  const session = (await res.json()).message.name

  let seq = 0
  for (const turn of turns) {
    seq += 1
    const last = seq === turns.length
    const wrote = await page.request.post('/api/method/frappe.client.insert', {
      data: { doc: JSON.stringify({
        doctype: 'OneSpace Chat Message',
        session,
        seq,
        role: turn.role,
        content: turn.content || '',
        tool_calls: turn.tool_calls ? JSON.stringify(turn.tool_calls) : '',
        tool_call_id: turn.tool_call_id || '',
        tool_name: turn.name || '',
        ...(last ? { stopped, credits } : {}),
      }) },
    })
    expect(wrote.ok()).toBe(true)
  }
  return session
}

const ASKED = { role: 'user', content: 'How many projects are open?' }
const LOOKED = {
  role: 'assistant',
  content: '',
  tool_calls: [{ id: 'c0', name: 'count_records',
                 arguments: { space: 'rua', screen: 'projects',
                              filters: [['status', '=', 'Open']] } }],
}
const ANSWERED = { role: 'tool', tool_call_id: 'c0', name: 'count_records',
                   content: '{"total": 121}' }
const REPLY = { role: 'assistant', content: '121 projects are open in RUA.' }

test('an answer shows what it looked at, and the working is not a message',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    const session = await thread(page, [ASKED, LOOKED, ANSWERED, REPLY])

    await page.goto(`/one/chat?chat=${session}`)
    const turns = page.locator('[data-slot="chat-turn"]')
    await expect(turns).toHaveCount(2)

    // The turn where the model only asked for tools has no text of its own.
    // Drawing it is an empty bubble between the question and the answer, which
    // reads as a failure; its lookup gathers onto the answer instead.
    await expect(turns.nth(1)).toContainText('121 projects are open in RUA.')
    await expect(turns.nth(1).locator('[data-slot="chat-looked-at"]'))
      .toContainText('count records — rua / projects, status = Open')

    expectNoRealErrors(errors)
  })

test('a run that stopped without answering says why', async ({ page }) => {
  const session = await thread(page, [ASKED, LOOKED, ANSWERED,
                                      { role: 'assistant', content: '' }],
                               { stopped: 'budget_spent' })

  await page.goto(`/one/chat?chat=${session}`)
  // The one case where a turn with no text is still drawn: silence is what the
  // reader would otherwise be given, and the reason is the message.
  await expect(page.locator('[data-slot="chat-turn"]').last())
    .toContainText('reached what one question may spend')
})

test('the rail lists the threads and opening one puts it in the URL',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no rail')
    // Its own title: threads are named after the question, earlier runs left
    // theirs behind, and `.first()` on a shared title opens somebody else's.
    const asked = `How many projects are open ${Date.now()}?`
    const session = await thread(page, [{ role: 'user', content: asked }, REPLY])

    await page.goto('/one/chat')
    const row = page.locator('[data-slot="chat-thread"]').filter({ hasText: asked })
    await row.first().click()

    await expect(page).toHaveURL(new RegExp(`chat=${session}`))
    await expect(page.locator('[data-slot="chat-turn"]').first()).toContainText(asked)
  })

test('a conversation can be deleted and stops being listed', async ({ page }) => {
  const session = await thread(page, [ASKED, REPLY])

  await page.goto(`/one/chat?chat=${session}`)
  await page.locator('[data-slot="chat-forget"]').click()

  // Back to a blank thread, and the server has forgotten it.
  await expect(page).toHaveURL(/\/one\/chat$/)
  const res = await page.request.get(
    `/api/method/oneapp.oneapp_core.chat.messages?session=${session}`,
  )
  expect(res.ok()).toBe(false)
})

test('the assistant appears in the rail only where it is switched on',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no rail')
    await page.goto('/one/files')

    // The dev site has the gateway configured and AI on, so it is here. The
    // absent case is the server's answer, not the browser's: `sessions()`
    // reports `available` and the rail draws nothing when it is false.
    const said = await page.request.get('/api/method/oneapp.oneapp_core.chat.sessions')
    const available = (await said.json()).message.available
    await expect(page.locator('[data-slot="chat-link"]')).toHaveCount(available ? 1 : 0)
  })
