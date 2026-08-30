/**
 * How a number reads.
 *
 * Three answers stacked, most specific first: the field's own `precision`, then
 * the site's `float_precision` / `currency_precision` from System Settings, then
 * a plain rendering. Without the middle one a Float column renders with whatever
 * `toLocaleString` defaults to, which is not the same answer twice across two
 * browsers — and the doctype's own `precision` was travelling to the browser and
 * being ignored entirely.
 *
 * Pure, and takes the site's formats as an argument rather than importing the
 * session. Every function here is a question about a number and a docfield, so
 * reaching for application state to answer one would make it untestable in
 * exchange for saving a caller one word.
 *
 * The currency *symbol* is deliberately absent. A Currency field's currency
 * comes from another field on the record or from the site default, and
 * resolving it is a separate question from how many decimal places to show.
 */

/**
 * Decimal places for one column: the field's own answer, else the site's.
 *
 * `precision` of 0 on a DocField means unset rather than "no decimals" — Frappe
 * stores it as a Select whose blank option is the empty string — so a falsy
 * value falls through to the site.
 */
export function precisionFor(column, formats = {}) {
  const own = Number(column?.precision)
  if (own) return own

  if (column?.cell === 'currency') {
    return Number(formats.currency_precision ?? formats.float_precision ?? 2)
  }
  return Number(formats.float_precision ?? 3)
}

/**
 * Group the thousands and fix the decimals.
 *
 * An Int carries no decimals whatever the site says: precision is a question
 * about fractions, and a count of 3 is not "3.000".
 */
export function formatNumber(value, column, formats = {}) {
  // `Number(null)` is 0 and `Number('')` is 0, so an empty cell would render
  // as "0.000" — a number nobody stored. Emptiness is the caller's to draw.
  if (value === null || value === undefined || value === '') return ''

  const number = Number(value)
  if (!Number.isFinite(number)) return String(value)

  const whole = column?.fieldtype === 'Int' || column?.fieldtype === 'Long Int'
  const digits = whole ? 0 : precisionFor(column, formats)

  return number.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}
