/**
 * The workspace assistant, from the browser's side.
 *
 * Four calls and none of them names a model, a prompt or a limit. That is the
 * whole boundary: what the assistant may do is declared on the server in
 * `onespace/chat/assistant.py` as an `@ai_feature`, and the browser picks a
 * thread and types a question. There is nothing here to configure and nowhere
 * to put a key.
 *
 * `askAssistant` is slow on purpose — a question that needs three lookups is
 * four provider calls, and the answer arrives when it is finished rather than a
 * word at a time. It is not silent: this is the one place in the SPA where a
 * failure has to be said out loud, because a chat that quietly answers nothing
 * looks broken rather than refused.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

export const assistant = {
  assistantSessions: () =>
    callMethod('oneapp.onespace.chat.sessions', {}, {
      silent: true, method: 'GET',
    }),

  assistantMessages: (session) =>
    callMethod('oneapp.onespace.chat.messages', { session }, {
      silent: true, method: 'GET',
    }),

  // `on` is what the reader has open — `{space, screen, docname}`. Sent as an
  // answer to be verified rather than a premise: `chat/context.py` resolves
  // every part of it through the same checks a click goes through, so a stale
  // one narrows to nothing rather than widening anything.
  askAssistant: (question, session = '', on = null) =>
    callMethod('oneapp.onespace.chat.send', { question, session, on }),

  forgetChat: (session) =>
    callMethod('oneapp.onespace.chat.forget', { session }, {
      success: 'Conversation deleted',
    }),
}
