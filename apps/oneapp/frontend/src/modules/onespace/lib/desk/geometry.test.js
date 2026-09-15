// Where a window is and how big — the arithmetic, and the edges it has.
//
// `docs/UNIFICATION.md` F3's meta-rail is that every guard has a witness. The
// guard here is `fit`, and what it guards against is a window somebody cannot
// close: one whose title bar is off the top of the screen, or whose corner is
// past the right edge after the browser was made narrower. Each of those is a
// case below rather than a sentence in a docstring.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  DOCK, FLOOR, MARGIN, corner, fit, full, grow, keep, opened, room, wasFull,
} from './geometry'

/** The desk, which is what is left of a 1280x856 window once the dock has its
 *  row. Every case here passes it explicitly; `room()` has one of its own. */
const DESK = { w: 1280, h: 800 }

describe('fit', () => {
  it('leaves a window that is already inside alone', () => {
    const was = { x: 100, y: 120, w: 400, h: 560 }
    expect(fit(was, DESK)).toEqual(was)
  })

  it('pulls a window back when the desk got smaller', () => {
    // The case this exists for: a 1280 window, then the browser is narrowed to
    // 800. Without this the close button is past the right edge and the only
    // way out is the keyboard.
    const found = fit({ x: 1000, y: 700, w: 400, h: 560 }, { w: 800, h: 600 })
    expect(found.x + found.w).toBeLessThanOrEqual(800)
    expect(found.y + found.h).toBeLessThanOrEqual(600)
  })

  it('never puts the leading edge off the top or the start', () => {
    const found = fit({ x: -400, y: -200, w: 400, h: 560 }, DESK)
    expect(found.x).toBe(0)
    expect(found.y).toBe(0)
  })

  it('raises a window somebody made unreadably small', () => {
    const found = fit({ x: 0, y: 0, w: 10, h: 10 }, DESK)
    expect(found.w).toBe(FLOOR.w)
    expect(found.h).toBe(FLOOR.h)
  })

  it('honours a tenant that needs more room than the floor', () => {
    const found = fit({ x: 0, y: 0, w: 100, h: 100 }, DESK, { w: 600, h: 700 })
    expect(found).toMatchObject({ w: 600, h: 700 })
  })

  it('gives up the floor on a desk too small for it', () => {
    // A 340 floor on a 320 viewport would hang the window off the edge, so the
    // window becomes the desk. Clamping the floor is the whole of this.
    const found = fit({ x: 0, y: 0, w: 400, h: 560 }, { w: 320, h: 300 })
    expect(found).toEqual({ x: 0, y: 0, w: 320, h: 300 })
  })
})

describe('corner', () => {
  it('is the bottom end, one margin clear of both edges', () => {
    expect(corner({ w: 400, h: 560 }, DESK)).toEqual({
      w: 400, h: 560, x: 1280 - 400 - MARGIN, y: 800 - 560 - MARGIN,
    })
  })

  it('still lands inside a desk with no room for the margin', () => {
    const found = corner({ w: 400, h: 560 }, { w: 380, h: 500 })
    expect(found.x).toBe(0)
    expect(found.y).toBe(0)
  })
})

describe('grow', () => {
  const FROM = { x: 800, y: 200 }

  it('is the distance from the origin to the pointer', () => {
    expect(grow(FROM, { x: 1200, y: 700 }, DESK)).toEqual({ w: 400, h: 500 })
  })

  it('stops at the edge rather than moving the window', () => {
    // The bug this exists for. Unclamped, the width runs past the desk, `fit`
    // pulls the origin back to make room, and the next pointer event measures
    // from the new origin — so the window walks across the screen while
    // somebody holds still.
    const found = grow(FROM, { x: 4000, y: 4000 }, DESK)
    expect(FROM.x + found.w).toBeLessThanOrEqual(DESK.w)
    expect(FROM.y + found.h).toBeLessThanOrEqual(DESK.h)
  })

  it('will not go under the floor, however far back the pointer is dragged', () => {
    expect(grow(FROM, { x: 10, y: 10 }, DESK)).toEqual({ w: FLOOR.w, h: FLOOR.h })
  })

  it('keeps the floor even where the room cannot hold it', () => {
    // A window dragged to the far corner of a small desk: the floor wins, and
    // `fit` is the one that then decides where it sits.
    expect(grow({ x: 300, y: 300 }, { x: 320, y: 320 }, { w: 400, h: 400 }))
      .toEqual({ w: FLOOR.w, h: FLOOR.h })
  })
})

describe('the desk', () => {
  it('is the viewport less the dock', () => {
    // A window filling the desk must not cover the dock, because the dock's
    // tile is how it is folded away — covered, the only way out is the close
    // button, which throws away what is in the window.
    vi.stubGlobal('window', { innerWidth: 1280, innerHeight: 800 + DOCK })
    expect(room()).toEqual(DESK)
    vi.unstubAllGlobals()
  })
})

describe('full', () => {
  it('is the desk less its margin, not the whole screen', () => {
    // A window filling the desk still reads as a window over a page. The page
    // underneath is the thing you came back to.
    expect(full(DESK)).toEqual({ x: MARGIN, y: MARGIN, w: 1240, h: 760 })
  })
})

describe('what is remembered', () => {
  // The suite runs on `node`, where there is no window and no storage — which
  // is also the case `remember.js` answers `null` for, so a test that only ran
  // there would pass without ever storing anything. A Map behind a `window` is
  // the smallest thing that makes the round trip real.
  beforeEach(() => {
    const held = new Map()
    vi.stubGlobal('window', {
      innerWidth: DESK.w,
      // The window, not the desk: the dock's row comes off it.
      innerHeight: DESK.h + DOCK,
      localStorage: {
        getItem: (key) => (held.has(key) ? held.get(key) : null),
        setItem: (key, value) => held.set(key, String(value)),
        removeItem: (key) => held.delete(key),
      },
    })
  })

  afterEach(() => vi.unstubAllGlobals())

  it('opens in the default corner when nothing was stored', () => {
    expect(opened('nobody', { w: 400, h: 560 })).toEqual(corner({ w: 400, h: 560 }, DESK))
  })

  it('comes back where it was left', () => {
    keep('mail', { x: 120, y: 90, w: 700, h: 500 }, 'where')
    keep('mail', { x: 120, y: 90, w: 700, h: 500 }, 'size')
    expect(opened('mail', { w: 400, h: 560 })).toMatchObject({
      x: 120, y: 90, w: 700, h: 500,
    })
  })

  it('keeps a size that was never moved', () => {
    // Size and position are written separately because they are changed
    // separately: a window resized and never dragged should keep its size and
    // take the default corner.
    keep('drive', { x: 0, y: 0, w: 900, h: 600 }, 'size')
    expect(opened('drive', { w: 400, h: 560 })).toMatchObject({ w: 900, h: 600 })
  })

  it('does not trust a position from a wider monitor', () => {
    keep('mail', { x: 4000, y: 3000, w: 400, h: 560 }, 'where')
    const found = opened('mail', { w: 400, h: 560 })
    expect(found.x + found.w).toBeLessThanOrEqual(DESK.w)
  })

  it('remembers nothing about filling the desk until somebody does', () => {
    expect(wasFull('mail')).toBe(false)
  })

  it('does not let one window read another one’s corner', () => {
    keep('mail', { x: 11, y: 22, w: 700, h: 500 }, 'where')
    expect(opened('drive', { w: 400, h: 560 }).x).not.toBe(11)
  })
})
