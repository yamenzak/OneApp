/** What surrounds a record — its timeline, people, files, tags and state. */

import { callMethod } from '../resource'

export const record = {
  // Comments and the change log. Frappe keeps both on every doctype, so no app
  // has to ask for them.
  timeline: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.timeline',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  comment: (spaceCode, screen, name, content) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.comment',
      { space_code: spaceCode, screen, name, content },
      { successMessage: 'Added' },
    ),

  // Who a record is assigned to, and who it could be.
  //
  // Frappe's own model: `_assign` is a list of user ids on the document and a
  // ToDo sits beside each one, so assigning is how a record reaches somebody's
  // own list rather than only somebody's avatar. Both halves are the server's
  // — this sends a set of people and reads back what the document ended up
  // holding.

  // Who a record is assigned to, and who it could be.
  //
  // Frappe's own model: `_assign` is a list of user ids on the document and a
  // ToDo sits beside each one, so assigning is how a record reaches somebody's
  // own list rather than only somebody's avatar. Both halves are the server's
  // — this sends a set of people and reads back what the document ended up
  // holding.
  assignees: (spaceCode, screen, query) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.assignees',
      { space_code: spaceCode, screen, query },
      { silent: true, method: 'GET' },
    ),

  assign: (spaceCode, screen, name, users) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.assign',
      { space_code: spaceCode, screen, name, users },
      { silent: true },
    ),

  toggleLike: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.toggle_like',
      { space_code: spaceCode, screen, name },
      { silent: true },
    ),

  // The numbers behind a screen's dashboard. Its own call rather than part of
  // the spec: a spec is read on every navigation and this is one aggregate
  // query per widget.

  tags: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.tags',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  tagOptions: (spaceCode, screen, name, query = '') =>
    callMethod(
      'oneapp.oneapp_core.spaceview.tag_options',
      { space_code: spaceCode, screen, name, query },
      { silent: true, method: 'GET' },
    ),

  // Silent: the badge appearing is the confirmation, and a toast for every
  // tag is a toast for something nobody was unsure about.

  // Silent: the badge appearing is the confirmation, and a toast for every
  // tag is a toast for something nobody was unsure about.
  setTag: (spaceCode, screen, name, tag, on) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.set_tag',
      { space_code: spaceCode, screen, name, tag, on: on ? 1 : 0 },
      { silent: true },
    ),

  shares: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.shares',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  shareable: (spaceCode, screen, query = '') =>
    callMethod(
      'oneapp.oneapp_core.spaceview.shareable',
      { space_code: spaceCode, screen, query },
      { silent: true, method: 'GET' },
    ),

  // Not silent, either way. Handing somebody access to a record — or taking it
  // back — is the kind of change you want told you happened.

  // Not silent, either way. Handing somebody access to a record — or taking it
  // back — is the kind of change you want told you happened.
  setShare: (spaceCode, screen, name, { user = null, everyone = 0, level = 'read' }) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.set_share',
      { space_code: spaceCode, screen, name, user, everyone, level },
      { successMessage: 'Shared' },
    ),

  unshare: (spaceCode, screen, name, { user = null, everyone = 0 }) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.unshare',
      { space_code: spaceCode, screen, name, user, everyone },
      { successMessage: 'Stopped sharing' },
    ),

  // Give a record a different id. Not silent: a rename is the one edit that
  // changes what everything else points at, and it deserves saying so.

  // Give a record a different id. Not silent: a rename is the one edit that
  // changes what everything else points at, and it deserves saying so.
  rename: (spaceCode, screen, name, newName) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.rename',
      { space_code: spaceCode, screen, name, new_name: newName },
      { successMessage: 'Renamed' },
    ),

  // Follow this record, or stop. Not silent: unlike a like, nothing on the
  // screen changes to prove it worked — the whole result is a notification
  // that has not happened yet — so the toast is the confirmation.

  // Follow this record, or stop. Not silent: unlike a like, nothing on the
  // screen changes to prove it worked — the whole result is a notification
  // that has not happened yet — so the toast is the confirmation.
  toggleFollow: (spaceCode, screen, name) =>
    callMethod('oneapp.oneapp_core.spaceview.toggle_follow', {
      space_code: spaceCode,
      screen,
      name,
    }),

  // What is filed against a record. Frappe's own File rows, so a file uploaded
  // through an Attach field and a file dropped on the record are one list.
  // `fieldname` narrows the list to one Attachment Gallery's share of them,
  // by the `link_filters` on that docfield. The filter is read off the field
  // server-side rather than sent from here, so this only names which field is
  // asking.

  // What is filed against a record. Frappe's own File rows, so a file uploaded
  // through an Attach field and a file dropped on the record are one list.
  // `fieldname` narrows the list to one Attachment Gallery's share of them,
  // by the `link_filters` on that docfield. The filter is read off the field
  // server-side rather than sent from here, so this only names which field is
  // asking.
  attachments: (spaceCode, screen, name, fieldname) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.attachments',
      { space_code: spaceCode, screen, name, fieldname },
      { silent: true, method: 'GET' },
    ),

  removeAttachment: (spaceCode, screen, name, file) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.remove_attachment',
      { space_code: spaceCode, screen, name, file },
      { successMessage: 'File removed' },
    ),

  // A layout: the filters, the sort and the columns saved together under a
  // name, the way Frappe's own List Filter doctype models it. `layout` updates
  // one, `label` makes a new one, neither writes this person's unnamed default
  // — the Save button on the toolbar.
  //
  // Narrows what the screen offers; never widens it, shared or not.

  submit: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.submit',
      { space_code: spaceCode, screen, name },
      { successMessage: 'Submitted' },
    ),

  cancel: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.cancel',
      { space_code: spaceCode, screen, name },
      { successMessage: 'Cancelled' },
    ),

  amend: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.amend',
      { space_code: spaceCode, screen, name },
      { successMessage: 'Amended' },
    ),

  workflowAction: (spaceCode, screen, name, action) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.workflow_action',
      { space_code: spaceCode, screen, name, action },
      { successMessage: 'Done' },
    ),

  // --- the mail about a record --------------------------------------------
  //
  // Correspondence is a `Communication` linked to the document, and the link is
  // made by `oneapp_core/email/linking.py` — inherited down a thread, or found
  // as an id this site issues written in the subject or body. What comes back
  // is what *this reader* may already see, never everything linked: a link is
  // not a grant, or filing a message against a project would publish it to
  // everybody who can open the project.
  recordMail: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.correspondence',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  // Sending from a record is the one path where the filing needs no working
  // out at all — the person was looking at the record when they wrote it.
  recordMailSend: (spaceCode, screen, name, values) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.write',
      { space_code: spaceCode, screen, name, ...values },
      { successMessage: 'Sent' },
    ),

  // The way out of every case the automatic filing did not get, and the way
  // back from every one it got wrong.
  recordMailAttach: (spaceCode, screen, name, message) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.attach',
      { space_code: spaceCode, screen, name, message },
      { successMessage: 'Filed here' },
    ),

  recordMailDetach: (spaceCode, screen, name, message) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.detach',
      { space_code: spaceCode, screen, name, message },
      { successMessage: 'Unfiled' },
    ),

  // --- print formats and letter heads -------------------------------------
  //
  // What is drawn on the page, as against the paper it comes out on — the
  // paper is a settings group and lives in `SettingsFields`. A drawn format is
  // a Frappe beta Print Format: our builder writes `format_data` and Frappe's
  // own generator renders it, so the same format prints identically wherever
  // it is opened. See `oneapp_core/printing.py`.
}
