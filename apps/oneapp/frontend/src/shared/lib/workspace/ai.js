/**
 * A run, from the browser's side: catching up with one and stopping one.
 *
 * There is no `start` here, and that is the boundary rather than an omission.
 * A run is begun by whichever module owns the feature — mail asks
 * `onemail...` for a summary, the writer asks `onedoc...` to write a
 * paragraph — through an endpoint that takes the thing being worked on and
 * nothing else. A general "run feature X with arguments Y" call would be an
 * endpoint that takes a prompt, which is the one shape this whole layer
 * exists not to have.
 *
 * These two are about the run itself and belong to nobody's module, so they
 * are here.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

export const ai = {
  // Silent: this is the catch-up fetch behind a stream, and a run that has
  // expired is a thing the panel says in its own words rather than a toast.
  aiResult: (run) =>
    callMethod('oneapp.onespace.ai.streaming.result', { run }, {
      silent: true, method: 'GET',
    }),

  aiStop: (run) =>
    callMethod('oneapp.onespace.ai.streaming.stop', { run }, { silent: true }),

  // What the writing menu may offer. Silent, and read once a session by
  // `shared/lib/ai/verbs.js` — a site with no gateway draws no menu, which is
  // not an error anybody needs told about.
  aiVerbs: () =>
    callMethod('oneapp.onespace.ai.text.available', {}, {
      silent: true, method: 'GET',
    }),

  // --- what a model asked for, and the two answers to it -------------------
  //
  // Apply is the write, and it is a request a person made: not silent and not
  // optimistic, because it can be refused by the record's own validation or
  // by having moved since it was suggested, and both are things the person
  // who pressed the button has to see.

  applySuggestion: (name) =>
    callMethod('oneapp.onespace.ai.actions.apply_suggestion', { name }),

  discardSuggestion: (name) =>
    callMethod('oneapp.onespace.ai.actions.discard_suggestion', { name }, {
      silent: true,
    }),
}
