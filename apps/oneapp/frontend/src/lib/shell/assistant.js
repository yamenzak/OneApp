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
import { reactive } from 'vue'
import { workspace } from '@/lib/workspace'

export const assistant = reactive({
  // False until we know. The rail draws nothing while it is false, which is
  // the right way round: an entry that appears and then disappears is worse
  // than one that appears a beat late.
  available: false,
  sessions: [],
  loaded: false,
})

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
