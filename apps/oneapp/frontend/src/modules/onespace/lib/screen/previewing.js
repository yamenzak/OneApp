/**
 * Whether the record being drawn is a preview rather than the thing you are
 * working on.
 *
 * A window over a record is a *look* at something that record points at. It is
 * reached by pressing a Link field's first button, and what a person wants
 * there is to read the address, check the status, see the face — then either go
 * back to what they were doing or go and work on it properly. Nothing in
 * between.
 *
 * Letting it be a full record instead asked three questions with no good
 * answers. A Link field inside a window offers to open *its* target, so a peek
 * peeks: windows over windows, each one a different record, none of them the
 * one the page is about. Document actions inside a window submit and cancel a
 * document the reader opened to glance at. And unsaved edits in a window are
 * unsaved edits in something that closes when you click past it.
 *
 * So the rule, and it is one sentence: **a window holds something you consult
 * or pick from, never something you work in.** The record it holds is read
 * only — no editable fields, no pipeline band, no verbs, nothing to save — and
 * carries exactly one control that leads anywhere, which is the door out to the
 * record's own screen, where all of it works.
 *
 * `provide`/`inject` rather than a prop, for the reason `LEAVING` beside this
 * file is injected: the component that knows it is in a window is `RecordView`,
 * and the control that has to stand down is a button inside a Link field four
 * components below it, past three that would only be carrying the prop along.
 */

/** The injection key. A Symbol, so nothing collides with it by accident. */
export const PREVIEWING = Symbol('onespace.previewing')
