/**
 * The diary: everything with a date on it, merged.
 *
 * One request per range rather than one per source — the merge is the server's,
 * because it is the same permission path the screens themselves use and a
 * browser fanning out over five screens would be five round trips and five
 * chances to disagree. See `oneapp_core/diary.py`.
 */

import { callMethod } from '../resource'

export const diary = {
  // `since` and `until` are the days on screen. A diary is not a page: it
  // fetches the range it is showing, the way the screen calendar does.
  agenda: (since, until) =>
    callMethod('oneapp.oneapp_core.diary.agenda', { since, until }, {
      silent: true, method: 'GET',
    }),

  // The reader's own events, which are the one thing this surface stores. The
  // gate is ownership rather than the workspace's doctype grants — see
  // `diary._mine`.
  diaryEvent: (name) =>
    callMethod('oneapp.oneapp_core.diary.event', { name }, { silent: true, method: 'GET' }),

  saveDiaryEvent: (values) =>
    callMethod('oneapp.oneapp_core.diary.save_event', { values: JSON.stringify(values) }),

  removeDiaryEvent: (name) =>
    callMethod('oneapp.oneapp_core.diary.remove_event', { name }),
}
