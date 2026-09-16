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
 *
 * And it is not asked at all through a share link. A stranger following
 * `/one/link/<secret>` has no account and no workspace, so the endpoint
 * answers 403 — which is correct, and which would still be a failed request
 * in their console on a page that is meant to be a document and nothing else.
 * Closed is already the right answer for them, so the question is not put.
 */
import { reactive } from 'vue'

import { throughLink } from '@/shared/lib/live/link'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const state = reactive({
  /** Whether the site has a gateway at all — for a surface whose own feature
   * is neither of the two below, like mail's filing. */
  live: false,
  rewrite: false,
  summarise: false,
  verbs: [],
  tones: [],
  asked: false,
})

export function writingVerbs() {
  if (!state.asked && !throughLink()) {
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


/**
 * What each verb is called on screen, and what it is drawn with.
 *
 * Here and not on the server: the server's `VERBS` are keys and the
 * instructions behind them, and neither is a label — one is machine-facing
 * and the other is written at a model. These are written at a person, and
 * they are the strings that get translated.
 *
 * Functions rather than maps at module scope, because `__` resolves against a
 * catalogue that is fetched before the first render: a constant built at
 * import time would be built in English on a site that is not.
 */
export const verbWords = () => ({
  write: [__('Write…'), 'lucide-pen-line'],
  improve: [__('Improve'), 'lucide-wand-sparkles'],
  proofread: [__('Proofread'), 'lucide-spell-check'],
  shorten: [__('Make it shorter'), 'lucide-minimize-2'],
  expand: [__('Make it longer'), 'lucide-maximize-2'],
})

/** And the six registers, which are one verb with an argument. */
export const toneWords = () => ({
  formal: __('More formal'),
  friendly: __('Friendlier'),
  direct: __('More direct'),
  warm: __('Warmer'),
  apologetic: __('Apologetic'),
  firm: __('Firmer'),
})

/**
 * The verbs as menu groups, for whichever menu is drawing them.
 *
 * Mail's `AiMenu` was the only caller for a long time and the words lived
 * inside it. They came out when the writer's own AI button left its chrome —
 * the verbs are entries in that editor's own menu now, the one place the
 * workbook has always kept them — and the menu itself went when mail's
 * followed: a composer drawn inside the reading pane, with OneAI a window
 * over it, does not need a second door to the same thing.
 *
 * `narrow` is what this surface has any use for; empty means all of them. It
 * can only narrow — a verb nothing declares is refused at the endpoint, and
 * drawing it would be teaching somebody a thing that does not work.
 */
export function writingOptions(declared, { narrow = [], ask, write } = {}) {
  if (!declared.rewrite) return []

  const wanted = narrow.length ? narrow : declared.verbs
  const offered = declared.verbs.filter((one) => wanted.includes(one))
  const words = verbWords()
  const tones = toneWords()

  // Ordered by `verbWords` rather than by what the server listed. Which verbs
  // exist is the server's; the order they are read in is a question about a
  // menu, and Write comes first because on an empty passage it is the only
  // one that does anything.
  const plain = Object.keys(words)
    .filter((one) => offered.includes(one))
    .map((one) => ({
      label: words[one][0],
      icon: words[one][1],
      onClick: () => (one === 'write' ? write?.() : ask?.({ verb: one })),
    }))

  const groups = plain.length ? [{ group: '', hideLabel: true, options: plain }] : []

  // A group rather than a submenu, because these menus have no submenus and
  // six items under a heading is what a submenu would have shown anyway.
  if (offered.includes('tone')) {
    groups.push({
      group: __('Tone'),
      options: declared.tones
        .filter((one) => tones[one])
        .map((one) => ({ label: tones[one], onClick: () => ask?.({ verb: 'tone', tone: one }) })),
    })
  }
  return groups
}
