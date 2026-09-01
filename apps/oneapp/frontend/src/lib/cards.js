import { plainText } from './format'

/**
 * A record, drawn as a card.
 *
 * The board and the grid are the same card twice. A board buckets its cards by
 * a field and lets you drag one from bucket to bucket; a grid lays the same
 * cards out flat. That difference is entirely about arrangement, and a card
 * knows nothing about arrangement — so it lives here, once, and the two bodies
 * are the two ways of putting these on a page.
 *
 * `RecordCard` was already shared, between a board card and the hover card
 * over a link. What was not shared was the answer to "what goes on it", which
 * is the half with the rules in it: which field is the title, which fields the
 * card already says in its own way, and what an empty one means.
 *
 * `spaceview._cards` is the server's half — which fields a reader chose, and
 * making sure they are fetched.
 */

// The activity column is a row's meta — likes, comments, when it moved — and
// not a field of the record. It has a place in a list, under a heading that
// says what the numbers are; on a card it is two glyphs and no explanation.
export const META_COLUMN = '__activity'

/**
 * Who the record is: a face, its title, and its id under the title.
 *
 * The same identity the chip draws everywhere else, which is the point — a
 * card and a link to the same record should not disagree about its name. The
 * id is dropped where the title already *is* the id, because "TASK-0007"
 * printed twice is not more informative than once.
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
 * The reader's own list where they have made one — and it is taken as given:
 * somebody who puts the status on a board card meant to put it there, even
 * though the column heading above it already says the same thing.
 *
 * Where they have not, the columns they are looking at, minus the ones the
 * card already says in its own way: the title, which is the card's heading,
 * the activity column, and whatever the caller says is redundant here (a
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
 * A blank field is not on the card at all. A list draws an em dash for an empty
 * cell because the column heading above it says what is missing; a card has no
 * headings, so four dashes say only "there are fields here and they are empty".
 * Frappe's own kanban card does the same — what is on it is what is filled in.
 *
 * Which is why the cap comes after the filter and not before: capping first
 * gave one card four fields and the next one none, from the same list.
 */
export function cardValues(row, shown, cap) {
  const filled = (shown || [])
    .map((c) => ({ ...c, value: row[c.fieldname] }))
    .filter((c) => c.value !== null && c.value !== undefined && c.value !== '')
  return cap ? filled.slice(0, cap) : filled
}
