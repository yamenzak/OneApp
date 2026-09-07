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
import { assistant } from './assistant'
import { settings } from './settings'
import { screen } from './screen'
import { record } from './record'
import { drive } from './drive'
import { diary } from './diary'
import { layouts } from './layouts'
import { mail } from './mail'
import { printing } from './printing'
import { sheets } from './sheets'
import { docs } from './docs'
import { versions } from './versions'
import { account } from './account'

export const workspace = {
  ...assistant,
  ...settings,
  ...screen,
  ...record,
  ...drive,
  ...diary,
  ...layouts,
  ...mail,
  ...printing,
  ...sheets,
  ...docs,
  ...versions,
  ...account,
}
