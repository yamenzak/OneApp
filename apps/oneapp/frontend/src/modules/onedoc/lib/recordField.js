/**
 * A field of the bound record, as a node in the prose.
 *
 * A covering letter is prose with the quotation's numbers in it. Typed out,
 * those numbers are a second copy that goes stale — so this is a node that is
 * not text but a *name*, and the text it shows is whatever the record says
 * when the document is read. See `oneapp/onedoc/fields.py` for the other half
 * and for what freezing one means.
 *
 * An atom: it has no editable content of its own. Putting the cursor inside
 * `AED 144,235.00` and deleting a comma would produce a number the record
 * never said, which is exactly the failure the node exists to prevent. So it
 * selects and deletes whole, the way a mention chip does.
 *
 * The last answer is stored in the node's own `text` attribute and written
 * into the markup, rather than being fetched on render. Three readers depend
 * on that: the export, which is one HTML file with no app behind it; a mail
 * client; and this editor before the resolve comes back. An empty span that
 * JavaScript fills is a document that reads as broken everywhere but here.
 */

import { Node, mergeAttributes } from '@tiptap/core'

export const RECORD_FIELD = 'recordField'
export const RECORD_TABLE = 'recordTable'

//: `quotation.grand_total`. One string, because it keys the flat answer the
//: server sends and a flat answer is what a patch reads without walking a
//: tree. The empty source means the file's first record — see
//: `shared/binding.py`.
export const at = (source, field) => `${source || 'record'}.${field}`

//: What a token shows when nothing has resolved it yet — an em dash rather
//: than the fieldname, because a reader seeing `grand_total` in a letter
//: reads it as a bug and a reader seeing `—` reads it as a blank.
export const PENDING = '—'

export const RecordField = Node.create({
  name: RECORD_FIELD,
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,

  addAttributes() {
    return {
      // Which of the document's records this is a field of. A document may
      // read several — the quotation, its customer, the project — and two of
      // them can offer a field of the same name.
      source: {
        default: '',
        parseHTML: (el) => el.getAttribute('data-record-source') || '',
        renderHTML: (attrs) =>
          attrs.source ? { 'data-record-source': attrs.source } : {},
      },
      // The fieldname on that record's doctype. With the source, the whole of
      // what is stored: everything else about this node is a cache.
      field: {
        default: '',
        parseHTML: (el) => el.getAttribute('data-record-field') || '',
        renderHTML: (attrs) => ({ 'data-record-field': attrs.field || '' }),
      },
      // What the field is called, for the chip's tooltip and for the moment
      // the record is unreachable — "Total" is a better hole than nothing.
      label: {
        default: '',
        parseHTML: (el) => el.getAttribute('data-record-label') || '',
        renderHTML: (attrs) =>
          attrs.label ? { 'data-record-label': attrs.label } : {},
      },
      // The last answer. Not an attribute in the markup — it is the node's
      // text content — which is why `renderHTML` puts it in the span's body
      // and `parseHTML` reads it back off `textContent`.
      text: { default: PENDING, renderHTML: () => ({}) },
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-record-field]',
        getAttrs: (el) => ({
          source: el.getAttribute('data-record-source') || '',
          field: el.getAttribute('data-record-field') || '',
          label: el.getAttribute('data-record-label') || '',
          text: el.textContent || PENDING,
        }),
      },
    ]
  },

  renderHTML({ HTMLAttributes, node }) {
    return [
      'span',
      // Utilities rather than a class of our own: every class in either SPA
      // has to emit CSS, and a bespoke name would need a stylesheet nobody
      // else reads. A quiet chip — this is part of the sentence, not a
      // control, so it must not shout.
      mergeAttributes(HTMLAttributes, {
        class: 'rounded-4 bg-surface-gray-2 px-1 text-ink-primary',
      }),
      node.attrs.text || PENDING,
    ]
  },

  renderText({ node }) {
    return node.attrs.text || PENDING
  },

  addCommands() {
    return {
      insertRecordField:
        ({ source = '', field, label = '', text = PENDING }) =>
        ({ commands }) =>
          commands.insertContent({
            type: RECORD_FIELD,
            attrs: { source, field, label, text },
          }),
    }
  },
})

