/**
 * Whether the workspace has an assistant, and which conversations it holds.
 *
 * Two readers and neither owns the other: the rail decides whether to draw the
 * entry at all, and the page draws the list of threads. A module-level
 * reactive for the same reason `mail.js` is one — the rail outlives the page,
 * so there is no parent to pass it down from.
 *
 * Fetched once rather than polled. Whether AI is switched on for a workspace
 * changes when somebody changes it, which is a page reload away; a minute
 * timer would be a request a minute to answer a question whose answer does not
 * move.
 */
import { computed, reactive } from 'vue'
import { close, onDesk, open, press } from '@/modules/onespace/lib/desk/windows'
import { assistant as booted } from '@/shared/lib/runtime/boot'
import { workspace } from '@/shared/lib/workspace'
import { nameOf } from '@/shared/lib/brand/naming'
import { detachAll } from '@/shared/lib/ai/context'

/** Which window on the desk this is. One id, said once. */
export const ASSISTANT = 'assistant'

export const assistant = reactive({
  // Which conversation is open. What it is *looking at* is no longer here:
  // that is every window on the desk with something to say about itself, and
  // the desk already keeps the list — `shared/lib/ai/context.js` reads it and
  // the panel draws a chip per entry.
  //
  // Whether it is *showing* is not here either, for the same reason: the
  // assistant is one window among several now. Two places saying whether it is
  // open is how one of them comes to be wrong — the dock would light a tile
  // for a panel nobody had opened.
  session: '',
  // False until we know. The rail draws nothing while it is false, which is
  // the right way round: an entry that appears and then disappears is worse
  // than one that appears a beat late.
  available: false,
  sessions: [],
  loaded: false,
  // Who it is, from the boot payload. Here rather than fetched with the thread
  // list, because the rail names it before that call returns and a label that
  // says "Assistant" for a beat and then says something else is the same
  // visible flicker the favicon had. `www/one.py` puts it there.
  name: booted?.name || '',
  avatar: booted?.avatar || '',
})

/**
 * Whether its window is on the desk. Read by the dock, which lights the tile,
 * and by the widget, which draws the panel.
 *
 * On the desk rather than *drawn*: a folded assistant is still open, and its
 * tile says so. `DeskWindow` is what decides whether a folded window is
 * painted.
 */
export const assistantShowing = computed(() => onDesk(ASSISTANT))

/** What to call it. Never empty — a nameless assistant is still on screen, and
 *  this is the same fallback the server uses when nothing has been set. */
/**
 * What this workspace calls its assistant, or what the product does.
 *
 * `nameOf('oneai')` and not a literal: `MARKS[id].name` is the only place a
 * product name is written down — `CLAUDE.md`, and the reason is that four of
 * the ids disagree with their names on purpose. The default was the word
 * "Assistant", which is a category rather than a name and left the one app in
 * the pack that has no name on screen.
 *
 * A workspace that has set one still wins. That is the whole point of the
 * setting, and it is why this is a fallback rather than a rename.
 */
export const assistantName = computed(() => assistant.name || nameOf('oneai'))

/**
 * Whether the name on screen is the workspace's choice rather than ours.
 *
 * `SpaceName` writes `One` a shade back where the name is ours to style, and
 * says a name somebody chose whole. It cannot be `!!assistant.name`: the boot
 * payload carries `identity()`, which has *already* fallen back to our
 * default, so the panel would treat every workspace as having renamed it and
 * the one window in the product that is an app would be the one writing its
 * name flat.
 *
 * So the comparison is against the mark. A workspace that typed "OneAI" on
 * purpose gets the quiet prefix, which is what they typed and what they meant.
 */
export const assistantRenamed = computed(() => assistantName.value !== nameOf('oneai'))

/** Its picture, or nothing: `Avatar` draws a letter from the label instead. */
export const assistantAvatar = computed(() => assistant.avatar)

/**
 * What the AI settings tab calls once a save has come back.
 *
 * Without it the rail and the panel keep the old name until a reload, which is
 * the kind of wrong nobody reports and everybody notices.
 */
export function setAssistant(who) {
  assistant.name = who?.name || ''
  assistant.avatar = who?.avatar || ''
}

/**
 * Open the panel.
 *
 * It used to take what the caller was looking at and start a new thread
 * whenever that changed — a conversation about a quotation that is now about a
 * project being two conversations. That rule was right while the context was
 * invisible and one thing: the alternative was a model answering "this one"
 * from a note nobody could see had gone stale.
 *
 * The panel draws a chip per open thing now and the person switches them on
 * and off, so there is nothing to freeze and nothing to guess: what the next
 * question carries is on screen above the box it is typed in.
 * `shared/lib/ai/context.js` holds it, and New chat is still one press.
 */
export function openAssistant() {
  open(ASSISTANT)
  loadAssistant()
}

/**
 * A fresh conversation.
 *
 * The session and what was attached to it, because an attachment belongs to
 * the thread it was attached for: carrying a colleague's contract into the
 * next question is the model reading a file nobody meant to give it. What is
 * *open* is not touched — that is a fact about the desk, not about the thread.
 */
export function newChat() {
  assistant.session = ''
  detachAll()
}

export function closeAssistant() {
  close(ASSISTANT)
}

/**
 * What the dock's tile does, which is not quite opening.
 *
 * A tile is a toggle: shut it opens, in front it folds away, behind it comes
 * forward.
 */
export function pressAssistant() {
  if (onDesk(ASSISTANT)) press(ASSISTANT)
  else openAssistant()
}

/** Ask the server once whether the assistant is on, and for the thread list. */
export async function loadAssistant({ reload = false } = {}) {
  if (assistant.loaded && !reload) return assistant
  try {
    const got = await workspace.assistantSessions()
    assistant.available = !!got?.available
    assistant.sessions = got?.sessions || []
  } catch {
    // A workspace with no AI configured refuses rather than answering an empty
    // list, and the rail's answer to a refusal is the same as its answer to
    // "switched off": offer nothing.
    assistant.available = false
    assistant.sessions = []
  }
  assistant.loaded = true
  return assistant
}
