import { cellText } from '@/modules/onespace/lib/screen/cells'
import { workspace } from '@/shared/lib/workspace'

/**
 * The records hanging off one record, for a surface that draws them.
 *
 * Two surfaces want the same thing and want it drawn differently — the showcase
 * as a strip of cards, the person page as a row of faces — which is the moment
 * to extract rather than the moment to copy. `docs/UNIFICATION.md` F1: every
 * abstraction here was built at the second caller and abandoned at the third,
 * and this is the second caller.
 *
 * Through the ordinary list endpoint, with a narrowing filter, which is the
 * whole point of declaring children as a screen and a field rather than as a
 * query: the space, the permissions and the filter are checked where every
 * other list checks them. A surface may read — it may not invent a way to.
 */

/** How many. A glance at who is there; the tab is where the list lives. */
export const KEPT = 24

/**
 * One row, as a surface draws it: something to show, something to say under it,
 * and the id to open.
 *
 * `detail` is the first column that is not the title — on a variation order its
 * stage, on a direct report their job. Through `cellText` rather than printed
 * raw, so a number here and the same number in its column are one number.
 */
export function shapeChildren(rows, columns, spec, formats) {
  const titleField = spec?.title_field || 'name'
  const imageField = spec?.image_field || ''
  const first = (columns || []).find(
    (one) => one.fieldname !== titleField && one.fieldname !== '__activity',
  )
  return (rows || []).map((row) => ({
    name: row.name,
    label: String(row[titleField] || row.name),
    image: imageField ? row[imageField] || '' : '',
    detail: first
      ? cellText(first, row[first.fieldname], formats, row._links?.[first.fieldname])
      : '',
  }))
}

/**
 * Fetch and shape them, with the child screen's own spec beside them.
 *
 * The spec is part of the answer rather than a second call a caller has to
 * remember: a card here says what a row of *that* screen says, and reading it
 * off the parent's spec is right only while a record's children are its own
 * doctype.
 */
export async function loadChildren({ spaceCode, screen, field, name, formats, limit = KEPT }) {
  if (!name || !screen || !field) return { spec: null, children: [] }

  const [spec, found] = await Promise.all([
    workspace.screenSpec(spaceCode, screen),
    workspace.screenRows(
      spaceCode,
      screen,
      { filters: [[field, '=', name]] },
      '',
      { start: 0, limit },
    ),
  ])

  return {
    spec: spec || null,
    children: shapeChildren(found?.rows || [], found?.columns || [], spec, formats),
  }
}
