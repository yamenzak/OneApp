/**
 * Version history, over the one version module both editors read.
 *
 * The panel, the preview banner and the restore flow are Frappe's, vendored
 * with the editor (`lib/sheets/VENDORED.md`). This is the half that was not
 * ported, and it is small because `shared/versions.py` answers the same
 * questions for a workbook and a document alike — a version is a blob, its
 * file, when, who, and whether somebody named it.
 *
 * Two of Frappe's calls stay empty and will. `cellHistory` and `cellDiff` read
 * their op log, which exists because their save is incremental; ours is total,
 * so there is no sequence of operations to walk and nothing to replay. The
 * editor already treats the highlighting they feed as optional — "highlighting
 * optional" is its own comment — so an empty answer degrades to a preview
 * without the changed cells outlined, which is what it degrades to upstream
 * when the log has been truncated.
 */

import { callMethod } from '@/lib/runtime/resource'

export const AVAILABLE = true

const KIND = 'Sheet'

const OFFSET = () => -new Date().getTimezoneOffset()

/** Their row shape, from ours. The panel groups and labels off these five. */
const asVersion = (one) => ({
  name: one.name,
  // A named version has a name; an automatic one has a timestamp for a title,
  // and the panel's "named only" filter is exactly this field being set.
  version_name: one.manual ? one.title : '',
  timestamp: one.at,
  user: one.by,
  collapsed_count: one.saves || 1,
})

export async function list(sheet) {
  const answer = await callMethod(
    'oneapp.shared.versions.history',
    { file: sheet, kind: KIND, offset_minutes: OFFSET() },
    { silent: true, method: 'GET' },
  )
  // The panel does its own grouping by date, so the groups are flattened back
  // out here rather than asking the server not to make them: a document's
  // panel wants them, and one endpoint serving both is worth one `flatMap`.
  return (answer?.groups || []).flatMap((group) => group.versions).map(asVersion)
}

export async function getState(sheet, version) {
  const answer = await callMethod(
    'oneapp.shared.versions.version_body',
    { version, kind: KIND },
    { silent: true, method: 'GET' },
  )
  return { sheets_data: answer?.payload || '{}', title: '' }
}

export async function restore(sheet, version) {
  return callMethod('oneapp.shared.versions.restore_version',
    { version, kind: KIND }, { success: 'Restored' })
}

export async function name(sheet, version, title) {
  return callMethod('oneapp.shared.versions.name_version',
    { version, kind: KIND, title }, { success: 'Named' })
}

export async function clearName(sheet, version) {
  // The same endpoint with nothing in it: a name and its absence are one
  // field, and an empty one puts the version back among the automatic ones.
  return callMethod('oneapp.shared.versions.name_version',
    { version, kind: KIND, title: '' }, { silent: true })
}

export async function saveVersion(sheet, title = '') {
  return callMethod('oneapp.shared.versions.save_version',
    { file: sheet, kind: KIND, title }, { success: 'Version saved' })
}

export async function makeACopy(sheet, version, title) {
  const made = await callMethod('oneapp.shared.versions.copy_version',
    { version, kind: KIND, title }, { success: 'Copied' })
  return made?.name || null
}

export async function latestVersion(sheet) {
  const rows = await list(sheet)
  return rows[0] || null
}

export async function cellHistory() { return [] }
export async function cellDiff() { return null }

/**
 * Upstream this posts one entry to the op log. Our save is total — the browser
 * hands back the whole workbook — so there is no operation to record, and a
 * caller that awaited a sequence number gets none, which is the truth.
 */
export function recordOp() { return Promise.resolve(null) }
