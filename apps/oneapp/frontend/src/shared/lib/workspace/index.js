/**
 * Workspace settings: the parts of Frappe a customer owns.
 *
 * The field list is not written here. The server owns the spec — which setting
 * exists, what type it is, and which of Frappe's singles it writes — because
 * that same object is the allowlist the write path checks against. A copy in
 * the SPA would be a second list to keep in step, and the one that drifts is
 * always the one that decides what is rendered.
 */


// One object, assembled from the modules, because every caller says
// `workspace.screenRows(...)` and the split is ours rather than theirs.
import { assistant } from '@/shared/lib/workspace/assistant'
import { settings } from '@/shared/lib/workspace/settings'
import { screen } from '@/shared/lib/workspace/screen'
import { record } from '@/shared/lib/workspace/record'
import { drive } from '@/shared/lib/workspace/drive'
import { diary } from '@/shared/lib/workspace/diary'
import { layouts } from '@/shared/lib/workspace/layouts'
import { mail } from '@/shared/lib/workspace/mail'
import { legal } from '@/shared/lib/workspace/legal'
import { printing } from '@/shared/lib/workspace/printing'
import { sheets } from '@/shared/lib/workspace/sheets'
import { docs } from '@/shared/lib/workspace/docs'
import { versions } from '@/shared/lib/workspace/versions'
import { account } from '@/shared/lib/workspace/account'

export const workspace = {
  ...assistant,
  ...settings,
  ...screen,
  ...record,
  ...drive,
  ...diary,
  ...layouts,
  ...mail,
  ...legal,
  ...printing,
  ...sheets,
  ...docs,
  ...versions,
  ...account,
}
