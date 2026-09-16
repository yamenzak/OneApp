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
 * **Several at a time, since the desk.** It was one claim and the last writer
 * won, on the grounds that two mounted surfaces both claiming to be what you
 * are looking at is a question with no answer. Windows made it a question with
 * an obvious answer and the old rule the wrong one: with a workbook and a
 * letter open, the assistant was about whichever had mounted last — which is
 * the order they were opened in, not the order they are stacked in, and not
 * the one you are looking at.
 *
 * So a claim is *owned*. A claim made inside a window belongs to that window,
 * everything else belongs to the page, and the desk gives the order:
 * `frontToBack` is its own ordering — the same one the dock reads — so raising
 * a window changes what is first and folding one away takes it off the list,
 * which is what a person pressing a tile means by it.
 *
 * **And all of them count, not the front one.** Picking the front-most was
 * the first answer and it was a guess that was right about half the time: a
 * question asked with a workbook, a letter and the record they are both about
 * on screen is usually a question about more than one of them. So every claim
 * goes, front-first, and the panel draws a chip per claim that the person can
 * switch off. `excluded` is what they switched off, by owner — off rather
 * than on, so something newly opened is included without anybody having to
 * say so, which is the whole point of not having to choose.
 *
 * Everything here is a *claim*. `onespace/chat/context.py` resolves every field
 * again through the same checks a click goes through, so a page cannot widen
 * what its reader may see by describing something they cannot open.
 */

import { inject, onScopeDispose, getCurrentScope, reactive, shallowRef, unref } from 'vue'

import { WINDOW_ID, frontToBack } from '@/modules/onespace/lib/desk/windows'

/** What a claim belongs to when it is not inside a window. */
const PAGE = 'page'

/**
 * Every claim in force, by owner — a window id, or `page`.
 *
 * A `shallowRef` holding a fresh Map rather than a reactive one, because what
 * has to be reactive is *which claims exist*: the panel redraws when a surface
 * registers or goes, and reads the describes through a computed the rest of
 * the time.
 */
const declared = shallowRef(new Map())

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
  // Which window this is inside, if any. Injected at setup and unwrapped —
  // an `inject` inside a getter registers nothing and answers undefined the
  // second time, which this codebase has paid for twice.
  const inside = inject(WINDOW_ID, null)
  const owner = unref(inside) || PAGE

  const mine = { describe }
  const next = new Map(declared.value)
  next.set(owner, mine)
  declared.value = next

  if (getCurrentScope()) {
    onScopeDispose(() => {
      // Only if it is still ours. A page that unmounts *after* the next one
      // mounted would otherwise clear a claim it does not own — which is the
      // ordinary order of things in Vue's router.
      if (declared.value.get(owner) !== mine) return
      const without = new Map(declared.value)
      without.delete(owner)
      declared.value = without
    })
  }
}

/**
 * Owners the reader has switched off. Everything else is on.
 *
 * A `Set` in a `reactive`, and not persisted: what is open is a fact about
 * this session, and a chip switched off for a window that has since closed is
 * a preference about nothing. Owners are reused — `file:<name>` is stable —
 * so an owner that goes and comes back comes back switched on, which is the
 * forgiving direction.
 */
const excluded = reactive(new Set())

/** Whether this one goes to the model. */
export function isIncluded(owner) {
  return !excluded.has(owner)
}

/** Switch one on or off. What pressing its chip does. */
export function toggleContext(owner) {
  if (excluded.has(owner)) excluded.delete(owner)
  else excluded.add(owner)
}

/** Everything off, which is "ask about the whole workspace instead". */
export function clearIncluded(owners) {
  for (const one of owners) excluded.add(one)
}

/**
 * Everything open that can be talked about, front-first.
 *
 * Each entry is what its surface's `describe` said, plus the `owner` it was
 * claimed under and whether it is switched on. The page comes last: it is
 * behind every window by definition, and a window is what somebody opened on
 * purpose.
 *
 * The route fallback is the screen case and is unchanged — every record screen
 * in the product gets its context without a line of its own, which is worth
 * keeping. A page that declares one wins, because it knows more.
 */
export function openContexts(route, fromRoute) {
  const claims = declared.value
  const found = []

  for (const id of frontToBack()) {
    const said = claims.get(id)?.describe?.()
    if (said) found.push({ owner: id, on: !excluded.has(id), ...said })
  }

  const page = claims.get(PAGE)?.describe?.() || (fromRoute ? fromRoute(route) : null)
  if (page) found.push({ owner: PAGE, on: !excluded.has(PAGE), ...page })

  // The same document open in a window and as the page is one document. The
  // window's entry wins because it came first, which is also the one that is
  // in front.
  const seen = new Set()
  return found.filter((one) => {
    const key = one.file || `${one.space || ''}/${one.screen || ''}/${one.docname || ''}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

/** What actually goes with the question. */
export function includedContexts(route, fromRoute) {
  return openContexts(route, fromRoute).filter((one) => one.on)
}

/**
 * What is open now: what a page said, or what the route can be read to mean.
 *
 * The one in front, for the callers that want a subject rather than a list —
 * the opening questions the panel offers, and the line it puts under its own
 * name.
 */
export function openContext(route, fromRoute) {
  const said = declaredNow()
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
  const claims = declared.value
  if (!claims.size) return null

  // The front-most window that has something to say. `frontToBack` leaves out
  // the folded ones, so a window put away stops being what the assistant is
  // about — which is what putting it away means.
  for (const id of frontToBack()) {
    const said = claims.get(id)?.describe?.()
    if (said) return said
  }
  return claims.get(PAGE)?.describe?.() || null
}

/** For a page that wants to say "nothing", rather than say nothing. */
export function clearAiContext() {
  declared.value = new Map()
}
