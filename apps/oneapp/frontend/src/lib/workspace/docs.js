/**
 * Documents: the prose a `File` could not hold.
 *
 * A document's identity is a File row, so everything about *the file* —
 * rename, move, share, trash, the expiring link — goes through `drive.js` and
 * none of it is repeated here. What is here is the prose: loading it, saving
 * it, and the two plain-text calls beside it. See `oneapp_core/docs`.
 *
 * Two blobs go up on every save and only one is authoritative. `content` is
 * the ProseMirror JSON the editor reads back; `html` is what it rendered, and
 * it is what search, the preview and every export read. The editor has both in
 * hand at the moment it saves, and asking Python to derive the second from the
 * first would mean a ProseMirror implementation in Python.
 */

import { callMethod } from '@/lib/runtime/resource'

export const docs = {
  docMake: (params) =>
    callMethod('oneapp.oneapp_core.docs.make', params, {
      success: 'Document created',
    }),

  docMakeText: (params) =>
    callMethod('oneapp.oneapp_core.docs.make_text', params, {
      success: 'File created',
    }),

  docOpen: (name) =>
    callMethod('oneapp.oneapp_core.docs.get_doc', { name }, {
      silent: true, method: 'GET',
    }),

  // Silent: this runs every few seconds while somebody types, and a toast per
  // save is a toast every few seconds. The header says whether it landed.
  docSave: (name, params) =>
    callMethod('oneapp.oneapp_core.docs.save_doc', { name, ...params }, {
      silent: true,
    }),

  docDuplicate: (name, title) =>
    callMethod('oneapp.oneapp_core.docs.duplicate', { name, title }, {
      success: 'Copied',
    }),

  docMarkdown: (name) =>
    callMethod('oneapp.oneapp_core.docs.as_markdown', { name }, {
      silent: true, method: 'GET',
    }),

  // The plain-text pair. A `.md` in the Drive is a real object, so these read
  // and write the file itself rather than a body row beside it.
  textOpen: (name) =>
    callMethod('oneapp.oneapp_core.docs.get_text', { name }, {
      silent: true, method: 'GET',
    }),

  textSave: (name, params) =>
    callMethod('oneapp.oneapp_core.docs.save_text', { name, ...params }, {
      silent: true,
    }),
}
