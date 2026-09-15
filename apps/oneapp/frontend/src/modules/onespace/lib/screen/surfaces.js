/**
 * Where an open record goes, which is no longer a question.
 *
 * There were three answers and a preference between two of them:
 *
 *   pane    a resizable column beside the list, the desktop default
 *   page    the whole content area, for a screen declaring a showcase
 *   drawer  an overlay, for a record reached *from* another record
 *
 * A record is a page now — `docs/DESKTOP.md`, the second decision. The pane was
 * the right answer while a record was a form, and it is the wrong one now that
 * a record is a *place*: a person with a face and a photograph, a day of
 * attendance drawn as a day, an opening drawn as a funnel. Every one of those
 * had to survive 480 pixels, and the honest choices were pixel-perfect
 * responsiveness for every bespoke page forever or one width. One width.
 *
 * What the pane was actually for — mark this one done, glance at the next, come
 * back — is the breadcrumb's job now: `lib/desk/pip.js`. And the drawer's job,
 * a record you are reading *from* another one, is a window: `usePeek`.
 *
 * So what is left here is two names and a target. The file stays because
 * `RecordView` still has to be told which of the two it is drawn on, and
 * because a constant shared by three components is better here than agreed by
 * coincidence in each of them.
 */

/** The whole content area: what an open record is, everywhere, always. */
export const PAGE = 'page'

/** A window over it: a record reached from the one you are reading. */
export const WINDOW = 'window'

/**
 * Where a record's controls go, which is never a bar of their own.
 *
 * As a page, the trail above is already naming the record, so they teleport
 * onto that line. In a window, the window's own title bar is doing the same
 * job, so they go there. Either way a band drawn under a line that already
 * says what this is would be a second row for two buttons.
 *
 * Named here rather than written twice, because an id that agrees by
 * coincidence agrees until somebody renames one of them.
 */
export const MERGE_TARGET = 'record-controls-on-the-trail'
export const WINDOW_TARGET = 'record-controls-in-the-window'
