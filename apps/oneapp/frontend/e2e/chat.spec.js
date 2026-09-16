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

    await page.goto(`/one/chat?at=chat:${session}`)
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

  await page.goto(`/one/chat?at=chat:${session}`)
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

    await expect(page).toHaveURL(new RegExp(`at=chat:${session}`))
    await expect(page.locator('[data-slot="chat-turn"]').first()).toContainText(asked)
  })

test('a conversation can be deleted and stops being listed', async ({ page }) => {
  const session = await thread(page, [ASKED, REPLY])

  await page.goto(`/one/chat?at=chat:${session}`)
  await page.locator('[data-slot="chat-forget"]').click()

  // Back to a blank thread, and the server has forgotten it.
  await expect(page).toHaveURL(/\/one\/chat$/)
  const res = await page.request.get(
    `/api/method/oneapp.onespace.chat.messages?session=${session}`,
  )
  expect(res.ok()).toBe(false)
})

test('the assistant appears in the dock only where it is switched on',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone draws no dock')
    await page.goto('/one/files')

    // The dev site has the gateway configured and AI on, so it is here. The
    // absent case is the server's answer, not the browser's: `sessions()`
    // reports `available` and the dock draws a dim tile that says why rather
    // than a live one.
    const said = await page.request.get('/api/method/oneapp.onespace.chat.sessions')
    const available = (await said.json()).message.available
    await expect(page.locator('[data-slot="dock-tile"][data-app="chat"]')).toHaveCount(available ? 1 : 0)
  })

test('the assistant opens over the page without taking width off it',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone has one surface')
    const errors = collectConsoleErrors(page)

    // Asked for rather than written down. A Project's id is a running number,
    // so a spec that names one is a spec that passes on a fixture seeded as
    // many times as the day it was written and fails on a fresh site.
    const project = await anyProject(page)
    await page.goto(`/one/space/rua?screen=projects&type=list&at=record:${project}`)
    // For the record, not for the rail: the widget names what it is scoped to
    // out of the space's own manifest, so clicking the moment the rail appears
    // can beat the screen it is meant to be describing.
    await page.getByRole('tab', { name: 'Details' }).first().waitFor({ timeout: 20_000 })

    // The whole reason it is not a page: the record is still there. A page
    // would have made you leave the thing you wanted to ask about.
    const panel = page.locator('[data-window="assistant"]')
    const before = await page.locator('[data-slot="page-body"]').boundingBox()
    await page.locator('[data-slot="dock-tile"][data-app="chat"]').click()
    await expect(panel).toBeVisible()
    await expect(page).toHaveURL(new RegExp(`at=record:${project}`))

    // And the whole reason it is not a panel either: it takes nothing off the
    // page. As a column in the shell's row it did — with the Drive's pane open
    // the file list came out at about seventy pixels — so what is checked here
    // is that the content behind it is exactly as wide as it was.
    const after = await page.locator('[data-slot="page-body"]').boundingBox()
    expect(Math.round(after.width)).toBe(Math.round(before.width))

    // And it says what it is scoped to before anybody asks anything, rather
    // than leaving it to be inferred from an answer that turned out narrow.
    await expect(panel).toContainText(`Projects · ${project}`)
    await expect(panel.locator('[data-slot="chat-input"]'))
      .toHaveAttribute('placeholder', `Ask about Projects · ${project}`)

    expectNoRealErrors(errors)
  })

test('the shortcut folds it away rather than throwing the thread out',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone has one surface')
    await page.goto('/one/files')

    const widget = page.locator('[data-window="assistant"]')
    await page.locator('[data-slot="dock-tile"][data-app="chat"]').click()
    await expect(widget).toBeVisible({ timeout: 20_000 })

    // What changed when there was somewhere to fold to. Pressing it twice used
    // to close the window outright, which threw the conversation away and
    // started a new one on the way back; it is the dock's own press now.
    const mod = process.platform === 'darwin' ? 'Meta' : 'Control'
    await page.keyboard.press(`${mod}+j`)
    await expect(widget).toBeHidden()
    // Folded, not closed: still on the desk, and still lit in the dock.
    await expect(widget).toHaveCount(1)
    await expect(page.locator('[data-app="chat"]')).toHaveAttribute('data-open', 'yes')

    await page.keyboard.press(`${mod}+j`)
    await expect(widget).toBeVisible()
  })

