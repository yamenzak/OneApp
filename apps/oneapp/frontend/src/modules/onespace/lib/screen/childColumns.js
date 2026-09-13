/**
 * Which columns a child table draws, per person and per table.
 *
 * The doctype decides by default — `in_list_view` on the child's own fields,
 * which is what the desk's grid uses and is a reasonable guess. It is only a
 * guess: an invoice line has fifteen fields, four of them fit across a form
 * column, and which four matter depends on whether you are pricing the job or
 * checking what was delivered.
 *
 * A saved view is where that choice lives everywhere else in this product, and
 * a child table has none: it is not a screen, it has no layouts of its own, and
 * inventing a second storage model for one grid would be a doctype nobody
 * would ever look at. So it is the browser's, like the pane's width and the
 * sidebar's fold — a per-viewer convenience that costs nothing to lose.
 *
 * Keyed by the child doctype and the parent's fieldname together: Quotation
 * Item under `items` and under `packed_items` are the same doctype answering
 * two different questions.
 *
 * Stored as `[{ fieldname, align }]` in the order they go across. It used to be
 * a list of fieldnames re-sorted into the doctype's own field order, on the
 * argument that its author had already decided — which is true of the default
 * and not of a choice somebody made afterwards. A person who drags Rate in
 * front of Quantity means it. Bare strings still read, so an older preference
 * survives.
 */

import { forget, recallJson, rememberJson } from '@/shared/lib/url/remember'
const KEY = 'child.columns'

/** The fieldnames this person chose, or `null` where they never chose. */
export function remembered(doctype, fieldname) {
  if (!doctype || !fieldname) return null
  const found = recallJson(KEY, doctype, fieldname)
  if (!Array.isArray(found) || !found.length) return null
  return found
    // An older answer held bare fieldnames; a newer one holds the alignment
    // beside each. Read either, write the second.
    .map((one) => (typeof one === 'string' ? { fieldname: one, align: '' } : one))
    .filter((one) => one && typeof one.fieldname === 'string' && one.fieldname)
}

/** Remember them, or forget them — `null` puts the table back on the doctype. */
export function remember(doctype, fieldname, columns) {
  if (!doctype || !fieldname) return
  if (columns && columns.length) {
    rememberJson(
      KEY,
      columns.map((one) => ({ fieldname: one.fieldname, align: one.align || '' })),
      doctype,
      fieldname,
    )
  } else {
    forget(KEY, doctype, fieldname)
  }
}