/**
 * Put the current answers into a document's tokens, in place.
 *
 * A ProseMirror transaction rather than a reload: the person may be typing,
 * and replacing the document under them would move their cursor to the top
 * and lose the sentence they are in the middle of. `setNodeMarkup` on each
 * token leaves everything else exactly where it was.
 *
 * `said` is `{fieldname: text}` — `onedoc/fields.py`'s answer. A token whose
 * field is not in it keeps what it had, which is what makes a partial resolve
 * (one field behind a permlevel somebody lacks) show nine numbers and one
 * stale one rather than nine numbers and a hole.
 */
export function applyRecordFields(editor, said) {
  if (!editor || !said || !Object.keys(said).length) return 0

  const { state } = editor
  const changes = []
  state.doc.descendants((node, pos) => {
    if (node.type.name !== RECORD_FIELD) return
    const now = said[at(node.attrs.source, node.attrs.field)]
    if (now === undefined || now === node.attrs.text) return
    changes.push({ pos, attrs: { ...node.attrs, text: now } })
  })
  if (!changes.length) return 0

  const tr = state.tr
  for (const one of changes) tr.setNodeMarkup(one.pos, undefined, one.attrs)
  // Not undoable, and not a change the save loop should count: nothing a
  // person did produced it, and an autosave fired by the record answering
  // would rewrite the document every time somebody else edited the record.
  tr.setMeta('addToHistory', false)
  tr.setMeta('recordFields', true)
  editor.view.dispatch(tr)
  return changes.length
}

/**
 * Everything the document names, in the shape the server resolves.
 *
 * `{fields, tables}`, matching `onedoc/fields.py::named` — read off the live
 * editor rather than off the saved body, because the save is debounced and a
 * token inserted a second ago is only here.
 */
export function namedFields(editor) {
  const fields = []
  const tables = []
  const seen = new Set()
  editor?.state?.doc?.descendants((node) => {
    const kind = node.type.name
    if (kind !== RECORD_FIELD && kind !== RECORD_TABLE) return
    const source = node.attrs.source || ''
    const what = kind === RECORD_FIELD ? node.attrs.field : node.attrs.table
    if (!what || seen.has(`${kind}:${source}.${what}`)) return
    seen.add(`${kind}:${source}.${what}`)
    if (kind === RECORD_FIELD) fields.push({ source, field: what })
    else tables.push({ source, table: what, columns: node.attrs.columns || [] })
  })
  return { fields, tables }
}

/**
 * A child table of one of the records, as a block in the prose.
 *
 * The other shape a record can take in a document, and it is not a token: a
 * quotation's lines are a table, and a table is not a phrase in a sentence.
 * So a block node rather than an inline one, and an atom for the same reason
 * the token is — the rows belong to the record, and a cursor inside them
 * would let somebody edit a number the record never said.
 *
 * `columns` is the only part of what is drawn that is stored. The heads and
 * the rows are a cache and the server empties both on every read — see
 * `fields.sanitise` — because a column's label is as much the record's as its
 * cells are.
 */