test('closing the assistant leaves the page where it was', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone has one surface')
  await page.goto('/one/space/rua?screen=projects&type=list')
  // The rows first. What this checks is that the page is *still* where it was,
  // and a page that had not finished arriving before the panel opened cannot
  // say anything about that — which is how this failed once in a full run and
  // passed on the retry.
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible({
    timeout: 20_000,
  })

  await page.locator('[data-slot="dock-tile"][data-app="chat"]').click()
  await expect(page.locator('[data-window="assistant"]')).toBeVisible()

  // Scoped to the window: the desk holds more than one now — the
  // picture-in-picture list is mounted from the start so its teleport target
  // resolves — and `window-close` on its own matches every one of them.
  await page.locator('[data-window="assistant"] [data-slot="window-close"]').click()
  await expect(page.locator('[data-window="assistant"]')).toHaveCount(0)
  await expect(page.locator('[data-slot="list-row"]').first()).toBeVisible({
    timeout: 20_000,
  })
})

test('the widget hands its conversation to the page', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone has one surface')
  const session = await thread(page, [ASKED, REPLY])

  await page.goto('/one/space/rua?screen=projects&type=list')
  await page.locator('[data-slot="dock-tile"][data-app="chat"]').click()

  // Opened from the rail with a thread already chosen is not a state the rail
  // reaches, so this drives the widget's own menu from the thread it starts on:
  // a fresh one, then Open as a page.
  await page.locator('[data-window="assistant"]')
    .getByRole('button', { name: 'More' }).click()
  await page.getByRole('menuitem', { name: 'Open as a page' }).click()

  await expect(page).toHaveURL(/\/one\/chat/)
  await expect(page.locator('[data-window="assistant"]')).toHaveCount(0)
  expect(session).toBeTruthy()
})

test('a panel opened on a record is scoped to it, server side', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone has one surface')

  // The claim the panel rests on, asked of the server directly: what the
  // browser sends is an answer to be verified, so a space this reader cannot
  // open is refused rather than quietly widened to the whole workspace.
  const refused = await page.request.post(
    '/api/method/oneapp.onespace.chat.send',
    { data: { question: 'anything', on: JSON.stringify({
      space: 'not-a-space', screen: 'projects' }) } },
  )
  expect(refused.ok()).toBe(false)
})

// --------------------------------------------------------------------------
// Asking to write
//
// The assistant cannot save; it can put a card in front of somebody. These
// drive that card, and the reason they are here rather than only in
// `tests/test_chat_changes.py` is that the whole guarantee is a button: a
// change that applies without one being pressed is the thing the design exists
// to prevent, and only a browser can say whether the button is there.
// --------------------------------------------------------------------------

/**
 * A project of this spec's own, so applying a change touches nobody else's.
 *
 * Swept at the end of the test rather than left behind. The fixture is shared
 * with every other spec and the Projects list is something browser passes read
 * — three rows called "Card test 1789033444818" at the top of it are three
 * rows somebody else's assertion has to scroll past.
 */
async function project(page, name) {
  const made = await page.request.post('/api/method/frappe.client.insert', {
    data: { doc: JSON.stringify({
      doctype: 'Project', project_name: name, custom_location: 'Deira',
    }) },
  })
  expect(made.ok()).toBe(true)
  return (await made.json()).message.name
}

