/**
 * A flat list of `Web Form Field` rows, read as a page.
 *
 * `docs/ONEFORMS.md` §13. Stage 3 drew the list straight down the page, which
 * is what the rows literally are and not what they mean: three of them are
 * furniture rather than questions, and the reader is the only thing that knows
 * where one page ends.
 *
 *   * **Page Break** starts a new step — dots at the top, a Next at the
 *     bottom, and one screenful at a time. This is the one that makes a form
 *     of thirty questions finishable, and it is what Frappe's own renderer has
 *     always done with the same field.
 *   * **Section Break** starts a titled group inside a step.
 *   * **Column Break** puts what follows beside what came before rather than
 *     under it, which is how two short fields stop taking two full rows.
 *
 * Pure, and its own file so `layout.test.js` can hold it to the awkward cases
 * — a break before any field, two in a row, a trailing one — which are what a
 * drag-and-drop builder produces constantly and which decide whether the page
 * draws an empty box.
 */

/** The three that are furniture. Everything else is a question. */
export const BREAKS = ['Page Break', 'Section Break', 'Column Break']

/** Whether this row is one of them. */
export const isBreak = (field) => BREAKS.includes(field?.fieldtype)

/**
 * `[{ label, shown_when, sections: [{ label, columns: [[field, …], …] }] }]`.
 *
 * Empty columns and empty sections are dropped on the way out, so a builder
 * that left two section breaks together does not produce a heading with
 * nothing under it. A section keeps its label even where the reader gave it
 * none — a blank heading is not drawn, and grouping without a title is still
 * grouping.
 */
export function pagesOf(fields) {
  // A page break's own condition rides on the step it *opens*, so the first
  // step can never carry one — there is no break before it. That is the right
  // shape: a form whose first question could be skipped is a form that can
  // open on nothing.
  const pages = []
  let page = null
  let section = null
  let column = null

  const startPage = (when) => {
    page = { label: '', shown_when: when || null, sections: [] }
    pages.push(page)
    section = null
    startSection('')
  }
  const startSection = (label) => {
    section = { label: label || '', columns: [] }
    page.sections.push(section)
    startColumn()
  }
  const startColumn = () => {
    column = []
    section.columns.push(column)
  }

  startPage()
  for (const field of fields || []) {
    if (field.fieldtype === 'Page Break') startPage(field.shown_when)
    else if (field.fieldtype === 'Section Break') startSection(field.label)
    else if (field.fieldtype === 'Column Break') startColumn()
    else column.push(field)
  }

  return pages
    .map((one) => ({
      ...one,
      sections: one.sections
        .map((each) => ({ ...each, columns: each.columns.filter((c) => c.length) }))
        .filter((each) => each.columns.length),
    }))
    .filter((one) => one.sections.length)
}

/**
 * The step a field is on, for sending somebody back to their own mistake.
 *
 * The server validates too and its refusal names a fieldname, which is no use
 * on page three of four: without this, "Email is required" appears over a step
 * the reader cannot see.
 */
export function pageOf(pages, fieldname) {
  const at = pages.findIndex((page) =>
    page.sections.some((section) =>
      section.columns.some((column) =>
        column.some((field) => field.fieldname === fieldname))))
  return at < 0 ? 0 : at
}


/**
 * The steps that are being asked, given what has been answered.
 *
 * A page break may carry a condition, so a whole step can be skipped by an
 * answer on an earlier one — "tell us about the vehicle" only where they said
 * they are driving. Kept out of `pagesOf` on purpose: the layout of a form does
 * not change as somebody fills it in, and only the *walk* through it does.
 */
export const walk = (pages, values, holds) =>
  (pages || []).filter((page) => !page.shown_when || holds(page.shown_when, values))
