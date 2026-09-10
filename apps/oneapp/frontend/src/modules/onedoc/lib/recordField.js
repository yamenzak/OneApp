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
      // The fieldname on the bound doctype. The whole of what is stored:
      // everything else about this node is a cache of what it last said.
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
        class: 'rounded-4 bg-surface-gray-2 px-1 text-ink-gray-8',
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
        ({ field, label = '', text = PENDING }) =>
        ({ commands }) =>
          commands.insertContent({
            type: RECORD_FIELD,
            attrs: { field, label, text },
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
    const now = said[node.attrs.field]
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

/** Every fieldname the document names, for the resolve request. */
export function namedFields(editor) {
  const found = []
  editor?.state?.doc?.descendants((node) => {
    if (node.type.name !== RECORD_FIELD) return
    const field = node.attrs.field
    if (field && !found.includes(field)) found.push(field)
  })
  return found
}
