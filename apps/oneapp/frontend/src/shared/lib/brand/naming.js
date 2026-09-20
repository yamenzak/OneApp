/**
 * Whether a name on screen is ours to write or somebody else's to keep.
 *
 * Every app of ours is `One` and a word, and the prefix is the part that is the
 * same on all of them — so it is said quietly, which is what `SpaceName` does.
 * Two names are not ours to style that way: a space a customer renamed, and an
 * assistant a workspace named. Those are said whole.
 *
 * The switcher used to decide by *kind* — a space is somebody's, an app is
 * ours — and got the commonest case wrong in both states: OneHR in the
 * corner was a space, so the corner wrote it flat while the board one row down
 * wrote it the family way. The question is not what kind of thing it is. It is
 * whether the name is still the one the mark carries.
 */
import { MARKS } from '@/shared/lib/brand/marks'

/** True where this label is a name somebody chose rather than the product's. */
export function theirs(brand, label) {
  const ours = MARKS[brand]?.name || ''
  return !ours || String(label || '') !== ours
}

/**
 * An app's own colour, for a surface that wants the hue without the drawing.
 *
 * `MARKS[brand].colour` is the middle stop of the mark's gradient — see
 * `scripts/gen_brand.py` — so it is the colour somebody would name if you
 * showed them the icon. A window's chrome is tinted with it, which is what it
 * was generated for and what nothing was using it for.
 *
 * Empty for a brand nobody declared, which every caller treats as "grey, like
 * it always was" rather than as a failure: a window with no tint is a window.
 */
export function colourOf(brand) {
  return MARKS[brand]?.colour || ''
}

/**
 * What an app is called, read rather than typed.
 *
 * `MARKS[brand].name` is the only place a product name is written down —
 * `CLAUDE.md` and `scripts/gen_brand.py`, and the reason is that four of the
 * ids disagree with their names on purpose. `SpaceName` is what draws one on
 * screen; this is for the places that need the string itself, like a window's
 * accessible name.
 */
export function nameOf(brand) {
  return MARKS[brand]?.name || ''
}
