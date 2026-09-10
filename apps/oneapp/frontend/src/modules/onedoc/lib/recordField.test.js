/**
 * The token, as the editor holds it.
 *
 * Two claims worth a test and neither is about rendering. Patching must be a
 * transaction rather than a reload, because the person is typing and their
 * cursor is somewhere in the sentence. And a field that did not come back must
 * keep what it had, because a partial resolve — one field behind a permlevel
 * somebody lacks — should show nine numbers and one stale one rather than
 * nine numbers and a hole.
 */

import { describe, expect, it, vi } from 'vitest'
import { PENDING, RECORD_FIELD, applyRecordFields, namedFields } from './recordField'

/**
 * A ProseMirror document, thin. Only what these two functions touch:
 * `descendants` over the nodes, and a transaction that records the markups
 * it was asked for.
 */
function editorWith(nodes) {
  const marked = []
  const tr = {
    setNodeMarkup: (pos, _type, attrs) => marked.push({ pos, attrs }),
    setMeta: vi.fn(),
  }
  return {
    marked,
    tr,
    dispatched: [],
    state: {
      tr,
      doc: {
        descendants: (visit) =>
          nodes.forEach((node, at) =>
            visit({ type: { name: node.type || RECORD_FIELD }, attrs: node }, at),
          ),
      },
    },
    view: { dispatch(one) { this.sent = one } },
  }
}

describe('applyRecordFields', () => {
  it('sets the text of every token whose field came back', () => {
    const editor = editorWith([
      { field: 'grand_total', text: PENDING },
      { field: 'party_name', text: PENDING },
    ])
    const changed = applyRecordFields(editor, {
      grand_total: 'AED 144,235.00',
      party_name: 'Halloway',
    })
    expect(changed).toBe(2)
    expect(editor.marked.map((one) => one.attrs.text)).toEqual([
      'AED 144,235.00',
      'Halloway',
    ])
  })

  it('leaves a token whose field did not come back', () => {
    const editor = editorWith([
      { field: 'grand_total', text: PENDING },
      { field: 'margin', text: '12%' },
    ])
    applyRecordFields(editor, { grand_total: 'AED 1.00' })
    expect(editor.marked).toHaveLength(1)
    expect(editor.marked[0].attrs.field).toBe('grand_total')
  })

  it('does nothing when nothing moved', () => {
    const editor = editorWith([{ field: 'grand_total', text: 'AED 1.00' }])
    expect(applyRecordFields(editor, { grand_total: 'AED 1.00' })).toBe(0)
    expect(editor.marked).toHaveLength(0)
  })

  it('keeps the patch out of the undo stack', () => {
    // Nothing a person did produced it. Undo should step back over the
    // sentence they typed, not over the record answering.
    const editor = editorWith([{ field: 'grand_total', text: PENDING }])
    applyRecordFields(editor, { grand_total: 'AED 1.00' })
    expect(editor.tr.setMeta).toHaveBeenCalledWith('addToHistory', false)
  })

  it('ignores an editor that is not there yet', () => {
    expect(applyRecordFields(null, { grand_total: '1' })).toBe(0)
  })
})

describe('namedFields', () => {
  it('names each field once, in the order the prose names them', () => {
    const editor = editorWith([
      { field: 'grand_total' },
      { field: 'party_name' },
      { field: 'grand_total' },
    ])
    expect(namedFields(editor)).toEqual(['grand_total', 'party_name'])
  })

  it('skips everything that is not a token', () => {
    const editor = editorWith([
      { type: 'text', field: '' },
      { field: 'grand_total' },
    ])
    expect(namedFields(editor)).toEqual(['grand_total'])
  })
})
