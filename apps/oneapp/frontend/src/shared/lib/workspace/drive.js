/**
 * Files: one place for everything the workspace stores.
 *
 * Every one of these is over Frappe's own `File` table — the same rows an
 * attachment already is — so the Drive and a record's Files tab are two queries
 * rather than two stores. See `onestorage`.
 */

import { callMethod } from '@/shared/lib/runtime/resource'
import { __ } from '@/shared/lib/runtime/translate'

export const drive = {
  // A place is a filter: home, recents, favourites, shared, trash.
  driveList: (params) =>
    callMethod('oneapp.onestorage.listing', params, {
      silent: true, method: 'GET',
    }),

  // Opening a file is what makes it recent, so this is a read with a write in
  // it — deliberately, and on the details rather than the preview, because the
  // preview is a redirect and there is no request to hang it on.
  driveFile: (name) =>
    callMethod('oneapp.onestorage.details', { name }, {
      silent: true, method: 'GET',
    }),

  driveStorage: () =>
    callMethod('oneapp.onestorage.storage', {}, {
      silent: true, method: 'GET',
    }),

  // Attach a file that already exists to a record. A second row pointing at
  // the same object, not a move — see `drive/writing.attach`.
  driveAttach: (file, { doctype, docname, fieldname } = {}) =>
    callMethod(
      'oneapp.onestorage.attach',
      { file, doctype, docname, fieldname: fieldname || '' },
      { successMessage: __('Attached') },
    ),

  // A link somebody without an account can follow, until a date. The one thing
  // `DocShare` cannot do — see `drive/sharing`.
  driveMakeLink: (file, days) =>
    callMethod('oneapp.onestorage.make_link', { file, days }),

  driveLinks: (file) =>
    callMethod('oneapp.onestorage.links', { file }, {
      silent: true, method: 'GET',
    }),

  driveRevokeLink: (name) =>
    callMethod('oneapp.onestorage.revoke', { name }, {
      successMessage: __('That link no longer works'),
    }),

  // Who this file has been given to inside the workspace. `DocShare`, the same
  // rows the record surface writes — there is nothing of ours in it.
  drivePeople: (file) =>
    callMethod('oneapp.onestorage.people', { file }, {
      silent: true, method: 'GET',
    }),

  // Who a file can be shared with: the workspace, asked without a screen —
  // a file is not on a space, so there is no screen to bound it by.
  driveColleagues: (query = '') =>
    callMethod('oneapp.onestorage.colleagues', { query }, {
      silent: true, method: 'GET',
    }),

  driveShare: (file, { user, everyone, level } = {}) =>
    callMethod(
      'oneapp.onestorage.share_with',
      { file, user: user || '', everyone: everyone ? 1 : 0, level: level || 'read' },
      { successMessage: __('Shared') },
    ),

  driveUnshare: (file, { user, everyone } = {}) =>
    callMethod(
      'oneapp.onestorage.unshare_with',
      { file, user: user || '', everyone: everyone ? 1 : 0 },
      { successMessage: __('Share removed') },
    ),

  // `_liked_by`, which is why Favourites is a filter and not a table.
  driveFavourite: (name, on) =>
    callMethod(
      'oneapp.onestorage.set_favourite',
      { name, on: on ? 1 : 0 },
      { silent: true },
    ),

  driveNewFolder: (fileName, folder) =>
    callMethod(
      'oneapp.onestorage.make_folder',
      { file_name: fileName, folder },
      { successMessage: __('Folder made') },
    ),

  driveRename: (name, fileName) =>
    callMethod(
      'oneapp.onestorage.rename',
      { name, file_name: fileName },
      { successMessage: __('Renamed') },
    ),

  driveMove: (names, folder) =>
    callMethod(
      'oneapp.onestorage.move',
      { names: JSON.stringify(names), folder },
      { successMessage: __('Moved') },
    ),

  // Reversible. The object survives until the sweep decides it has been thirty
  // days, which is the whole reason this is not a delete.
  driveTrash: (names) =>
    callMethod(
      'oneapp.onestorage.trash',
      { names: JSON.stringify(names) },
      { successMessage: __('Moved to the bin') },
    ),

  driveRestore: (names) =>
    callMethod(
      'oneapp.onestorage.restore',
      { names: JSON.stringify(names) },
      { successMessage: __('Restored') },
    ),

  // The one that does not come back, which is why it lives on its own screen.
  driveEmptyTrash: (names) =>
    callMethod(
      'oneapp.onestorage.empty_trash',
      { names: JSON.stringify(names || []) },
      { successMessage: __('Deleted for good') },
    ),
}