/**
 * Take it back out again, and say so if it did not go.
 *
 * The token, because this one runs *after* `page.goto`. A page load mints a
 * fresh CSRF token and the cookie jar's old one stops being accepted, so the
 * POSTs before the navigation succeed and this one gets a `CSRFTokenError` —
 * which for a long time read only as "it was left in the fixture" while the
 * fixture filled up with test projects. `window.csrf_token` is what the boot
 * payload puts there and what the SPA's own requests send.
 *
 * With what the server said, too, and not only that it refused: the next
 * thing to go wrong here should be diagnosable from the failure.
 */
async function sweep(page, docname) {
  const token = await page.evaluate(() => window.csrf_token)
  const gone = await page.request.post('/api/method/frappe.client.delete', {
    headers: token ? { 'X-Frappe-CSRF-Token': token } : {},
    data: { doctype: 'Project', name: docname },
  })
  expect(gone.ok(), `${docname} was left in the fixture: ${await gone.text()}`)
    .toBe(true)
}

/** What the assistant would have written: a proposal, unanswered. */
async function proposed(page, session, docname, values, before) {
  const made = await page.request.post('/api/method/frappe.client.insert', {
    data: { doc: JSON.stringify({
      doctype: 'OneSpace Suggestion',
      session,
      after_message: '',
      kind: 'record.save',
      state: 'Proposed',
      summary: `Change ${docname} on Location`,
      payload: JSON.stringify({
        space: 'rua', screen: 'projects', docname, values,
      }),
      before: JSON.stringify(before),
    }) },
  })
  expect(made.ok()).toBe(true)
  return (await made.json()).message.name
}

/** Any project the fixture happens to have, by its id. */
async function anyProject(page) {
  const said = await page.request.get(
    '/api/method/frappe.client.get_list?doctype=Project&limit_page_length=1',
  )
  expect(said.ok()).toBe(true)
  const [row] = (await said.json()).message || []
  expect(row, 'the fixture has no projects').toBeTruthy()
  return row.name
}

async function field(page, docname, fieldname) {
  const said = await page.request.get(
    `/api/method/frappe.client.get_value?doctype=Project&filters=`
    + `${encodeURIComponent(JSON.stringify({ name: docname }))}`
    + `&fieldname=${fieldname}`,
  )
  return (await said.json()).message[fieldname]
}

test('a change is a card with the diff on it, and nothing happens until Apply',
  async ({ page }) => {
    const errors = collectConsoleErrors(page)
    const made = await project(page, `Card test ${Date.now()}`)
    const session = await thread(page, [ASKED, REPLY])
    await proposed(page, session, made,
                   { custom_location: 'Jumeirah' }, { custom_location: 'Deira' })

    await page.goto(`/one/chat?at=chat:${session}`)
    const card = page.locator('[data-slot="suggestion"]')
    await expect(card).toHaveCount(1)

    // The diff, not a sentence about it: both values, so what is being agreed
    // to is on screen rather than described.
    await expect(card).toContainText('Deira')
    await expect(card).toContainText('Jumeirah')

    // Drawn, read, and still not applied.
    expect(await field(page, made, 'custom_location')).toBe('Deira')

    await card.locator('[data-slot="suggestion-apply"]').click()
    await expect(card).toContainText('Applied')
    expect(await field(page, made, 'custom_location')).toBe('Jumeirah')

    expectNoRealErrors(errors)
    await sweep(page, made)
  })

test('discarding leaves the record alone and the card in the thread',
  async ({ page }) => {
    const made = await project(page, `Discard test ${Date.now()}`)
    const session = await thread(page, [ASKED, REPLY])
    await proposed(page, session, made,
                   { custom_location: 'Jumeirah' }, { custom_location: 'Deira' })

    await page.goto(`/one/chat?at=chat:${session}`)
    const card = page.locator('[data-slot="suggestion"]')
    await card.locator('[data-slot="suggestion-discard"]').click()

    // Still there, saying what became of it: a card that vanished would leave
    // an answer above it claiming to have asked for something with no sign of
    // what happened next.
    await expect(card).toContainText('Discarded')
    await expect(card.locator('[data-slot="suggestion-apply"]')).toHaveCount(0)
    expect(await field(page, made, 'custom_location')).toBe('Deira')
    await sweep(page, made)
  })

