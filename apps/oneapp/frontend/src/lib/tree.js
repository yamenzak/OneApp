import { cardIdentity } from './cards'

/**
 * A flat page of records, as the forest a tree draws.
 *
 * Separate from `TreeBody` because it is the only part of that view with a
 * decision in it. The component owns disclosure and indentation — frappe-ui's
 * `Tree` owns those, in fact — and this owns the two questions a hierarchy
 * built out of a *page* has to answer: what happens to a record whose parent is
 * not here, and what happens when the data points in a circle.
 *
 * A record this cannot draw under its parent becomes a root, marked `orphan`.
 * Dropping it would be the alternative and it is never the better one: the
 * parent may be missing because a filter excluded it or because it is on a page
 * nobody has loaded yet, and a tree that silently hides a record for either
 * reason is a tree that disagrees with the count in the footer. Load more
 * re-nests it when the parent arrives.
 *
 * Order is the page's, at every level. A tree is still a screen's rows in the
 * screen's order — nesting them is not a reason to sort them again.
 */
export function forestOf(rows, field, spec) {
  if (!field) return []

  const nodes = new Map()
  for (const row of rows || []) {
    nodes.set(row.name, {
      name: row.name,
      label: cardIdentity(row, spec).label,
      row,
      orphan: false,
      children: [],
    })
  }

  const roots = []
  for (const row of rows || []) {
    const node = nodes.get(row.name)
    const above = nodes.get(row[field])
    if (!above || above === node || reaches(above, node, nodes, field)) {
      // Only a record that *names* a parent is an orphan. One that names none
      // is a root, which is what a root is.
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
 * Nothing stops two records naming each other: `renews` is an ordinary Link and
 * the doctype only refuses a record that renews *itself*. Attaching one under
 * the other here would build a cycle in the node graph, and the component
 * recurses through it. So the pair are both left as roots, which is the only
 * drawing of a circle that terminates.
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
