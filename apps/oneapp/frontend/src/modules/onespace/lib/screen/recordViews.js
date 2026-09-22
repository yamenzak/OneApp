import { defineAsyncComponent } from 'vue'

/**
 * The ways a screen can draw *one* record.
 *
 * `viewTypes.js` is this table for a page of records; this is the same idea one
 * level down. A record has more than one right shape — a form with tabs, a hero
 * over a form, a page built for what the record actually is — and which one a
 * screen uses is a name in the manifest rather than a fork of `RecordView`:
 *
 *     "view_settings": {"record": {"as": "person"}}
 *
 * Not `surfaces.js`, which is the other question about an open record — pane,
 * page or drawer, meaning *how much of the window*. This one is what is drawn
 * inside whichever of those it got.
 *
 * Two rules keep the library from becoming a pile of pages. There were four
 * and eight entries; OneHR owned all eight bespoke ones and took them, and its
 * shared shell — `RecordPage`, `RecordHead`, `RecordTally` — left with them,
 * along with the two rules that were only about how a band is built.
 *
 * **A record view owns layout.** `RecordView` keeps the header, the controls,
 * the save loop, the tab strip and the form; a record view is handed the
 * record, the spec and the space, and decides what is on the screen and in what
 * order. It may *read* the workspace but only through the engine's own
 * endpoints, which keeps the space, the permissions and the filters checked
 * where every other list checks them. It never saves and never decides a
 * permission. That is what stops a bespoke page becoming a second
 * implementation of the record, the way the Drive once became a second
 * implementation of a list (`docs/UNIFICATION.md` F1).
 *
 * **Every one of these stands above the tab strip.** One that replaced the form
 * outright was built first and taken out again: it put the fields above the
 * strip, which is the wrong order, and it had one speculative user. Rail 10 —
 * an abstraction with a single caller is the thing this repository keeps
 * getting wrong, and writing one for a caller that does not exist yet is the
 * same mistake earlier.
 *
 * **A name means the same thing in both halves.** `onespace/recordviews.py` has
 * this table too, and `tests/test_record_views.py` holds them to each other — a
 * name here and not there is a screen that draws nothing.
 *
 * `built: false` is allowed and is how a manifest names one before it ships:
 * the server falls back to `record`, so the screen keeps the page it had and
 * gets the new one the day it exists.
 */
export const RECORD_VIEWS = {
  record: {
    built: true,
    /** The default, and the only one that is not a component: `RecordView`'s
     *  own form and tabs, drawn when nothing else is named. */
    body: null,
  },
  showcase: {
    built: true,
    body: () => import('@/modules/onespace/components/screen/record/RecordShowcase.vue'),
  },
}

/** What a screen gets when it names nothing, or names something unbuilt. */
export const DEFAULT_RECORD_VIEW = 'record'

/**
 * Which one this screen draws a record with.
 *
 * Off the resolved spec, which the server has already narrowed to a built name
 * — so this is a read rather than a second decision, for the same reason
 * `viewTypesOf` and `_view_types` are the same rule twice: two halves that
 * decide separately drift, and the drift shows up as a page that is one thing
 * in the rail and another when opened.
 */
export function recordViewOf(spec) {
  const name = spec?.view_settings?.record?.as
  return RECORD_VIEWS[name]?.built ? name : DEFAULT_RECORD_VIEW
}

/**
 * The component that draws it, or null for `record` — which is `RecordView`'s
 * own body and not a component it mounts.
 */
export function recordBodyFor(name) {
  const found = RECORD_VIEWS[name]
  return found?.body ? defineAsyncComponent(found.body) : null
}
