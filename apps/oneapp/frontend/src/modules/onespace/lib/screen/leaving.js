/**
 * What an unsaved surface stands to lose, offered to the controls inside it.
 *
 * A Link field carries two doors: read the target beside this, or go and work
 * on it. The first costs nothing. The second is navigation, and navigation out
 * of a half-filled create dialog throws the half away — which the dialog knows
 * and the picker, four components below it, does not.
 *
 * So the surface says so. `provide`/`inject` rather than a prop through
 * RecordForm, FormSections and FieldControl, none of which would use it: the
 * same reason `RETURN_TO` beside this file is injected.
 *
 * The contract is two things:
 *
 *   `losing`  a computed naming what would be lost — "this new Task" — or the
 *             empty string when nothing would be. Controls read it to say out
 *             loud what they are about to do.
 *   `leave()` close the surface, discarding. Called by a control that is
 *             navigating away on purpose, so the dialog does not stay on top
 *             of the screen it was left for.
 *
 * Only the create dialog provides one today. A record pane with unsaved edits
 * is the obvious second and is not one yet: its edits are per-field and it has
 * no discard of its own to call.
 */

/** The injection key. A Symbol, so nothing collides with it by accident. */
export const LEAVING = Symbol('onespace.leaving')
