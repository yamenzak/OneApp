import { plainText } from '@/modules/onespace/lib/screen/format'

/**
 * A record, drawn as a card.
 *
 * The board and the grid are the same card twice: a board buckets its cards by
 * a field, a grid lays them out flat, and a card knows nothing about
 * arrangement. `RecordCard` was already shared; what was not was the answer to
 * "what goes on it", which is the half with the rules in it.
 *
 * `spaceview._cards` is the server's half — which fields a reader chose, and
 * making sure they are fetched.
 */

// The activity column is a row's meta — likes, comments, when it moved — and
// not a field of the record. On a card it is two glyphs and no explanation.
export const META_COLUMN = '__activity'

/**
 * Who the record is: a face, its title, and its id under the title. The same
 * identity the chip draws everywhere else. The id is dropped where the title
 * already *is* the id.
 */
export function cardIdentity(row, spec) {
  const title = spec?.title_field
  const label = (title && row[title]) || row.name
  return {
    value: row.name,
    label: String(label),
    id: plainText(String(label)) === row.name ? '' : row.name,
    image: spec?.image_field ? row[spec.image_field] : null,
  }
}

/**
 * Which fields a card carries, in order.
 *
 * The reader's own list where they have made one, taken as given. Otherwise the
 * columns they are looking at, minus what the card already says in its own way:
 * the title, the activity column, and whatever the caller says is redundant (a
 * board passes the field its columns are made of).
 *
 * @param {object} spec     the resolved screen, for `all_columns` and the title
 * @param {Array}  columns  the columns the rows came back with
 * @param {Array}  chosen   fieldnames the reader picked, or empty
 * @param {Array}  exclude  fieldnames this arrangement already says elsewhere
 */
export function cardShown({ spec, columns = [], chosen = [], exclude = [] }) {
  const offered = spec?.all_columns || columns || []
  if (chosen.length) {
    return chosen.map((name) => offered.find((c) => c.fieldname === name)).filter(Boolean)
  }
  const said = new Set([
    META_COLUMN,
    'name',
    spec?.title_field || 'name',
    ...exclude.filter(Boolean),
  ])
  return (columns || []).filter((c) => !said.has(c.fieldname) && c.list_ok !== false)
}

/**
 * What one row puts on its card: those fields, with their values, minus the
 * blanks, capped.
 *
 * A blank field is not on the card at all — a list draws an em dash because the
 * heading above says what is missing, and a card has no headings. Which is why
 * the cap comes after the filter: capping first gave one card four fields and
 * the next one none.
 */
export function cardValues(row, shown, cap) {
  const filled = (shown || [])
    .map((c) => ({ ...c, value: row[c.fieldname] }))
    .filter((c) => c.value !== null && c.value !== undefined && c.value !== '')
  return cap ? filled.slice(0, cap) : filled
}
