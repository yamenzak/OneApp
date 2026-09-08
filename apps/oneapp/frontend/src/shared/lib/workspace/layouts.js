/** Saved views: reading them, writing them, hiding them. */

import { callMethod } from '@/shared/lib/runtime/resource'
import { __ } from '@/shared/lib/runtime/translate'

export const layouts = {
  // Every named layout in a space, keyed by screen. The sidebar's question:
  // it lists what each screen can be looked at as before anybody has opened
  // one, and asking a spec per screen to draw a menu is a request per item.
  spaceLayouts: (spaceCode) =>
    callMethod(
      'oneapp.onespace.spaceview.space_layouts',
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
      'oneapp.onespace.spaceview.save_layout',
      { space_code: spaceCode, screen, ...payload },
      { successMessage: __('View saved') },
    ),

  deleteLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.onespace.spaceview.delete_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: __('View deleted') },
    ),

  // Not a delete. A shared view belongs to the workspace and somebody else may
  // be living in it — this says only that one reader would rather not see it.
  hideLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.onespace.spaceview.hide_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: __('Hidden from your menu') },
    ),

  showLayouts: (spaceCode, screen) =>
    callMethod(
      'oneapp.onespace.spaceview.show_layouts',
      { space_code: spaceCode, screen },
      { successMessage: __('Hidden views are back') },
    ),

  defaultLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.onespace.spaceview.default_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: __('This opens the screen now') },
    ),

  // The view type goes with it: a screen has one unnamed default per way of
  // looking at it, and "undo my tinkering" on the board is not a decision about
  // the list.
  resetLayout: (spaceCode, screen, viewType) =>
    callMethod(
      'oneapp.onespace.spaceview.reset_layout',
      { space_code: spaceCode, screen, view_type: viewType || undefined },
      { successMessage: __('Back to the default screen') },
    ),
}
