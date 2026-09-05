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
import { settings } from './settings'
import { screen } from './screen'
import { record } from './record'
import { drive } from './drive'
import { diary } from './diary'
import { layouts } from './layouts'
import { mail } from './mail'
import { importing } from './importing'
import { printing } from './printing'
import { sheets } from './sheets'

export const workspace = {
  ...settings,
  ...screen,
  ...record,
  ...drive,
  ...diary,
  ...layouts,
  ...mail,
  ...importing,
  ...printing,
  ...sheets,
}