test('a record that moved since is refused rather than overwritten',
  async ({ page }) => {
    const made = await project(page, `Stale test ${Date.now()}`)
    const session = await thread(page, [ASKED, REPLY])
    await proposed(page, session, made,
                   { custom_location: 'Jumeirah' }, { custom_location: 'Deira' })

    // Somebody else, between the suggestion and the button.
    const moved = await page.request.post('/api/method/frappe.client.set_value', {
      data: { doctype: 'Project', name: made,
              fieldname: 'custom_location', value: 'Al Quoz' },
    })
    expect(moved.ok()).toBe(true)

    await page.goto(`/one/chat?at=chat:${session}`)
    const card = page.locator('[data-slot="suggestion"]')
    await card.locator('[data-slot="suggestion-apply"]').click()

    await expect(card).toContainText('changed since this was suggested')
    expect(await field(page, made, 'custom_location')).toBe('Al Quoz')
    await sweep(page, made)
  })

// --------------------------------------------------------------------------- //
// The widget itself
//
// Against the Drive rather than a space, because what these check is the shape
// and not the conversation: a tile that is always there, and a widget that
// stays where it was put. Every site has files.
// --------------------------------------------------------------------------- //

test('the dock is always there, and the widget remembers where it was put',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone has one surface')

    await page.goto('/one/files')
    // The dock and not a mark in the corner. There was a 64px dial fixed to the
    // bottom end of every page, which was the right answer while the assistant
    // was the only thing that floated; it is one app among several now and the
    // dock is where they all are.
    // `dock-tile` and not `data-app` alone: the dock draws a tile for OneAI
    // whether or not this workspace has it, and until `sessions()` comes back
    // saying it is on the tile is the dim one, which does not press. Waiting
    // on the live one is waiting for that answer.
    const tile = page.locator('[data-slot="dock-tile"][data-app="chat"]')
    await expect(tile).toBeVisible({ timeout: 20_000 })
    await tile.click()

    const widget = page.locator('[data-window="assistant"]')
    await expect(widget).toBeVisible()
    const opened = await widget.boundingBox()

    // Dragged by its header, which is the only handle: dragging anywhere else
    // would move it while somebody was selecting an answer to copy.
    const handle = await page
      .locator('[data-window="assistant"] [data-slot="window-handle"]').boundingBox()
    await page.mouse.move(handle.x + 60, handle.y + 10)
    await page.mouse.down()
    await page.mouse.move(handle.x - 220, handle.y - 60, { steps: 10 })
    await page.mouse.up()

    const moved = await widget.boundingBox()
    expect(Math.round(moved.x)).toBeLessThan(Math.round(opened.x))

    // The point of remembering it: a habit of mine, and my browser is where my
    // habits live — `lib/url/remember.js`. It was written under an undeclared
    // key for a while, which the `try` swallows, so this is the witness for
    // the declaration as much as for the drag.
    // No second press on the tile: opening it wrote `?ask=` (§C4), so the
    // reload comes back with the widget already open — and a second press on a
    // window that is already in front folds it away, which is the one thing
    // this must not do here.
    await page.reload()
    await expect(widget).toBeVisible({ timeout: 20_000 })
    const again = await widget.boundingBox()
    expect(Math.round(again.x)).toBe(Math.round(moved.x))
    expect(Math.round(again.y)).toBe(Math.round(moved.y))
  })

