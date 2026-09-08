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

const PREFIX = 'onespace:child-columns'

const slot = (doctype, fieldname) => `${PREFIX}:${doctype}:${fieldname}`

/** The fieldnames this person chose, or `null` where they never chose. */
export function remembered(doctype, fieldname) {
  if (!doctype || !fieldname) return null
  try {
    const found = JSON.parse(window.localStorage.getItem(slot(doctype, fieldname)) || 'null')
    if (!Array.isArray(found) || !found.length) return null
    return found
      .map((one) => (typeof one === 'string' ? { fieldname: one, align: '' } : one))
      .filter((one) => one && typeof one.fieldname === 'string' && one.fieldname)
  } catch {
    // Private browsing, a blocked origin, a quota, or something that is not
    // JSON. A preference nobody can read is a preference nobody set.
    return null
  }
}

/** Remember them, or forget them — `null` puts the table back on the doctype. */
export function remember(doctype, fieldname, columns) {
  if (!doctype || !fieldname) return
  try {
    if (columns && columns.length) {
      const kept = columns.map((one) => ({ fieldname: one.fieldname, align: one.align || '' }))
      window.localStorage.setItem(slot(doctype, fieldname), JSON.stringify(kept))
    } else {
      window.localStorage.removeItem(slot(doctype, fieldname))
    }
  } catch {
    // The table still draws; it draws the doctype's answer next time.
  }
}
