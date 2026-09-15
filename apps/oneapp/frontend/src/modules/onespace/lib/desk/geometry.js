/**
 * Where a window is and how big, as arithmetic nothing has to be mounted for.
 *
 * `AssistantWidget` worked all of this out for itself — the floors, the
 * clamping, the default corner, the two remembered numbers — and it was right
 * about every one of them. It was also the only window in the product, so the
 * arithmetic lived in the component that happened to need it first. There are
 * about to be several, which is the moment `docs/UNIFICATION.md` F1 says the
 * abstraction is usually abandoned instead.
 *
 * Pure, and that is the point: a window's geometry is the part with edge cases
 * — a viewport that shrank under an open window, a remembered position from a
 * wider monitor, a floor that cannot be honoured because the window itself is
 * smaller than it — and none of them needs a DOM to be tested.
 *
 * `docs/DESKTOP.md` stage 1.
 */

import { recall, remember } from '@/shared/lib/url/remember'

/**
 * How far off the edge a window sits by default.
 *
 * Clear of the dial's corner, which is where the eye already is — and it is
 * the same number at every edge, so a window placed by default reads as
 * deliberate rather than as wherever it landed.
 */
export const MARGIN = 20

/**
 * The smallest a window may be.
 *
 * Not taste: below about 340 a line of text stops being a line and becomes a
 * column of two words, and below 420 a transcript shows one turn. A tenant
 * may raise these and may not lower them, because the floor is about reading
 * rather than about what the tenant would like.
 */
export const FLOOR = Object.freeze({ w: 340, h: 420 })

/** The declared storage key. A prefix; the parts after it say which window. */
export const KEY = 'desk.at'

/** What is stored under it, per window. */
export const WHERE = 'where'
export const SIZE = 'size'
export const FULL = 'full'

/**
 * How tall the dock is — `components/desk/Dock.vue`'s own `h-12`.
 *
 * Written here as well as there because this is the half that has consequences:
 * the desk is the viewport *less the dock*, so a window filling it stops short
 * of the row rather than covering it. That matters more than it sounds. The
 * dock's tile is how a window is folded away, and a maximised window that
 * covered the tile that folds it would be a window with one way out — the close
 * button, which throws away what is in it.
 */
export const DOCK = 48

/**
 * The desk: the viewport, less the dock along its foot.
 *
 * Everything else here works in this space, so nothing else has to know the
 * dock exists — `corner` puts a new window one margin above it, `fit` keeps a
 * dragged one off it, and `full` stops at it.
 */
export function room() {
  if (typeof window === 'undefined') return { w: 1280, h: 800 - DOCK }
  return { w: window.innerWidth, h: Math.max(0, window.innerHeight - DOCK) }
}

/**
 * One box, inside the viewport, whatever the viewport has just done.
 *
 * Size first and then position, because a window wider than the room has to be
 * narrowed before there is anywhere to put it. Both are clamped rather than
 * refused: a window whose close button is off the edge of the screen is a
 * window nobody can shut, which is the one failure here that cannot be undone
 * from inside the product.
 *
 * The floor is itself clamped to the room. On a 320-wide viewport a 340 floor
 * is unreachable, and honouring it would hang the window off the edge — so on
 * a desk too small for the floor the window is the desk.
 */
export function fit(box, where = room(), floor = FLOOR) {
  const w = Math.min(Math.max(box.w, Math.min(floor.w, where.w)), where.w)
  const h = Math.min(Math.max(box.h, Math.min(floor.h, where.h)), where.h)
  return {
    w,
    h,
    x: Math.min(Math.max(box.x, 0), Math.max(0, where.w - w)),
    y: Math.min(Math.max(box.y, 0), Math.max(0, where.h - h)),
  }
}

/**
 * Where a window goes when nobody has moved it: the bottom end corner.
 *
 * The corner the dial is in, so opening something from the dock puts it where
 * the press was. A thing that appears somewhere else is a thing you have to go
 * and find.
 */
export function corner(size, where = room()) {
  return fit({
    ...size,
    x: where.w - size.w - MARGIN,
    y: where.h - size.h - MARGIN,
  }, where)
}

/**
 * Filling the desk, which is what maximise means here.
 *
 * Not the whole viewport: the margin stays, so a maximised window still reads
 * as a window over a page rather than as a page that replaced it. The page
 * underneath is the thing you came back to.
 */
export function full(where = room()) {
  return {
    x: MARGIN,
    y: MARGIN,
    w: Math.max(0, where.w - MARGIN * 2),
    h: Math.max(0, where.h - MARGIN * 2),
  }
}

/**
 * How big a window becomes when its far corner is dragged to a point.
 *
 * Clamped against the room *from the origin*, which is what stops the window
 * moving while it is resized. Without it the width can exceed the desk, `fit`
 * pulls the origin back to make it fit, and the window slides away from under
 * the pointer — and if the width is then measured from the new origin it grows
 * again on the next event. Four hundred pixels became nine hundred in one drag.
 *
 * So a window being resized stops at the edge, which is what a desk does.
 */
export function grow(origin, pointer, where = room(), floor = FLOOR) {
  return {
    w: Math.min(Math.max(pointer.x - origin.x, floor.w), Math.max(floor.w, where.w - origin.x)),
    h: Math.min(Math.max(pointer.y - origin.y, floor.h), Math.max(floor.h, where.h - origin.y)),
  }
}

/** Two numbers off a stored `"a,b"`, or null where there are not two. */
function pair(said) {
  const found = String(said || '').split(',').map(Number)
  return found.length === 2 && found.every(Number.isFinite) ? found : null
}

/**
 * The box this window was last left in, or the default corner.
 *
 * `size` and `where` are read separately because they are written separately:
 * dragging moves one and resizing writes both, and a window that had been
 * resized but never moved should keep its size.
 */
export function opened(id, size, where = room()) {
  const kept = pair(recall(KEY, id, SIZE))
  const wanted = kept && kept[0] ? { w: kept[0], h: kept[1] } : { ...size }
  const at = pair(recall(KEY, id, WHERE))
  if (!at) return corner(wanted, where)
  return fit({ ...wanted, x: at[0], y: at[1] }, where)
}

/** Rounded, because half a pixel is not a habit worth storing. */
export function keep(id, box, what = WHERE) {
  if (what === SIZE) remember(KEY, `${Math.round(box.w)},${Math.round(box.h)}`, id, SIZE)
  else remember(KEY, `${Math.round(box.x)},${Math.round(box.y)}`, id, WHERE)
}

/** Whether this window was left maximised, and saying so. */
export function wasFull(id) {
  return recall(KEY, id, FULL) === 'yes'
}

export function keepFull(id, on) {
  remember(KEY, on ? 'yes' : 'no', id, FULL)
}