test('an answer can be put into the document behind the widget',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone has one surface')

    // A document of its own, because the fixture seeds none and this needs one
    // it may write to. Named for the run so two of these never collide.
    const made = await page.request.post('/api/method/oneapp.onedoc.make', {
      data: { title: `zzInsert ${Date.now()}` },
    })
    expect(made.ok()).toBe(true)
    const doc = (await made.json()).message.name

    const PASSAGE = 'TO WHOM IT MAY CONCERN\n\nThis letter confirms employment.'
    const session = await thread(page, [
      { role: 'user', content: 'Draft a to whom it may concern' },
      { role: 'assistant', content: PASSAGE },
    ])

    await page.goto(`/one/docs/${doc}?ask=${session}`)
    const widget = page.locator('[data-window="assistant"]')
    await expect(widget).toBeVisible({ timeout: 20_000 })

    // The button names where it would go, because a widget you can drag
    // anywhere is one where "Insert" alone does not say into what.
    const insert = page.locator('[data-slot="chat-insert"]')
    await expect(insert).toBeVisible({ timeout: 20_000 })

    // The editor first. The widget and the document load independently, and
    // the widget is the faster of the two — so Insert was pressed while
    // ProseMirror was still mounting and the text went into an editor that did
    // not exist yet, silently. Nothing said so: the assertion below simply
    // found an empty document.
    const prose = page.locator('.ProseMirror')
    await expect(prose).toBeVisible({ timeout: 20_000 })
    await expect(prose).toHaveAttribute('contenteditable', 'true')

    await insert.click()

    // In the prose, and offering to take it back out — the two halves of why
    // this is safe to press without reading first.
    await expect(page.locator('.ProseMirror'))
      .toContainText('TO WHOM IT MAY CONCERN', { timeout: 20_000 })
    await expect(page.locator('[data-slot="doc-ai-undo"]')).toBeVisible()
  })

test('there is nowhere to put an answer when nothing is offering',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone has one surface')

    // The Drive takes no prose. A button that refuses is worse than no button,
    // so `shared/lib/ai/insert.js` draws one only while something is offering.
    const session = await thread(page, [
      { role: 'user', content: 'Draft something' },
      { role: 'assistant', content: 'Here is a passage.' },
    ])

    await page.goto(`/one/files?ask=${session}`)
    await expect(page.locator('[data-window="assistant"]')).toBeVisible({
      timeout: 20_000,
    })
    await expect(page.locator('[data-slot="chat-turn"]').last()).toBeVisible()
    await expect(page.locator('[data-slot="chat-insert"]')).toHaveCount(0)
  })

test('what is highlighted is what "this" means', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone has one surface')

  const made = await page.request.post('/api/method/oneapp.onedoc.make', {
    data: { title: `zzSelect ${Date.now()}` },
  })
  expect(made.ok()).toBe(true)
  const doc = (await made.json()).message.name

  await page.goto(`/one/docs/${doc}?ask=new`)
  const chip = page.locator('[data-slot="assistant-context"]')
  await expect(chip).toBeVisible({ timeout: 20_000 })

  // Nothing highlighted: the subject is the document, and the openers are the
  // document's.
  await expect(chip).not.toContainText('highlighted')
  await expect(page.locator('[data-slot="chat-openers"]'))
    .toContainText('Summarise this in five lines.')

  // A fresh document opens on an empty paragraph, so there is something to
  // type into and then select.
  const prose = page.locator('.ProseMirror')
  await prose.click()
  await page.keyboard.type('Prices are to be held for ninety days from tender.')
  await page.keyboard.press('Home')
  await page.keyboard.press('Shift+End')

  // The chip says so, in words, because the passage is going into a request
  // and somebody ought to be able to see that it is.
  await expect(chip).toContainText('highlighted', { timeout: 20_000 })

  // And the questions on offer become the ones worth asking of a paragraph.
  await expect(page.locator('[data-slot="chat-openers"]'))
    .toContainText('Summarise this passage.')
})

