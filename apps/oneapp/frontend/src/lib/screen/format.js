/**
 * How a value reads.
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

  // Money and floats are two different settings about two different things.
  // Reading the float precision when the currency one is absent is not a
  // fallback Frappe makes, and it rendered every contract value in the product
  // with a thousandth of a dirham on the end. The server answers this from the
  // site's number format; two is what every format Frappe ships but one uses.
  if (column?.cell === 'currency') {
    return Number(formats.currency_precision ?? 2)
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
  let digits = whole ? 0 : precisionFor(column, formats)

  // A percentage never reads to more places than were stored. Frappe's own
  // `formatters.Percent` takes `min(precision, the value's own decimals)`, and
  // this is that rule: a project 89.12% done rendered as `89.120%` at the
  // site's float precision, and one that has not started rendered as `0.000%`
  // — three digits of a number nobody measured.
  if (column?.cell === 'percent') {
    digits = Math.min(digits, decimalsOf(number))
  }

  return number.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}


/**
 * How many decimal places a number actually carries.
 *
 * Off the string rather than by arithmetic, and through the exponent, because
 * `1e-7` is one significant digit written seven places down and `Number.toFixed`
 * on it is not what a person means by "how precise is this".
 */
function decimalsOf(number) {
  const [mantissa, exponent] = String(number).toLowerCase().split('e')
  const places = (mantissa.split('.')[1] || '').length - Number(exponent || 0)
  return Math.max(places, 0)
}

/**
 * Markup as one line of text.
 *
 * A Text Editor field holds HTML, and a title field may be one — ToDo's
 * `description` is exactly that. Drawn raw, the title of every record reads
 * `<p>Chase the Halloway invoice</p>`, in the list, in the crumb and in every
 * link chip pointing at it.
 *
 * Stripping rather than rendering, and everywhere a title is drawn rather than
 * once in the list: a title is one line, and interpreting markup there would be
 * a security decision made in four places. The record's own field still gets
 * the real HTML, because that is what it is editing.
 */
export function plainText(value) {
  if (value === null || value === undefined) return ''
  const text = String(value)
  if (!text.includes('<')) return text
  return text
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}
