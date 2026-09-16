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
 * Open windows, back to front. Each is
 * `{ id, folded, label, icon, image, face, family, brand, seq }`.
 *
 * The last three are the dock's, and they are here rather than in the dock
 * because only the opener knows them: a window an app's tile already stands
 * for needs none of them, and one that nothing stands for — a picture-in-
 * picture list, a record preview — has to be drawn from something. Without
 * them the dock drew a generic glyph with no name on it, which is a tile you
 * have to press to find out what it is.
 *
 * `family` is the set of windows that share a corner, and therefore cover one
 * another completely — the record previews are the only one so far. It is what
 * lets `visible` answer "is this the window I am looking at" rather than only
 * "is it folded": the same question for a window with a corner to itself, and
 * not for one of several stacked exactly on top of each other.
 *
 * `face` and `image` are what makes a row of previews readable. Five of them
 * are five *records*, and one glyph drawn five times is a row you have to
 * press to read. A window that says `face` is drawn as a record is drawn
 * everywhere else in the product — its picture where it has one, its initials
 * where it does not, which is what `RecordChip` and every list cell do. A
 * window that does not, like the picture-in-picture list, keeps its glyph:
 * initials for "People" would be a face for something that is not a person.
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
 *
 * `front: false` registers one without touching the stack — on the desk if it
 * was not, its name and face brought up to date, and otherwise exactly where
 * and how it was. What needs it is a family of windows opened together: three
 * record previews in a pasted URL are three fetches, and whichever *returned*
 * last was ending up in front, so the same address drew a different window
 * each time you opened it. Which one is in front is a question the URL
 * answers, not the network.
 *
 * It is also what a refresh has to use. `open` unfolds, so updating a tile's
 * label would bring back a window somebody had put away.
 */
/**
 * How many windows have ever been opened, which is how the dock orders them.
 *
 * `desk.open` is the *stack* — its order is which covers which, and raising a
 * window moves it — so a dock drawn from it rearranged itself every time
 * somebody pressed a tile. A taskbar whose buttons move under the pointer is
 * the wrong taskbar: what it is for is being in the same place twice. So a
 * window remembers when it arrived and the dock reads that instead.
 */
let arrivals = 0

/**
 * Where a window's tenant may put its own controls: the injection key carrying
 * the id of a target inside the window's title bar.
 *
 * A window and the thing inside it both want a bar, and two bars is what a
 * person sees — an editor in a window drew the window's title and then, right
 * under it, its own row with a mark on the left and its verbs on the right.
 * Nearly empty, and the width of the window.
 *
 * So the tenant teleports its verbs up. `DeskWindow` provides this; anything
 * inside one injects it and, where it finds one, draws into it instead of
 * drawing a bar. Injected rather than passed, because the thing with the verbs
 * is usually three components below the one that knows it is in a window.
 */
export const WINDOW_BAR = Symbol('window-bar')

export function open(id, how = {}, { front = true } = {}) {
  // Over whatever is already on screen — see `layer()`. Before the state
  // changes, so the element is in place by the time anything renders into it.
  layer()
  const { label = '', icon = '', image = '', face = false, family = '', brand = '' } = how
  let found = at(id)
  if (found === -1) {
    arrivals += 1
    desk.open.push({
      id, folded: false, label: '', icon: '', image: '', face: false, family: '',
      brand: '', seq: arrivals,
    })
    found = desk.open.length - 1
  }
  const one = desk.open[found]
  // Kept where the caller says nothing, so raising a window does not blank the
  // name it was opened with.
  if (label) one.label = label
  if (icon) one.icon = icon
  if (image) one.image = image
  if (face) one.face = true
  if (family) one.family = family
  // An app's mark, for a window the dock has no tile of its own for — the
  // three editors, which are OneCloud over a different `where`. A glyph there
  // would be the same drawing for all three.
  if (brand) one.brand = brand
  if (!front) return
  one.folded = false
  desk.open.push(desk.open.splice(found, 1)[0])
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

/**
 * The frontmost unfolded window of this family, or `''`.
 *
 * What lets a family of windows share one box. Several record previews are
 * open at once and all of them remember the same corner, so every one but the
 * front is covered completely — there is nothing to see behind a window
 * exactly on top of it, and a mounted record nobody can see is a form, a
 * presence subscription and a set of tabs held for no reason.
 *
 * So the front one is drawn and the rest are shells with a tile. That is the
 * whole of the "hibernation" the tabbing window was going to need: a preview
 * is read-only, so there is no state to suspend — only a fetched record, which
 * its caller keeps, so raising one is instant rather than a reload.
 */
export function frontOf(family) {
  for (let index = desk.open.length - 1; index >= 0; index -= 1) {
    const one = desk.open[index]
    if (!one.folded && one.family === family) return one.id
  }
  return ''
}

/**
 * Whether this is a window somebody is actually looking at.
 *
 * `shown` says it is not folded, which was the whole question while every
 * window had a corner to itself. It is not the question for a family: two
 * previews are both unfolded and one is behind the other to the pixel, so a
 * dock that lit both was saying two windows were on screen when one of them
 * had nothing to see.
 */
export function visible(id) {
  const found = desk.open[at(id)]
  if (!found || found.folded) return false
  return !found.family || frontOf(found.family) === id
}

/** Everything of this family, shut. One record preview closing is `close`. */
export function closeAll(family) {
  for (let index = desk.open.length - 1; index >= 0; index -= 1) {
    if (desk.open[index].family === family) desk.open.splice(index, 1)
  }
}

/**
 * Open windows in the order they arrived, which is the dock's order rather
 * than the stack's. See `arrivals`.
 */
export function byArrival(open) {
  return [...open].sort((a, b) => a.seq - b.seq)
}

/** Everything, shut. What signing out does — a desk is a session. */
export function clear() {
  desk.open.splice(0, desk.open.length)
}