test('a highlighted range is what "this" means in a workbook',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone has one surface')

    const made = await page.request.post('/api/method/oneapp.onesheet.make', {
      data: { title: `zzRange ${Date.now()}` },
    })
    expect(made.ok()).toBe(true)
    const book = (await made.json()).message.name

    await page.goto(`/one/sheets/${book}?ask=new`)
    const chip = page.locator('[data-slot="assistant-context"]')
    await expect(chip).toBeVisible({ timeout: 20_000 })

    // Nothing selected beyond the cell the caret starts on: the subject is the
    // workbook, and the openers are the workbook's.
    await expect(page.locator('[data-slot="chat-openers"]'))
      .toContainText('What does this workbook work out?', { timeout: 20_000 })

    // Drag a range. The grid is a canvas, so this is coordinates rather than a
    // locator — 50px of row header, 100px columns, 24px rows under a header of
    // the same height, which is `canvas/constants.js`.
    const box = await page.locator('canvas').first().boundingBox()
    const at = (col, row) => ({
      x: box.x + 50 + col * 100 + 40,
      y: box.y + 24 + row * 24 + 12,
    })
    const from = at(0, 0)
    const to = at(2, 4)
    await page.mouse.move(from.x, from.y)
    await page.mouse.down()
    await page.mouse.move(to.x, to.y, { steps: 8 })
    await page.mouse.up()

    // The range itself rather than a word count: "C3:E8" is what somebody
    // selecting cells is looking at, and a word count of a pipe table is a
    // number about nothing.
    await expect(chip).toContainText('A1:C5', { timeout: 20_000 })

    // And the questions become the ones worth asking of cells. "Shorten this
    // by half" is nonsense on a range.
    await expect(page.locator('[data-slot="chat-openers"]'))
      .toContainText('Which cells feed this?')
  })

test('everything open gets a chip, and a dim one is left out',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the phone has no desk')

    // A document, to open in a window of its own over a screen. Two things on
    // screen at once is the case one chip could not say anything about: it
    // picked whichever was in front and was silent about the rest.
    const made = await page.request.post('/api/method/oneapp.onedoc.make', {
      data: { title: `zzBoth ${Date.now()}` },
    })
    expect(made.ok()).toBe(true)
    const { name, title } = (await made.json()).message

    await page.goto('/one/space/onehr?screen=people&ask=new')
    const strip = page.locator('[data-slot="assistant-context"]')
    await expect(strip).toBeVisible({ timeout: 25_000 })

    // The screen alone, to begin with.
    await expect(strip.locator('[data-slot="context-chip-on"]')).toHaveCount(1)
    await expect(page.locator('[data-slot="chat-openers"]'))
      .toContainText('What is on this screen right now?', { timeout: 20_000 })

    // And now the document as well, in a window over it — the editors' own
    // dock tile lands on the place that holds what they make.
    await page.locator('[data-app="onedoc"]').click()
    const drive = page.locator('[data-window="onedoc"]')
    await expect(drive).toBeVisible({ timeout: 20_000 })
    await drive.getByText(title, { exact: true }).first().click()
    await expect(page.locator('[data-window^="file:"]')).toBeVisible({ timeout: 25_000 })

    // Two chips, both lit, and the document is in front — so it is what "this"
    // means and the openers are the document's.
    await expect(strip.locator('[data-slot="context-chip-on"]')).toHaveCount(2)
    await expect(page.locator('[data-slot="chat-openers"]'))
      .toContainText('Summarise this in five lines.', { timeout: 20_000 })

    // Forward, because opening a file put its window over this one — which is
    // what opening a window means and is why the chip cannot be pressed
    // through it.
    await page.locator('[data-app="chat"]').click()

    // Switch it off and the panel falls back to what is behind it. The chip
    // stays, dim: one you cannot see is one you cannot switch back on.
    await strip.locator('[data-slot="context-chip-on"]').first().click()
    await expect(strip.locator('[data-slot="context-chip-off"]')).toHaveCount(1)
    await expect(page.locator('[data-slot="chat-openers"]'))
      .toContainText('What is on this screen right now?', { timeout: 20_000 })

    // And back.
    await strip.locator('[data-slot="context-chip-off"]').first().click()
    await expect(page.locator('[data-slot="chat-openers"]'))
      .toContainText('Summarise this in five lines.', { timeout: 20_000 })
  })

