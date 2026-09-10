/**
 * The workspace assistant, from the browser's side.
 *
 * None of these calls names a model, a prompt or a limit. That is the whole
 * boundary: what the assistant may do is declared on the server in
 * `onespace/chat/assistant.py` as an `@ai_feature`, and the browser picks a
 * thread and types a question. There is nothing here to configure and nowhere
 * to put a key.
 *
 * `applyChange` is the only one that writes anything, and it is deliberately
 * a call a person makes rather than one an answer makes: the assistant asks
 * for a change and the card sits there until somebody presses the button.
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

  // The write. Not silent and not optimistic: a change can be refused by the
  // record's own validation or by having moved since it was suggested, and
  // both of those are things the person who pressed the button has to see.
  applyChange: (name) =>
    callMethod('oneapp.onespace.chat.apply_change', { name }),

  discardChange: (name) =>
    callMethod('oneapp.onespace.chat.discard_change', { name }, { silent: true }),

  forgetChat: (session) =>
    callMethod('oneapp.onespace.chat.forget', { session }, {
      success: 'Conversation deleted',
    }),
}
