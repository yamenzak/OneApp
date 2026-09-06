/**
 * Earlier drafts of a file's body — a workbook's or a document's.
 *
 * One family for both, because a version of a sheet and a version of a
 * document are the same row: a blob, its file, when, who, and whether somebody
 * named it. `kind` is the only thing that differs, and it is a parameter
 * rather than two copies of this file. See `oneapp_core/versions.py`.
 *
 * `offsetMinutes` is the reader's own clock. The grouping — today, yesterday,
 * this week — is decided on the server against the reader's midnight, so a
 * panel left open across midnight does not silently regroup itself under the
 * cursor.
 */

import { callMethod } from '@/lib/runtime/resource'

const OFFSET = () => -new Date().getTimezoneOffset()

export const versions = {
  fileHistory: (file, kind) =>
    callMethod('oneapp.oneapp_core.versions.history',
      { file, kind, offset_minutes: OFFSET() },
      { silent: true, method: 'GET' }),

  fileVersionBody: (version, kind) =>
    callMethod('oneapp.oneapp_core.versions.version_body', { version, kind }, {
      silent: true, method: 'GET',
    }),

  fileKeepVersion: (file, kind, title) =>
    callMethod('oneapp.oneapp_core.versions.save_version', { file, kind, title }, {
      success: 'Version saved',
    }),

  fileRestoreVersion: (version, kind) =>
    callMethod('oneapp.oneapp_core.versions.restore_version', { version, kind }, {
      success: 'Restored',
    }),

  fileNameVersion: (version, kind, title) =>
    callMethod('oneapp.oneapp_core.versions.name_version', { version, kind, title }, {
      success: 'Renamed',
    }),

  fileForgetVersion: (version, kind) =>
    callMethod('oneapp.oneapp_core.versions.forget_version', { version, kind }, {
      success: 'Version removed',
    }),
}
