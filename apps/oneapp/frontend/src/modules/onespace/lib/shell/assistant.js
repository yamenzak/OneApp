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
import { __ } from '@/shared/lib/runtime/translate'

/** Which window on the desk this is. One id, said once. */
export const ASSISTANT = 'assistant'

export const assistant = reactive({
  // What it is looking at. Here rather than on the panel itself because the
  // thing that opens it is somewhere else every time — the dock, a record's
  // controls, a keyboard shortcut — and none of them is its parent.
  //
  // Whether it is *showing* is no longer here: the assistant is one window
  // among several now, and the desk keeps the list. Two places saying whether
  // it is open is how one of them comes to be wrong — the dock would light a
  // tile for a panel nobody had opened.
  on: null,
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
export const assistantName = computed(() => assistant.name || __('Assistant'))

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
 * Open the panel, against what the caller is looking at.
 *
 * `on` is `{space, screen, docname, label}` or nothing. Only the label is for
 * the browser; the rest goes to the server, which resolves every part of it
 * through the same checks a click goes through — so a context this reader
 * cannot reach narrows to nothing rather than widening anything.
 *
 * Changing what it is looking at starts a new thread. A conversation that was
 * about a quotation and is now about a project is two conversations, and
 * carrying the first one forward would leave the model answering "this one"
 * from a note that no longer applies.
 */
export function openAssistant(on = null) {
  if (JSON.stringify(on || null) !== JSON.stringify(assistant.on || null)) {
    assistant.on = on || null
    assistant.session = ''
  }
  open(ASSISTANT)
  loadAssistant()
}

export function closeAssistant() {
  close(ASSISTANT)
}

/**
 * What the dock's tile does, which is not quite opening.
 *
 * A tile is a toggle: shut it opens, in front it folds away, behind it comes
 * forward. Only the first of those is `openAssistant`, and only the first of
 * them should carry a subject — folding a window is not a statement about what
 * you want to ask, so passing the context through here would start a new
 * thread every time somebody put the panel away and got it back.
 */
export function pressAssistant(on = null) {
  if (onDesk(ASSISTANT)) press(ASSISTANT)
  else openAssistant(on)
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
