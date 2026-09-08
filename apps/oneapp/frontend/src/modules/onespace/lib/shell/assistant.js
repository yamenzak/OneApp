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
import { assistant as booted } from '@/shared/lib/runtime/boot'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

export const assistant = reactive({
  // The panel, and what it is looking at. Here rather than on the panel itself
  // because the thing that opens it is somewhere else every time — the rail, a
  // record's controls, a keyboard shortcut — and none of them is its parent.
  showing: false,
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
  assistant.showing = true
  loadAssistant()
}

export function closeAssistant() {
  assistant.showing = false
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
