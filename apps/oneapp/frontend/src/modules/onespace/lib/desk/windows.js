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
 * The floor the stack sits on.
 *
 * Above the page and its dialogs' backdrop-less furniture, below the dock —
 * which has to stay reachable with a window filling the desk, because pressing
 * its tile is how you get the window out of the way.
 */
export const FLOOR = 40

/** Open windows, back to front. Each is `{ id, folded }`. */
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
export function open(id) {
  const found = at(id)
  const one = found === -1 ? { id, folded: false } : desk.open.splice(found, 1)[0]
  one.folded = false
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
export function press(id) {
  if (shown(id) && inFront(id)) fold(id)
  else open(id)
}

/** Everything, shut. What signing out does — a desk is a session. */
export function clear() {
  desk.open.splice(0, desk.open.length)
}
