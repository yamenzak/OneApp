// The rows hanging off one record, as a page draws them.
//
// The fetch is the workspace's; what is worth pinning is the shaping, which is
// where a card gets its label, its face and the one line under it — and which
// two record views now share rather than each carrying a copy.
import { describe, expect, it } from 'vitest'

import { shapeChildren } from '@/modules/onespace/lib/screen/related'

// `cell` and not `fieldtype`: `cellText` switches on what the *engine* called
// the cell, which `_columns` derives once so every surface reads the same word.
const COLUMNS = [
  { fieldname: 'employee_name', label: 'Name', cell: 'text' },
  { fieldname: 'designation', label: 'Designation', cell: 'link' },
]

const SPEC = { title_field: 'employee_name', image_field: 'image' }

describe('shapeChildren', () => {
  it('reads the title, the face and the first column that is not either', () => {
    const [one] = shapeChildren(
      [{ name: 'HR-EMP-1', employee_name: 'Leila Amari', designation: 'Architect', image: '/x.png' }],
      COLUMNS,
      SPEC,
      {},
    )
    expect(one).toEqual({
      name: 'HR-EMP-1',
      label: 'Leila Amari',
      image: '/x.png',
      detail: 'Architect',
    })
  })

  it('says the id where the title field is empty', () => {
    // A record with no title is still a record, and a card with no words on it
    // is a card nobody can click on purpose.
    const [one] = shapeChildren([{ name: 'HR-EMP-2' }], COLUMNS, SPEC, {})
    expect(one.label).toBe('HR-EMP-2')
  })

  it('prefers what a Link is called over what it is keyed by', () => {
    // The same `_links` map every list cell reads. Without it a detail line
    // said HR-EMP-00002 where the list beside it said the person's name.
    const [one] = shapeChildren(
      [{
        name: 'HR-EMP-3',
        employee_name: 'Omar Fadel',
        designation: 'DESIG-004',
        // `_link_row`'s shape, which is what the server puts in `_links`.
        _links: { designation: { value: 'DESIG-004', label: 'Site engineer' } },
      }],
      COLUMNS,
      SPEC,
      {},
    )
    expect(one.detail).toBe('Site engineer')
  })

  it('draws no face where the doctype has none', () => {
    const [one] = shapeChildren(
      [{ name: 'T-1', employee_name: 'Sam' }],
      COLUMNS,
      { title_field: 'employee_name' },
      {},
    )
    expect(one.image).toBe('')
  })

  it('skips the activity column when picking the detail', () => {
    // `__activity` is a row's meta rather than a field of the record, and a
    // card captioned with two glyphs says nothing at all.
    const [one] = shapeChildren(
      [{ name: 'T-2', employee_name: 'Sam', designation: 'Architect' }],
      [COLUMNS[0], { fieldname: '__activity', label: '', cell: 'text' }, COLUMNS[1]],
      SPEC,
      {},
    )
    expect(one.detail).toBe('Architect')
  })

  it('is empty for nothing, rather than throwing', () => {
    expect(shapeChildren(null, null, null, {})).toEqual([])
  })
})
