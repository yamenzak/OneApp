/**
 * What a field is, on this record, for this reader.
 *
 * Four surfaces used to ask this and get four different answers. The form
 * folded in seven clauses; the child table and the inline cell folded in three
 * and a half each, and the half was the bug: a field declared
 * `read_only_depends_on` was locked in the form and editable in the grid.
 * Stage 0 closed the bug on both sides. This closes the thing that caused it,
 * which is that there was no one place to ask.
 *
 * **Three states, not two.** `disabled` was doing the work of two different
 * ideas and the visual result was the same grey for both:
 *
 *     writable   the control
 *     readonly   the value, as text, in the field's own layout — no box, no
 *                grey, no placeholder. This is the missing one, and it is
 *                most of what a record with twelve locked fields looks like.
 *     hidden     absent
 *
 * `disabled` survives in `FieldControl` for its true meaning only: a control
 * that is momentarily unavailable because something is in flight. A record
 * that cannot be edited is not a record whose controls are all busy.
 *
 * `docs/UNIFICATION.md` §B5.
 */
import { fieldRules } from '@/modules/onespace/lib/screen/rules'

export const STATE = Object.freeze({
  WRITABLE: 'writable',
  READONLY: 'readonly',
  HIDDEN: 'hidden',
})

export const STATES = Object.freeze(Object.values(STATE))

/**
 * One verdict, from every clause that has a say.
 *
 * The order is the order of certainty. Hidden first, because a field the
 * doctype says is not on this record has no other question to answer. Then
 * everything that locks it, cheapest first — and they are all ORs, so the
 * order among them is only about how quickly the answer is reached.
 *
 * `canWrite` is the *screen's* permission and `field.editable` the server's
 * verdict on `read_only` and permlevel; both are already computed elsewhere
 * and neither is recomputed here. What this adds is that all four surfaces
 * now fold in the same list.
 */
export function fieldState(field, doc, {
  canWrite = true,
  isNew = false,
  // The whole record is locked — a save in flight, a workflow the reader
  // cannot move, a screen opened read-only.
  locked = false,
} = {}) {
  const one = field || {}
  const rules = fieldRules(one, doc || {})

  if (rules.hidden) return STATE.HIDDEN

  //: `set_only_once` is a field you may fill in and never change, so it is
  //: writable exactly once: while the record is new.
  const once = !!one.set_only_once && !isNew

  //: A submitted record is editable only where the doctype said so, and a
  //: cancelled one nowhere.
  const status = Number(doc?.docstatus || 0)
  const submitted = status === 2 || (status === 1 && !one.allow_on_submit)

  if (locked || !canWrite || one.editable === false || once || submitted
      || rules.readOnly) {
    return STATE.READONLY
  }
  return STATE.WRITABLE
}

/** Shorthand for the common question, so a caller that only needs a boolean
 *  does not have to compare strings. */
export const writable = (...args) => fieldState(...args) === STATE.WRITABLE
