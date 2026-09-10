/**
 * Documents: the prose a `File` could not hold.
 *
 * A document's identity is a File row, so everything about *the file* —
 * rename, move, share, trash, the expiring link — goes through `drive.js` and
 * none of it is repeated here. What is here is the prose: loading it, saving
 * it, and the two plain-text calls beside it. See `onedoc`.
 *
 * Two blobs go up on every save and only one is authoritative. `content` is
 * the ProseMirror JSON the editor reads back; `html` is what it rendered, and
 * it is what search, the preview and every export read. The editor has both in
 * hand at the moment it saves, and asking Python to derive the second from the
 * first would mean a ProseMirror implementation in Python.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

export const docs = {
  docMake: (params) =>
    callMethod('oneapp.onedoc.make', params, {
      success: 'Document created',
    }),

  docMakeText: (params) =>
    callMethod('oneapp.onedoc.make_text', params, {
      success: 'File created',
    }),

  docOpen: (name) =>
    callMethod('oneapp.onedoc.get_doc', { name }, {
      silent: true, method: 'GET',
    }),

  // Silent: this runs every few seconds while somebody types, and a toast per
  // save is a toast every few seconds. The header says whether it landed.
  docSave: (name, params) =>
    callMethod('oneapp.onedoc.save_doc', { name, ...params }, {
      silent: true,
    }),

  // A template is a document with a flag on it, the same way a sheet template
  // is — `onedoc/templates.py` says why one shape rather than two.
  docTemplates: () =>
    callMethod('oneapp.onedoc.listing', {}, { silent: true, method: 'GET' }),

  docSetTemplate: (name, on) =>
    callMethod('oneapp.onedoc.set_template', { doc: name, on: on ? 1 : 0 }),

  docDuplicate: (name, title) =>
    callMethod('oneapp.onedoc.duplicate', { name, title }, {
      success: 'Copied',
    }),

  // The whole printable page as one string, for the frame that prints it —
  // `lib/paper/print.js` says why the app's own window is the wrong printer.
  docPrintable: (name) =>
    callMethod('oneapp.onedoc.printable', { name }, {
      silent: true, method: 'GET',
    }),

  docMarkdown: (name) =>
    callMethod('oneapp.onedoc.as_markdown', { name }, {
      silent: true, method: 'GET',
    }),

  // --- the record a document is written about ------------------------------
  // A field of that record, inside the prose: what the token says now, and
  // the moment it stops asking. See `modules/onedoc/lib/recordField.js`.

  // Ask the record again. Its own call rather than part of opening the
  // document, because the whole point is asking a second time — it has been
  // open for an hour and somebody wants to know whether the total moved.
  // `asked` is the field list the editor has on screen. Without it the
  // server reads the saved body, which is a debounce behind: a token
  // inserted a second ago would show an em dash until the next save.
  docFields: (name, asked) =>
    callMethod('oneapp.onedoc.refresh', {
      name,
      asked: asked?.fields?.length || asked?.tables?.length
        ? JSON.stringify(asked)
        : undefined,
    }, { silent: true, method: 'GET' }),

  // Freeze every token, permanently. What a document about to be sent gets:
  // a quotation the customer received is a fact about a day, not a view onto
  // a record that has moved on since.
  docSettleFields: (name) =>
    callMethod('oneapp.onedoc.settle', { name }, { success: 'Fields fixed' }),

  // Which record, for the dialog a bound template opens with. The server's
  // own search, so what somebody is offered is what they could have opened.
  bindableRecords: (doctype, query) =>
    callMethod('oneapp.shared.binding.records', { doctype, query }, {
      silent: true, method: 'GET',
    }),

  // What that doctype will answer — `{fields, tables}`, which is what the
  // sidebar draws. Narrowed on the server to what this person may read; see
  // `shared/binding.py`.
  bindableFields: (doctype) =>
    callMethod('oneapp.shared.binding.fields', { doctype }, {
      silent: true, method: 'GET',
    }),

  // Which kinds of record there are to choose from. Searched rather than
  // listed: the readable set on a full site is several hundred doctypes.
  bindableKinds: (query) =>
    callMethod('oneapp.shared.binding.kinds', { query }, {
      silent: true, method: 'GET',
    }),

  // What one record says now — `{fields: {name: {value, text}}}`. For a
  // caller with no file to key an ask by, which today means the mail
  // composer: a draft is held in the browser until it is sent, so there is
  // no `Bound Record` row and nothing for `sheetRecordFields` to hang off.
  // The permission is the record's either way — see `binding.resolve`.
  bindableValues: (doctype, name, fields) =>
    callMethod(
      'oneapp.shared.binding.resolve',
      { doctype, name, wanted: JSON.stringify(fields || []) },
      { silent: true, method: 'GET' },
    ),

  // And one child table of it — `{columns, rows, values}`. The same call the
  // document's blocks and the workbook's `RECORDROW()` grid are drawn from.
  bindableRows: (doctype, name, table, columns) =>
    callMethod(
      'oneapp.shared.binding.rows',
      { doctype, name, table, columns: JSON.stringify(columns || []) },
      { silent: true, method: 'GET' },
    ),

  // --- the set of records a file reads -------------------------------------
  // A `Bound Record` row each, keyed, so a token names `key.field` and the
  // record behind the key can be swapped without touching the prose.

  fileSources: (file) =>
    callMethod('oneapp.shared.binding.file_sources', { file }, {
      silent: true, method: 'GET',
    }),

  // `name` empty declares a slot — a template saying "a quotation goes here".
  addSource: (file, doctype, name, label) =>
    callMethod('oneapp.shared.binding.add_source',
      { file, doctype, name, label }, { silent: true }),

  // Fill a slot, or point a source at a different record. The key does not
  // move, so every token that named it keeps working.
  setSource: (file, key, name) =>
    callMethod('oneapp.shared.binding.set_source', { file, key, name }, {
      silent: true,
    }),

  dropSource: (file, key) =>
    callMethod('oneapp.shared.binding.drop_source', { file, key }, {
      silent: true,
    }),

  // The plain-text pair. A `.md` in the Drive is a real object, so these read
  // and write the file itself rather than a body row beside it.
  textOpen: (name) =>
    callMethod('oneapp.onedoc.get_text', { name }, {
      silent: true, method: 'GET',
    }),

  textSave: (name, params) =>
    callMethod('oneapp.onedoc.save_text', { name, ...params }, {
      silent: true,
    }),
}
