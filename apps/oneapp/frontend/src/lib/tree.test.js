// Turning a flat page of records into the forest a tree draws.
//
// Two of these are cases a browser cannot easily be made to show and that both
// end as a blank screen or a hung tab: a record whose parent is on the next
// page, and two records that name each other.
import { describe, expect, it } from 'vitest'

import { forestOf } from './tree'

const SPEC = { title_field: 'title' }

/** A page of records, in the order the server sent them. */
const page = (...rows) =>
  rows.map(([name, title, renews]) => ({ name, title, renews: renews || null }))

const labels = (nodes) => nodes.map((node) => node.label)

describe('forestOf', () => {
  it('nests a record under the one it points at', () => {
    const forest = forestOf(
      page(
        ['CD-1', 'Trade Licence — 2024'],
        ['CD-2', 'Trade Licence', 'CD-1'],
        ['CD-3', 'Trade Licence — 2027', 'CD-2'],
        ['CD-4', 'Memorandum of Association'],
      ),
      'renews',
      SPEC,
    )

    expect(labels(forest)).toEqual(['Trade Licence — 2024', 'Memorandum of Association'])
    expect(labels(forest[0].children)).toEqual(['Trade Licence'])
    expect(labels(forest[0].children[0].children)).toEqual(['Trade Licence — 2027'])
    // A root is a record that names no parent, and it is not an orphan.
    expect(forest.map((node) => node.orphan)).toEqual([false, false])
  })

  it('keeps the page order at every level', () => {
    const forest = forestOf(
      page(
        ['CD-1', 'Alpha'],
        ['CD-2', 'Zulu', 'CD-1'],
        ['CD-3', 'Bravo', 'CD-1'],
      ),
      'renews',
      SPEC,
    )
    // Not sorted: a tree is still the screen's rows in the screen's order.
    expect(labels(forest[0].children)).toEqual(['Zulu', 'Bravo'])
  })

  it('draws a record whose parent is not on the page as a root, and says so', () => {
    const forest = forestOf(
      page(['CD-2', 'Trade Licence', 'CD-1'], ['CD-4', 'Memorandum of Association']),
      'renews',
      SPEC,
    )
    // Never dropped: the parent may have been filtered out or may be on a page
    // nobody has loaded, and hiding the record for either reason would make the
    // tree disagree with the count in the footer.
    expect(labels(forest)).toEqual(['Trade Licence', 'Memorandum of Association'])
    expect(forest.map((node) => node.orphan)).toEqual([true, false])
  })

  it('leaves a circle as roots rather than recursing through it', () => {
    const forest = forestOf(
      page(['CD-1', 'One', 'CD-2'], ['CD-2', 'Two', 'CD-1'], ['CD-3', 'Three']),
      'renews',
      SPEC,
    )
    // Two records naming each other is data the doctype permits — it only
    // refuses a record that renews itself — and the only drawing of a circle
    // that terminates is both of them at the top.
    expect(labels(forest)).toEqual(['One', 'Two', 'Three'])
    expect(forest[0].children).toEqual([])
  })

  it('treats a record that points at itself as a root', () => {
    const forest = forestOf(page(['CD-1', 'One', 'CD-1']), 'renews', SPEC)
    expect(labels(forest)).toEqual(['One'])
    expect(forest[0].children).toEqual([])
  })

  it('is nothing at all without a field to nest by', () => {
    expect(forestOf(page(['CD-1', 'One']), '', SPEC)).toEqual([])
    expect(forestOf(null, 'renews', SPEC)).toEqual([])
  })

  it('names a node the way every other surface names a record', () => {
    // The doctype's own title field, through `cardIdentity`, so a tree and a
    // card do not disagree about what a record is called.
    const [node] = forestOf(page(['CD-1', 'Trade Licence']), 'renews', SPEC)
    expect(node.label).toBe('Trade Licence')
    expect(node.name).toBe('CD-1')

    const [byId] = forestOf(page(['CD-1', 'Trade Licence']), 'renews', {})
    expect(byId.label).toBe('CD-1')
  })
})
