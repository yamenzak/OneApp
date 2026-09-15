/**
 * What is open on the desk, and which of it is in front.
 *
 * `geometry.js` answers where one window is; this answers how many there are.
 * They are separate because they are read by different things: a window knows
 * its own box and nothing about its neighbours, and the dock knows the list and
 * nothing about anybody's corner.
 *
 * A module-level reactive for the same reason `assistant.js` and `mail.js` are
 * ones — the thing that opens a window is somewhere else every time (the dock,
 * a breadcrumb, a Link field, a keyboard shortcut) and none of them is its
 * parent. There is one desk per person, not one per component tree.
 *
 * **The order is the stack.** Last in the list is in front, which makes raising
 * a window a move to the end rather than a number to keep unique, and makes
 * "which is frontmost" a question with an answer instead of a tie. The z-index
 * a window gets is its place in that order, so nothing has to be renumbered
 * when one closes.
 *
 * Nothing here is in the URL. `docs/DESKTOP.md`: position and size are
 * remembered per app, *which* windows are open is not — a pasted link opens the
 * page, not somebody else's desk.
 *
 * `docs/DESKTOP.md` stage 2.
 */
import { reactive } from 'vue'

/**
 * The floor the stack sits on — *inside the desk's own layer*, which is the
 * part that matters. See `layer()`.
 */
export const FLOOR = 40

/**
 * Where every window is drawn: one element, appended to `body`.
 *
 * Not where it looks — where it *layers*. frappe-ui's Dialog portals itself to
 * `body` at `z-50`, and a window drawn inside the page loses to it however high
 * its own z-index goes, because the page is a stacking context of its own. That
 * is not hypothetical: a Link peeked from inside a create dialog opened behind
 * the dialog that asked for it, which is the same bug the drawer this replaces
 * was written to fix, and it fixed it the same way.
 *
 * So: one container at the dialogs' own depth, and inside it the per-window
 * z-index gives the stack. Two questions, two mechanisms, neither fighting the
 * other — the desk against everything else is settled by DOM order, and the
 * windows against each other by `zOf`.
 *
 * **Re-appended whenever a window opens**, which is the whole of how DOM order
 * comes out right. A dialog opened while the desk sits there covers it, because
 * it appends after — a modal covering what was already on screen is correct. A
 * window opened *from* that dialog moves the desk back to the end, so it covers
 * the dialog — which is correct too, because you asked for it from inside. The
 * drawer got this by being mounted on demand; the desk is permanent, so it has
 * to say it out loud.
 */
export const LAYER = 'oneapp-desk'

function layer() {
  if (typeof document === 'undefined') return null
  let found = document.getElementById(LAYER)
  if (!found) {
    found = document.createElement('div')
    found.id = LAYER
    // `z-50`, the same depth frappe-ui gives a dialog, so the tie is broken by
    // DOM order rather than by a number one of us picked. No size and no
    // pointer events of its own: every window inside is `fixed` and brings its
    // own.
    found.className = 'relative z-50'
    found.style.pointerEvents = 'none'
  }
  // To the end, every time. Moving an element does not unmount what Vue has
  // teleported into it — Vue holds the target element itself, not its place in
  // the document.
  document.body.appendChild(found)
  return found
}

/** Set up before anything is drawn into it, so the first window has somewhere
 *  to go. Idempotent, like the rest of this. */
export function mountLayer() {
  layer()
}

/**
 * Open windows, back to front. Each is `{ id, folded, label, icon }`.
 *
 * The last two are the dock's, and they are here rather than in the dock
 * because only the opener knows them: a window an app's tile already stands
 * for needs neither, and one that nothing stands for — a picture-in-picture
 * list — has to be drawn from something. Without them the dock drew a generic
 * glyph with no name on it, which is a tile you have to press to find out what
 * it is.
 */
export const desk = reactive({ open: [] })

const at = (id) => desk.open.findIndex((one) => one.id === id)

/** Whether this window is on the desk at all, folded or not. */
export function onDesk(id) {
  return at(id) !== -1
}

/** Whether it is on the desk *and* drawn. A folded window is still open. */
export function shown(id) {
  const found = desk.open[at(id)]
  return !!found && !found.folded
}

/** Whether it is the one in front, which is what a second press acts on. */
export function inFront(id) {
  return desk.open.length > 0 && desk.open[desk.open.length - 1].id === id
}

/** Its z-index, or the floor for a window nobody has opened yet. */
export function zOf(id) {
  const found = at(id)
  return found === -1 ? FLOOR : FLOOR + found
}

/**
 * Open it, unfold it, and put it in front. Idempotent, which matters: the
 * assistant's shortcut, its dock tile and a record's own control all call this,
 * and a second caller must not open a second assistant.
 */
export function open(id, { label = '', icon = '' } = {}) {
  // Over whatever is already on screen — see `layer()`. Before the state
  // changes, so the element is in place by the time anything renders into it.
  layer()
  const found = at(id)
  const one = found === -1 ? { id, folded: false, label: '', icon: '' } : desk.open.splice(found, 1)[0]
  one.folded = false
  // Kept where the caller says nothing, so raising a window does not blank the
  // name it was opened with.
  if (label) one.label = label
  if (icon) one.icon = icon
  desk.open.push(one)
}

export function close(id) {
  const found = at(id)
  if (found !== -1) desk.open.splice(found, 1)
}

/** In front, without changing whether it is folded. A no-op for a folded one:
 *  raising something nobody can see is how a window comes to be "open" and
 *  invisible with no way back to it. */
export function raise(id) {
  const found = at(id)
  if (found === -1 || desk.open[found].folded) return
  desk.open.push(desk.open.splice(found, 1)[0])
}

/**
 * Out of the way, and still open.
 *
 * Folded rather than minimised, because there is nowhere for it to go: this
 * product has no window bar of its own — the dock's tile is the window's tile,
 * so a folded window is one whose tile is still lit and whose panel is not
 * drawn. Its conversation, its scroll and its corner are all still there.
 */
export function fold(id) {
  const found = at(id)
  if (found !== -1) desk.open[found].folded = true
}

/**
 * What one press of a dock tile means, which is all three of the above.
 *
 * Shut → open it. Open and behind something → bring it forward. Open and
 * already in front → fold it, because the only thing left to ask of a window
 * you are looking at is to stop looking at it. Folded → unfold.
 *
 * This is what every desktop does and none of them explains, and it is worth
 * one sentence: the press means "I want this", and the only reading of "I want
 * this" when it is already the thing in front of you is that you do not.
 */
export function press(id, how) {
  if (shown(id) && inFront(id)) fold(id)
  else open(id, how)
}

/** Everything, shut. What signing out does — a desk is a session. */
export function clear() {
  desk.open.splice(0, desk.open.length)
}
