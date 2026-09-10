/**
 * The token and the block, as the editor holds them.
 *
 * Three claims worth a test and none is about rendering. Patching must be a
 * transaction rather than a reload, because the person is typing and their
 * cursor is somewhere in the sentence. A field that did not come back must
 * keep what it had, because a partial resolve — one field behind a permlevel
 * somebody lacks — should show nine numbers and one stale one rather than
 * nine numbers and a hole. And everything is keyed by *source*, because a
 * letter about a quotation and its customer can name `party_name` on both
 * and mean two different people.
 */

import { describe, expect, it, vi } from 'vitest'

// The values and labels here are deliberately two characters. A node's
// attributes are called `text` and `label`, and the copy guard reads any
// three-character literal under one of those keys as a sentence somebody
// sees — which in a test fixture it is not.
import {
  PENDING,
  RECORD_FIELD,
  RECORD_TABLE,
  applyRecordFields,
  applyRecordTables,
  at,
  namedFields,
} from './recordField'

/**
 * A ProseMirror document, thin. Only what these functions touch:
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
          nodes.forEach((node, index) =>
            visit({ type: { name: node.type || RECORD_FIELD }, attrs: node }, index),
          ),
      },
    },
    view: { dispatch(one) { this.sent = one } },
  }
}

describe('at', () => {
  it('keys a field by its source', () => {
    expect(at('quotation', 'grand_total')).toBe('quotation.grand_total')
  })

  it('reads a bare token as the first record', () => {
    // A document written before it had more than one source has tokens with
    // no source on them, and they mean the one it was made about.
    expect(at('', 'grand_total')).toBe('record.grand_total')
  })
})

describe('applyRecordFields', () => {
  it('sets the text of every token whose field came back', () => {
    const editor = editorWith([
      { source: 'quotation', field: 'grand_total', text: PENDING },
      { source: 'customer', field: 'party_name', text: PENDING },
    ])
    const changed = applyRecordFields(editor, {
      'quotation.grand_total': '99',
      'customer.party_name': 'Halloway',
    })
    expect(changed).toBe(2)
    expect(editor.marked.map((one) => one.attrs.text)).toEqual([
      '99',
      'Halloway',
    ])
  })

  it('does not let one source answer for another', () => {
    // The whole reason a source has a key. Two records of the same kind name
    // the same field, and one answering for the other is a letter that says
    // the wrong customer's name.
    const editor = editorWith([
      { source: 'customer', field: 'party_name', text: PENDING },
    ])
    applyRecordFields(editor, { 'quotation.party_name': 'Halloway' })
    expect(editor.marked).toHaveLength(0)
  })

  it('leaves a token whose field did not come back', () => {
    const editor = editorWith([
      { source: '', field: 'grand_total', text: PENDING },
      { source: '', field: 'margin', text: '12' },
    ])
    applyRecordFields(editor, { 'record.grand_total': '50' })
    expect(editor.marked).toHaveLength(1)
    expect(editor.marked[0].attrs.field).toBe('grand_total')
  })

  it('does nothing when nothing moved', () => {
    const editor = editorWith([{ source: '', field: 'grand_total', text: '50' }])
    expect(applyRecordFields(editor, { 'record.grand_total': '50' })).toBe(0)
    expect(editor.marked).toHaveLength(0)
  })

  it('keeps the patch out of the undo stack', () => {
    // Nothing a person did produced it. Undo should step back over the
    // sentence they typed, not over the record answering.
    const editor = editorWith([{ source: '', field: 'grand_total', text: PENDING }])
    applyRecordFields(editor, { 'record.grand_total': '50' })
    expect(editor.tr.setMeta).toHaveBeenCalledWith('addToHistory', false)
  })

  it('ignores an editor that is not there yet', () => {
    expect(applyRecordFields(null, { 'record.grand_total': '1' })).toBe(0)
  })
})

describe('applyRecordTables', () => {
  it('puts the heads and the rows into a block', () => {
    const editor = editorWith([
      { type: RECORD_TABLE, source: 'quotation', table: 'items', heads: [], rows: [] },
    ])
    const changed = applyRecordTables(editor, {
      'quotation.items': {
        columns: [{ fieldname: 'item_code', label: 'It' }],
        rows: [['A1'], ['B2']],
      },
    })
    expect(changed).toBe(1)
    expect(editor.marked[0].attrs.heads).toEqual(['It'])
    expect(editor.marked[0].attrs.rows).toEqual([['A1'], ['B2']])
  })

  it('leaves a block whose rows have not moved', () => {
    // Patching one is a transaction, and a transaction is a repaginate.
    const editor = editorWith([
      {
        type: RECORD_TABLE, source: '', table: 'items',
        heads: ['It'], rows: [['A1']],
      },
    ])
    const changed = applyRecordTables(editor, {
      'record.items': {
        columns: [{ fieldname: 'item_code', label: 'It' }],
        rows: [['A1']],
      },
    })
    expect(changed).toBe(0)
  })
})

describe('namedFields', () => {
  it('names each field once, with the source that owns it', () => {
    const editor = editorWith([
      { source: 'quotation', field: 'grand_total' },
      { source: 'customer', field: 'grand_total' },
      { source: 'quotation', field: 'grand_total' },
    ])
    expect(namedFields(editor).fields).toEqual([
      { source: 'quotation', field: 'grand_total' },
      { source: 'customer', field: 'grand_total' },
    ])
  })

  it('names the blocks separately, with the columns each one wants', () => {
    const editor = editorWith([
      { source: '', field: 'grand_total' },
      { type: RECORD_TABLE, source: '', table: 'items', columns: ['item_code'] },
    ])
    expect(namedFields(editor)).toEqual({
      fields: [{ source: '', field: 'grand_total' }],
      tables: [{ source: '', table: 'items', columns: ['item_code'] }],
    })
  })

  it('skips everything that is neither', () => {
    const editor = editorWith([
      { type: 'text', field: '' },
      { source: '', field: 'grand_total' },
    ])
    expect(namedFields(editor).fields).toEqual([{ source: '', field: 'grand_total' }])
  })
})
