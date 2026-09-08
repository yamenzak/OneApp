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
