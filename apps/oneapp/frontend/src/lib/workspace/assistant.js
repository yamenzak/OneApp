/**
 * The workspace assistant, from the browser's side.
 *
 * Four calls and none of them names a model, a prompt or a limit. That is the
 * whole boundary: what the assistant may do is declared on the server in
 * `oneapp_core/chat/assistant.py` as an `@ai_feature`, and the browser picks a
 * thread and types a question. There is nothing here to configure and nowhere
 * to put a key.
 *
 * `askAssistant` is slow on purpose — a question that needs three lookups is
 * four provider calls, and the answer arrives when it is finished rather than a
 * word at a time. It is not silent: this is the one place in the SPA where a
 * failure has to be said out loud, because a chat that quietly answers nothing
 * looks broken rather than refused.
 */

import { callMethod } from '@/lib/runtime/resource'

export const assistant = {
  assistantSessions: () =>
    callMethod('oneapp.oneapp_core.chat.sessions', {}, {
      silent: true, method: 'GET',
    }),

  assistantMessages: (session) =>
    callMethod('oneapp.oneapp_core.chat.messages', { session }, {
      silent: true, method: 'GET',
    }),

  askAssistant: (question, session = '') =>
    callMethod('oneapp.oneapp_core.chat.send', { question, session }),

  forgetChat: (session) =>
    callMethod('oneapp.oneapp_core.chat.forget', { session }, {
      success: 'Conversation deleted',
    }),
}
