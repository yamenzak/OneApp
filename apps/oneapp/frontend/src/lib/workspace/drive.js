/**
 * Files: one place for everything the workspace stores.
 *
 * Every one of these is over Frappe's own `File` table — the same rows an
 * attachment already is — so the Drive and a record's Files tab are two queries
 * rather than two stores. See `oneapp_core/drive`.
 */

import { callMethod } from '../resource'

export const drive = {
  // A place is a filter: home, recents, favourites, shared, trash.
  driveList: (params) =>
    callMethod('oneapp.oneapp_core.drive.listing', params, {
      silent: true, method: 'GET',
    }),

  // Opening a file is what makes it recent, so this is a read with a write in
  // it — deliberately, and on the details rather than the preview, because the
  // preview is a redirect and there is no request to hang it on.
  driveFile: (name) =>
    callMethod('oneapp.oneapp_core.drive.details', { name }, {
      silent: true, method: 'GET',
    }),

  driveStorage: () =>
    callMethod('oneapp.oneapp_core.drive.storage', {}, {
      silent: true, method: 'GET',
    }),

  // Attach a file that already exists to a record. A second row pointing at
  // the same object, not a move — see `drive/writing.attach`.
  driveAttach: (file, { doctype, docname, fieldname } = {}) =>
    callMethod(
      'oneapp.oneapp_core.drive.attach',
      { file, doctype, docname, fieldname: fieldname || '' },
      { successMessage: 'Attached' },
    ),

  // A link somebody without an account can follow, until a date. The one thing
  // `DocShare` cannot do — see `drive/sharing`.
  driveMakeLink: (file, days) =>
    callMethod('oneapp.oneapp_core.drive.make_link', { file, days }),

  driveLinks: (file) =>
    callMethod('oneapp.oneapp_core.drive.links', { file }, {
      silent: true, method: 'GET',
    }),

  driveRevokeLink: (name) =>
    callMethod('oneapp.oneapp_core.drive.revoke', { name }, {
      successMessage: 'That link no longer works',
    }),

  driveNewFolder: (fileName, folder) =>
    callMethod(
      'oneapp.oneapp_core.drive.make_folder',
      { file_name: fileName, folder },
      { successMessage: 'Folder made' },
    ),

  driveRename: (name, fileName) =>
    callMethod(
      'oneapp.oneapp_core.drive.rename',
      { name, file_name: fileName },
      { successMessage: 'Renamed' },
    ),

  driveMove: (names, folder) =>
    callMethod(
      'oneapp.oneapp_core.drive.move',
      { names: JSON.stringify(names), folder },
      { successMessage: 'Moved' },
    ),

  // Reversible. The object survives until the sweep decides it has been thirty
  // days, which is the whole reason this is not a delete.
  driveTrash: (names) =>
    callMethod(
      'oneapp.oneapp_core.drive.trash',
      { names: JSON.stringify(names) },
      { successMessage: 'Moved to the bin' },
    ),

  driveRestore: (names) =>
    callMethod(
      'oneapp.oneapp_core.drive.restore',
      { names: JSON.stringify(names) },
      { successMessage: 'Restored' },
    ),

  // The one that does not come back, which is why it lives on its own screen.
  driveEmptyTrash: (names) =>
    callMethod(
      'oneapp.oneapp_core.drive.empty_trash',
      { names: JSON.stringify(names || []) },
      { successMessage: 'Deleted for good' },
    ),
}
