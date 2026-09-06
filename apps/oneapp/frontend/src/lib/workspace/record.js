/** What surrounds a record — its timeline, people, files, tags and state. */

import { callMethod } from '@/lib/runtime/resource'
import { __ } from '@/lib/runtime/translate'

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
      { successMessage: __('Added') },
    ),

  // Who a record is assigned to, and who it could be. Frappe's own model:
  // `_assign` is a list of user ids on the document and a ToDo sits beside each
  // one, so assigning is how a record reaches somebody's own list.
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
  // the spec, which is read on every navigation.

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

  // Silent: the badge appearing is the confirmation.
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
  // back — is a change you want told you happened.
  setShare: (spaceCode, screen, name, { user = null, everyone = 0, level = 'read' }) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.set_share',
      { space_code: spaceCode, screen, name, user, everyone, level },
      { successMessage: __('Shared') },
    ),

  unshare: (spaceCode, screen, name, { user = null, everyone = 0 }) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.unshare',
      { space_code: spaceCode, screen, name, user, everyone },
      { successMessage: __('Stopped sharing') },
    ),

  // Give a record a different id. Not silent: a rename is the one edit that
  // changes what everything else points at.
  rename: (spaceCode, screen, name, newName) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.rename',
      { space_code: spaceCode, screen, name, new_name: newName },
      { successMessage: __('Renamed') },
    ),

  // Follow this record, or stop. Not silent: nothing on the screen changes to
  // prove it worked, so the toast is the confirmation.
  toggleFollow: (spaceCode, screen, name) =>
    callMethod('oneapp.oneapp_core.spaceview.toggle_follow', {
      space_code: spaceCode,
      screen,
      name,
    }),

  // What is filed against a record — Frappe's own File rows, so a file uploaded
  // through an Attach field and a file dropped on the record are one list.
  // `fieldname` narrows it by the `link_filters` on that docfield, which the
  // server reads off the field rather than taking from here.
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
      { successMessage: __('File removed') },
    ),

  // A layout: the filters, the sort and the columns saved together under a
  // name, the way Frappe's own List Filter models it. `layout` updates one,
  // `label` makes a new one, neither writes this person's unnamed default.
  // Narrows what the screen offers; never widens it, shared or not.

  submit: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.submit',
      { space_code: spaceCode, screen, name },
      { successMessage: __('Submitted') },
    ),

  cancel: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.cancel',
      { space_code: spaceCode, screen, name },
      { successMessage: __('Cancelled') },
    ),

  amend: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.amend',
      { space_code: spaceCode, screen, name },
      { successMessage: __('Amended') },
    ),

  workflowAction: (spaceCode, screen, name, action) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.workflow_action',
      { space_code: spaceCode, screen, name, action },
      { successMessage: __('Done') },
    ),

  // --- the mail about a record --------------------------------------------
  //
  // Correspondence is a `Communication` linked to the document by
  // `oneapp_core/email/linking.py`. What comes back is what *this reader* may
  // already see, never everything linked: a link is not a grant.
  recordMail: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.correspondence',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  // Sending from a record is the one path where the filing needs no working
  // out — the person was looking at the record when they wrote it.
  recordMailSend: (spaceCode, screen, name, values) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.write',
      { space_code: spaceCode, screen, name, ...values },
      { successMessage: __('Sent') },
    ),

  // The way out of every case the automatic filing did not get, and the way
  // back from every one it got wrong.
  recordMailAttach: (spaceCode, screen, name, message) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.attach',
      { space_code: spaceCode, screen, name, message },
      { successMessage: __('Filed here') },
    ),

  recordMailDetach: (spaceCode, screen, name, message) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.detach',
      { space_code: spaceCode, screen, name, message },
      { successMessage: __('Unfiled') },
    ),

  // --- print formats and letter heads -------------------------------------
  //
  // What is drawn on the page, as against the paper it comes out on. A drawn
  // format is a Frappe beta Print Format: our builder writes `format_data` and
  // Frappe's own generator renders it. See `oneapp_core/printing.py`.
}
