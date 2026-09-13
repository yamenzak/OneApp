/**
 * What the reader has open, for the assistant to be about.
 *
 * The panel was context-aware for records and blind everywhere else, and the
 * reason was structural: `shell/nav.js` derived context from the route, and a
 * route is the only thing it had. `/space/rua?screen=quotations&at=…` carries a
 * space, a screen and a record; `/one/docs/<id>` carries an id and nothing that
 * says what it is called. So a panel opened beside a scope of works said "Ask
 * about this workspace", and "summarise this" meant the whole of it.
 *
 * **A page declares its own context.** It is the only thing that knows: it has
 * the title, it knows whether the thing has finished loading, and it knows when
 * what is open has changed underneath the same URL. A route never knew the
 * first of those and cannot know the third.
 *
 * Declared for as long as the component is mounted and withdrawn when it goes,
 * which is what makes leaving a document put the assistant back on the
 * workspace without the document having to remember to say so.
 *
 * One at a time, deliberately. Two mounted surfaces both claiming to be what
 * you are looking at is a question with no answer — and the case that would
 * cause it, a file open in the Drive's pane, is one where the file is the
 * better answer and the Drive should say so itself.
 *
 * Everything here is a *claim*. `onespace/chat/context.py` resolves every field
 * again through the same checks a click goes through, so a page cannot widen
 * what its reader may see by describing something they cannot open.
 */

import { onScopeDispose, getCurrentScope, shallowRef } from 'vue'

/** The claim in force, or null. A ref so the panel redraws when it changes. */
const declared = shallowRef(null)

/**
 * Say what this component has open, for as long as it is mounted.
 *
 * `describe` is called rather than stored, so a page whose title arrives after
 * its id does not have to re-register when it lands — see `Doc.vue`, where the
 * name comes back with the document.
 *
 * Returns nothing to call: the claim is withdrawn on scope disposal, because a
 * page that forgot to withdraw it is a panel that stays wrong.
 */
export function useAiContext(describe) {
  const mine = { describe }
  declared.value = mine
  if (getCurrentScope()) {
    onScopeDispose(() => {
      // Only if it is still ours. A page that unmounts *after* the next one
      // mounted would otherwise clear a claim it does not own — which is the
      // ordinary order of things in Vue's router.
      if (declared.value === mine) declared.value = null
    })
  }
}

/**
 * What is open now: what a page said, or what the route can be read to mean.
 *
 * The route fallback is the screen case and is unchanged — every record screen
 * in the product gets its context without a line of its own, which is worth
 * keeping. A page that declares one wins, because it knows more.
 */
export function openContext(route, fromRoute) {
  const said = declared.value?.describe?.()
  if (said && (said.file || said.space)) return said
  return fromRoute ? fromRoute(route) : null
}

/**
 * The claim as it stands *now*, for a reader that wants it to stay current.
 *
 * `openAssistant` stores what it was handed, and rightly: the stored subject is
 * what decides thread identity, and a thread whose subject changed under it is
 * two threads. But a *label* is not identity — a document's title arrives a
 * beat after its id, and the panel that read the claim at open time said "This
 * document" for ever afterwards.
 *
 * So the identity is stored and the words are read live. Called inside a
 * `computed`, this tracks whatever the page's own `describe` reads, which is
 * how the title appears the moment it lands.
 */
export function declaredNow() {
  return declared.value?.describe?.() || null
}

/** For a page that wants to say "nothing", rather than say nothing. */
export function clearAiContext() {
  declared.value = null
}
