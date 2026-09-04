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
