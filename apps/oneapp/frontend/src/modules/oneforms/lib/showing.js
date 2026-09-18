/**
 * When a field is asked, and when it is not.
 *
 * `oneapp/oneforms/showing.py` is the other half and is the one that decides —
 * this draws, that enforces. Both compare a `{field, op, value}` tuple the
 * server parsed, and neither evaluates anything: `depends_on` nominally holds a
 * JavaScript expression and Frappe's own renderer evals it, which is exactly
 * what `docs/ONEFORMS.md` §12 refused for `client_script`. A page strangers
 * open does not run a customer's code, and an admin's own code is still code.
 *
 * So the rule arrives parsed, this compares it, and a field whose condition
 * fails is not drawn *and* is not sent — a value left behind for a question
 * that stopped being asked is an answer to something nobody asked.
 */

/** Numbers where both sides are numbers, so `count == 3` matches the string. */
const asNumber = (value) => {
  if (typeof value === 'boolean') return value ? 1 : 0
  if (typeof value === 'number') return value
  const said = String(value ?? '').trim()
  if (said === '') return null
  if (said.toLowerCase() === 'true') return 1
  if (said.toLowerCase() === 'false') return 0
  const found = Number(said)
  return Number.isNaN(found) ? null : found
}

/**
 * Equal, as somebody filling a form in would mean it: trimmed, and
 * case-insensitive because the difference between "Yes" and "yes" is a Select
 * option's capitalisation that nobody filling the form in can see.
 */
const same = (said, wanted) => {
  const left = asNumber(said)
  const right = asNumber(wanted)
  if (left !== null && right !== null) return left === right
  return String(said ?? '').trim().toLowerCase() === String(wanted ?? '').trim().toLowerCase()
}

/** Whether a parsed condition is true of what has been filled in so far. */
export function holds(rule, values) {
  if (!rule || !rule.field) return true

  const said = values?.[rule.field] ?? ''
  const wanted = rule.value ?? ''

  if (rule.op === '==') return same(said, wanted)
  if (rule.op === '!=') return !same(said, wanted)
  if (rule.op === 'in') return String(wanted).split(',').some((one) => same(said, one.trim()))

  const left = asNumber(said)
  const right = asNumber(wanted)
  if (left === null || right === null) return false
  if (rule.op === '>') return left > right
  if (rule.op === '>=') return left >= right
  if (rule.op === '<') return left < right
  if (rule.op === '<=') return left <= right
  return true
}

/**
 * The fields worth drawing, given what has been answered.
 *
 * Hidden-by-the-form and hidden-by-a-condition are the same thing to whoever is
 * reading the page, so they are answered in one place — otherwise every caller
 * has to remember both.
 */
export const asked = (fields, values) =>
  (fields || []).filter((one) => !one.hidden && holds(one.shown_when, values))

/**
 * What to send, which is not everything that is in `values`.
 *
 * Somebody who answers a question, changes the answer above it and so puts that
 * question away has left a value behind for something the form stopped asking.
 * Sending it would file an answer to a question nobody was asked; the server
 * clears them too, because a browser is not a rule.
 */
export function answered(fields, values) {
  const live = new Set(asked(fields, values).map((one) => one.fieldname))
  const out = {}
  for (const field of fields || []) {
    if (!field.fieldname) continue
    if (live.has(field.fieldname) || field.hidden) out[field.fieldname] = values?.[field.fieldname]
  }
  return out
}
