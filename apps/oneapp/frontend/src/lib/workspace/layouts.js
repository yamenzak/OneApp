/** Saved views: reading them, writing them, hiding them. */

import { callMethod } from '../resource'

export const layouts = {
  // Every named layout in a space, keyed by screen. The sidebar's question:
  // it lists what each screen can be looked at as before anybody has opened
  // one, and asking a spec per screen to draw a menu is a request per item.
  spaceLayouts: (spaceCode) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.space_layouts',
      { space_code: spaceCode },
      { silent: true, method: 'GET' },
    ),

  // A few facts about the record a link points at, for a card on hover. Which
  // facts is the target doctype's own answer — its `in_preview` fields — so no
  // manifest chooses them and every screen pointing at that doctype agrees.

  // A layout: the filters, the sort and the columns saved together under a
  // name, the way Frappe's own List Filter doctype models it. `layout` updates
  // one, `label` makes a new one, neither writes this person's unnamed default
  // — the Save button on the toolbar.
  //
  // Narrows what the screen offers; never widens it, shared or not.
  saveLayout: (spaceCode, screen, payload) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.save_layout',
      { space_code: spaceCode, screen, ...payload },
      { successMessage: 'View saved' },
    ),

  deleteLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.delete_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: 'View deleted' },
    ),

  // Not a delete. A shared view belongs to the workspace and somebody else may
  // be living in it — this says only that one reader would rather not see it.

  // Not a delete. A shared view belongs to the workspace and somebody else may
  // be living in it — this says only that one reader would rather not see it.
  hideLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.hide_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: 'Hidden from your menu' },
    ),

  showLayouts: (spaceCode, screen) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.show_layouts',
      { space_code: spaceCode, screen },
      { successMessage: 'Hidden views are back' },
    ),

  defaultLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.default_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: 'This opens the screen now' },
    ),

  // The view type goes with it: a screen has one unnamed default per way of
  // looking at it, and "undo my tinkering" on the board is not a decision about
  // the list.

  // The view type goes with it: a screen has one unnamed default per way of
  // looking at it, and "undo my tinkering" on the board is not a decision about
  // the list.
  resetLayout: (spaceCode, screen, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.reset_layout',
      { space_code: spaceCode, screen, view_type: viewType || undefined },
      { successMessage: 'Back to the default screen' },
    ),
}
