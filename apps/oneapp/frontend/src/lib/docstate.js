/**
 * Where a record stands, as one badge.
 *
 * `_state` rides on a record whose doctype is submittable or governed by a
 * workflow, and it already holds both answers — the workflow's own state and
 * its style, or the framework's word for the docstatus. This turns whichever
 * of those applies into the two things a badge needs.
 *
 * It belongs beside the record's name rather than out among the buttons, which
 * is where it used to be: "where does this stand" is the second thing anybody
 * asks about a record, and the trail is where they already look for the answer
 * on every screen that has a status field. One place, whether the answer comes
 * from a Select the manifest named, a workflow, or the docstatus.
 */
export function docBadge(state, statusField = '') {
  if (!state) return null

  const flow = state.workflow
  if (flow) {
    // The screen already badges this field beside the name. Saying it twice in
    // two places is how a header starts to read as a debug view.
    if (!flow.state || flow.state_field === statusField) return null
    return { label: flow.state, theme: flow.theme || '' }
  }

  // No workflow, so the docstatus is the whole answer — and only on a doctype
  // that has one. A doctype that is not submittable has every record at
  // docstatus 0, and a badge reading "Draft" on a note is noise.
  if (!state.submittable || !state.status) return null
  return { label: state.status, theme: '' }
}