export const RecordTable = Node.create({
  name: RECORD_TABLE,
  group: 'block',
  atom: true,
  selectable: true,
  draggable: true,

  addAttributes() {
    return {
      source: {
        default: '',
        parseHTML: (el) => el.getAttribute('data-record-source') || '',
        renderHTML: (attrs) =>
          attrs.source ? { 'data-record-source': attrs.source } : {},
      },
      // The child table's fieldname on the source's doctype.
      table: {
        default: '',
        parseHTML: (el) => el.getAttribute('data-record-table') || '',
        renderHTML: (attrs) => ({ 'data-record-table': attrs.table || '' }),
      },
      label: {
        default: '',
        parseHTML: (el) => el.getAttribute('data-record-label') || '',
        renderHTML: (attrs) =>
          attrs.label ? { 'data-record-label': attrs.label } : {},
      },
      // Which of the child doctype's columns, and in what order. Stored,
      // because it is a decision the person writing made.
      columns: {
        default: [],
        parseHTML: (el) => {
          try {
            return JSON.parse(el.getAttribute('data-record-columns') || '[]')
          } catch {
            return []
          }
        },
        renderHTML: (attrs) => ({
          'data-record-columns': JSON.stringify(attrs.columns || []),
        }),
      },
      // The cache. Written into the markup as a real `<table>` rather than as
      // attributes, because the export is one HTML file with no app behind it
      // and a mail client cannot draw a block from JSON.
      heads: { default: [], renderHTML: () => ({}) },
      rows: { default: [], renderHTML: () => ({}) },
    }
  },

  parseHTML() {
    return [{ tag: 'div[data-record-table]' }]
  },

  renderHTML({ HTMLAttributes, node }) {
    const heads = node.attrs.heads || []
    const rows = node.attrs.rows || []
    const wrap = mergeAttributes(HTMLAttributes, { class: 'my-3 overflow-x-auto' })

    // Nothing read yet, or nothing to read. A visible box rather than an
    // empty one, so the block can be seen, selected and deleted.
    if (!heads.length && !rows.length) {
      return [
        'div',
        wrap,
        [
          'div',
          { class: 'rounded-6 border border-outline-gray-2 px-3 py-2 text-ink-muted' },
          node.attrs.label || node.attrs.table || PENDING,
        ],
      ]
    }

    return [
      'div',
      wrap,
      [
        'table',
        { class: 'w-full' },
        ['thead', {}, ['tr', {}, ...heads.map((one) => ['th', {}, one])]],
        [
          'tbody',
          {},
          ...rows.map((row) => ['tr', {}, ...row.map((cell) => ['td', {}, cell || ''])]),
        ],
      ],
    ]
  },

  renderText({ node }) {
    return (node.attrs.rows || []).map((row) => row.join('\t')).join('\n')
  },

  addCommands() {
    return {
      insertRecordTable:
        ({ source = '', table, label = '', columns = [] }) =>
        ({ commands }) =>
          commands.insertContent({
            type: RECORD_TABLE,
            attrs: { source, table, label, columns, heads: [], rows: [] },
          }),
    }
  },
})

/**
 * Put the current rows into a document's blocks, in place.
 *
 * `applyRecordFields`'s other half, and the same transaction discipline: not
 * undoable, not a change the save loop should count. `drawn` is keyed the
 * same way — `source.table` — and holds `{columns, rows}`, which is what
 * `binding.rows` answers.
 */
export function applyRecordTables(editor, drawn) {
  if (!editor || !drawn || !Object.keys(drawn).length) return 0

  const { state } = editor
  const changes = []
  state.doc.descendants((node, pos) => {
    if (node.type.name !== RECORD_TABLE) return
    const now = drawn[at(node.attrs.source, node.attrs.table)]
    if (!now) return
    const heads = (now.columns || []).map((one) => one.label || one.fieldname)
    const rows = now.rows || []
    if (same(node.attrs.heads, heads) && same(node.attrs.rows, rows)) return
    changes.push({ pos, attrs: { ...node.attrs, heads, rows } })
  })
  if (!changes.length) return 0

  const tr = state.tr
  for (const one of changes) tr.setNodeMarkup(one.pos, undefined, one.attrs)
  tr.setMeta('addToHistory', false)
  tr.setMeta('recordFields', true)
  editor.view.dispatch(tr)
  return changes.length
}

//: Whether two of these are the same, cheaply. Rows of strings, so stringify
//: is exact — and skipping an unchanged block matters: patching one is a
//: transaction, and a transaction on every refresh is a repaginate on every
//: refresh.
const same = (a, b) => JSON.stringify(a || []) === JSON.stringify(b || [])
