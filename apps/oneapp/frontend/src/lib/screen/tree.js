import { cardIdentity } from '@/lib/screen/cards'

/**
 * A flat page of records, as the forest a tree draws.
 *
 * Separate from `TreeBody` because it is the only part of that view with a
 * decision in it: what happens to a record whose parent is not on the page, and
 * what happens when the data points in a circle.
 *
 * A record this cannot draw under its parent becomes a root, marked `orphan`.
 * The parent may be missing because a filter excluded it or because it is on a
 * page nobody has loaded, and a tree that silently hides a record for either
 * reason disagrees with the count in the footer.
 *
 * Order is the page's, at every level: nesting rows is not a reason to sort
 * them again.
 */
export function forestOf(rows, field, spec, groupField = '') {
  if (!field) return []

  const nodes = new Map()
  for (const row of rows || []) {
    nodes.set(row.name, {
      name: row.name,
      label: cardIdentity(row, spec).label,
      row,
      orphan: false,
      // Whether this record may hold others. Frappe's nested-set doctypes say
      // so with `is_group`; a doctype nesting through a plain Link may have no
      // such field, and then every node is a group.
      group: !groupField || !!Number(row[groupField] || 0),
      children: [],
    })
  }

  const roots = []
  for (const row of rows || []) {
    const node = nodes.get(row.name)
    const above = nodes.get(row[field])
    if (!above || above === node || reaches(above, node, nodes, field)) {
      // Only a record that *names* a parent is an orphan.
      node.orphan = !!row[field]
      roots.push(node)
      continue
    }
    above.children.push(node)
  }
  return roots
}

/**
 * Whether walking up from `above` arrives at `node` — a circle in the data.
 *
 * Nothing stops two records naming each other: the doctype only refuses a
 * record that renews *itself*. Attaching one under the other would build a
 * cycle the component recurses through, so the pair are both left as roots.
 */
function reaches(above, node, nodes, field) {
  const seen = new Set()
  let walking = above
  while (walking && !seen.has(walking.name)) {
    if (walking === node) return true
    seen.add(walking.name)
    walking = nodes.get(walking.row[field])
  }
  return false
}