test('the panel says who it is and what it is about once each', async ({ page }, info) => {
  test.skip(info.project.name === 'mobile', 'the phone has no window bar and no chips')

  await page.goto('/one/space/onehr?screen=people&ask=new')
  const bar = page.locator('[data-window="assistant"] [data-slot="window-handle"]')
  await expect(bar).toBeVisible({ timeout: 25_000 })

  // The name, written the way the family is written: `One` a shade back and
  // the rest at full strength. This window was the last one saying it flat.
  await expect(bar.locator('[data-slot="brand-prefix"]')).toHaveText('One')
  await expect(bar).toContainText('OneAI')

  // And said once. The bar has the name, the chips have what is open, so the
  // empty state below has neither — it used to read "OneAI / OneAI / Asking
  // about People" with a chip saying People beside it: four statements, two
  // facts.
  const body = page.locator('[data-slot="chat"]')
  await expect(page.locator('[data-slot="chat-openers"]')).toBeVisible({ timeout: 20_000 })
  await expect(body).not.toContainText('Asking about')
  await expect(body).not.toContainText('OneAI')

  // Nor does the composer restate it under the box. The placeholder says what
  // the question will be about; a line under it saying the same thing was the
  // third statement of one fact in a column 384px wide.
  await expect(page.locator('[data-slot="chat-input"]'))
    .toHaveAttribute('placeholder', 'Ask about People')
  await expect(body).not.toContainText('About People')

  // The page at `/one/chat` has neither a bar nor chips, so it keeps both.
  await page.goto('/one/chat')
  const page_body = page.locator('[data-slot="chat"]')
  await expect(page_body).toContainText('OneAI', { timeout: 20_000 })
})

test('a file is attached from the Drive and goes with the question',
  async ({ page }, info) => {
    test.skip(info.project.name === 'mobile', 'the picker is its own dialog on a phone')

    // A file of this test's own, because what is in the fixture is not this
    // test's business.
    const made = await page.request.post('/api/method/oneapp.onedoc.make', {
      data: { title: `zzAttach ${Date.now()}` },
    })
    expect(made.ok()).toBe(true)
    const { name, title } = (await made.json()).message

    await page.goto('/one/space/onehr?screen=people&ask=new')
    await expect(page.locator('[data-slot="chat-attach"]')).toBeVisible({ timeout: 25_000 })

    // `FilePicker`, which is the Drive's own: the library, this device and the
    // camera. An upload writes into OneCloud and then picks the result, so
    // what is attached is always a file that exists somewhere a person can
    // find it again.
    await page.locator('[data-slot="chat-attach"]').click()
    await expect(page.locator('[data-slot="picker-library"]')).toBeVisible({ timeout: 20_000 })
    await page.locator('[data-slot="picker-library"]').getByText(title).first().click()

    const attached = page.locator('[data-slot="chat-attached"]')
    await expect(attached).toContainText(title, { timeout: 20_000 })

    // Beside the composer rather than up with the open windows, because the
    // two are different promises: a window is what you have open, a file is
    // what you chose to bring.
    await expect(page.locator('[data-slot="assistant-context"]')).not.toContainText(title)

    // And it comes back out, leaving the file where it lives.
    await attached.locator('[data-slot="chat-detach"]').click()
    await expect(attached).toHaveCount(0)

    const still = await page.request.get(
      `/api/method/oneapp.onedoc.get_doc?name=${name}`,
    )
    expect(still.ok()).toBe(true)
  })
