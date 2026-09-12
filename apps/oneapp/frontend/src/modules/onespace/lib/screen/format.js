/**
 * How a value reads.
 *
 * Three answers stacked, most specific first: the field's own `precision`, then
 * the site's `float_precision` / `currency_precision`, then a plain rendering.
 * Without the middle one a Float column renders with whatever
 * `toLocaleString` defaults to, which is not the same answer across two
 * browsers.
 *
 * Pure in the part that is a judgement — how many decimals this column wants,
 * which is a question about a docfield and takes the site's formats as an
 * argument. Where the separators go is not a judgement and is not pure: it is
 * the workspace's own setting, read once in `lib/runtime/format`.
 *
 * The currency *symbol* is deliberately absent — which currency a field is in
 * is a separate question from how many decimal places to show.
 */

import { number as written } from '@/shared/lib/runtime/format'

/**
 * Decimal places for one column: the field's own answer, else the site's.
 * `precision` of 0 means unset rather than "no decimals" — Frappe stores it as
 * a Select whose blank option is the empty string.
 */
export function precisionFor(column, formats = {}) {
  const own = Number(column?.precision)
  if (own) return own

  // Money and floats are two different settings about two different things.
  // Reading the float precision when the currency one is absent is not a
  // fallback Frappe makes, and it rendered every contract value with a
  // thousandth of a dirham on the end.
  if (column?.cell === 'currency') {
    return Number(formats.currency_precision ?? 2)
  }
  return Number(formats.float_precision ?? 3)
}

/**
 * Group the thousands and fix the decimals. An Int carries no decimals whatever
 * the site says: a count of 3 is not "3.000".
 */
export function formatNumber(value, column, formats = {}) {
  // `Number(null)` and `Number('')` are both 0, so an empty cell would render
  // as "0.000". Emptiness is the caller's to draw.
  if (value === null || value === undefined || value === '') return ''

  const number = Number(value)
  if (!Number.isFinite(number)) return String(value)

  const whole = column?.fieldtype === 'Int' || column?.fieldtype === 'Long Int'
  let digits = whole ? 0 : precisionFor(column, formats)

  // A percentage never reads to more places than were stored — Frappe's own
  // `formatters.Percent` takes `min(precision, the value's own decimals)`.
  // Without it a project 89.12% done rendered as `89.120%`.
  if (column?.cell === 'percent') {
    digits = Math.min(digits, decimalsOf(number))
  }

  // `written`, not `toLocaleString`: the browser's own language decides where
  // `toLocaleString` puts its separators, so a German workspace that had set
  // `#.###,##` saw `1,234.50` or `1.234,50` depending on nothing anybody
  // configured — two colleagues reading the same invoice differently, with no
  // way for either to tell. `lib/runtime/format` reads the workspace's own
  // setting instead. See `docs/UNIFICATION.md` §D1.
  return written(number, digits)
}


/**
 * How many decimal places a number actually carries. Off the string and through
 * the exponent, because `1e-7` is one significant digit written seven places
 * down.
 */
function decimalsOf(number) {
  const [mantissa, exponent] = String(number).toLowerCase().split('e')
  const places = (mantissa.split('.')[1] || '').length - Number(exponent || 0)
  return Math.max(places, 0)
}

/**
 * Markup as one line of text.
 *
 * A title field may hold HTML — ToDo's `description` is exactly that — and
 * drawn raw the title of every record reads `<p>Chase the invoice</p>` in the
 * list, the crumb and every link chip. Stripping rather than rendering, because
 * interpreting markup in a title would be a security decision made in four
 * places.
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
