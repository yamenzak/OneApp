/**
 * What the writing menu may offer, asked once for the whole session.
 *
 * Three surfaces draw this menu and a page can hold several of them — a
 * composer with a rail beside it, a document with a selection. Each one
 * asking whether AI is switched on would be a request per menu to answer a
 * question whose answer does not move: a workspace enabling a feature is a
 * page reload away, the same reasoning `lib/shell/assistant.js` uses for the
 * assistant's own availability.
 *
 * Shipped closed. The refs start at "no verbs, nothing available", so a menu
 * mounted before the answer lands draws nothing and then appears — rather
 * than appearing and then vanishing, which is the worse way round.
 */
import { reactive } from 'vue'

import { workspace } from '@/shared/lib/workspace'

const state = reactive({
  rewrite: false,
  summarise: false,
  verbs: [],
  tones: [],
  asked: false,
})

export function writingVerbs() {
  if (!state.asked) {
    state.asked = true
    workspace
      .aiVerbs()
      .then((said) => Object.assign(state, said || {}))
      // Left closed. A site whose gateway is unreachable draws no menu, which
      // is the same thing it would draw if the answer had said so.
      .catch(() => {})
  }
  return state
}
