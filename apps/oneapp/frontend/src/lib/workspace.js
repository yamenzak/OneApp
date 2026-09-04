/**
 * Workspace settings: the parts of Frappe a customer owns.
 *
 * The field list is not written here. The server owns the spec — which setting
 * exists, what type it is, and which of Frappe's singles it writes — because
 * that same object is the allowlist the write path checks against. A copy in
 * the SPA would be a second list to keep in step, and the one that drifts is
 * always the one that decides what is rendered.
 */

import { callMethod } from './resource'

export const workspace = {
  settings: () =>
    callMethod('oneapp.oneapp_core.workspace.get', {}, { silent: true, method: 'GET' }),

  save: (group, values) =>
    callMethod(
      'oneapp.oneapp_core.workspace.save',
      { group, values },
      {
        successMessage: 'Saved',
      },
    ),

  // The AI tab is not a field list like the rest: it is the feature registry
  // rendered, so the server sends rows rather than a spec. What it never sends
  // is our own instructions for a feature — only what the workspace added.
  ai: () => callMethod('oneapp.oneapp_core.ai.settings.get', {}, { silent: true, method: 'GET' }),

  saveAi: (values) =>
    callMethod(
      'oneapp.oneapp_core.ai.settings.update',
      { values },
      {
        successMessage: 'Saved',
      },
    ),

  // One screen, resolved against this site's own metadata: what each field is
  // called and whether this user may write it are facts only the tenant has.
  //
  // Rows and writes go through the screen too, rather than a generic document
  // API. That is what stops a screen being used to read a doctype the
  // entitlement did not include, or to write a field it does not show.
  screenSpec: (spaceCode, screen, layout, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.spec',
      { space_code: spaceCode, screen, layout, view_type: viewType },
      {
        silent: true,
        method: 'GET',
      },
    ),

  // `overrides` carries a filter or sort the person changed but has not saved:
  // the list answers the question the controls are asking, saved or not.
  screenRows: (spaceCode, screen, overrides, layout, page = {}, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.rows',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        // `start` pages; `limit` is how big a page is, which the reader picks
        // in the footer and the server bounds again.
        start: page.start || 0,
        limit: page.limit || undefined,
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // Its own request, and deliberately after the rows: a count over a filter
  // with no index behind it is a full scan, and nothing should hold a list up
  // for one.
  screenRowCount: (spaceCode, screen, overrides, layout, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.count',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // One record, by id. The list row carries only the columns somebody chose to
  // see; the record shows the doctype's whole field list, so it is fetched
  // rather than read out of the row — which is also what lets a record be a
  // link somebody can send.
  screenRecord: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.record',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  saveRecord: (spaceCode, screen, values, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.save',
      { space_code: spaceCode, screen, values, name },
      { successMessage: 'Saved' },
    ),

  // One call for a whole selection: forty rows is forty round trips otherwise,
  // and a failure halfway through leaves nobody able to say what happened.
  removeRecords: (spaceCode, screen, names) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.remove',
      { space_code: spaceCode, screen, name: names },
      { silent: true },
    ),

  // A Link is a foreign key, and a text box over one asks a customer to know a
  // record's name. Bounded by the screen like every other read.
  //
  // `target` is only meaningful for a Dynamic Link, whose doctype is on the
  // record rather than on the field. The server validates it against the
  // space's grant and this user's permissions before fetching anything, and
  // ignores it for a plain Link.
  linkOptions: (spaceCode, screen, fieldname, query, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_options',
      { space_code: spaceCode, screen, fieldname, query, target },
      { silent: true, method: 'GET' },
    ),

  // What choosing that record fills in elsewhere on the form.
  //
  // Frappe's `fetch_from` already applies on save, wherever the write came
  // from, so this changes no outcome — only when you see it. Without it the
  // Company box sits empty, somebody types into it, and the save quietly
  // replaces what they typed with the value it was always going to use.
  //
  // `silent`, because a form that fills itself in is a convenience: if the
  // lookup fails the field stays as it was and the save still fills it, which
  // is the behaviour that existed before this call did.
  fetched: (spaceCode, screen, fieldname, value) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.fetched',
      { space_code: spaceCode, screen, fieldname, value },
      { silent: true, method: 'GET' },
    ),

  // What creating one of those records would ask for: Frappe's own quick entry,
  // which is the fields a doctype marks `allow_in_quick_entry` plus anything
  // mandatory. Answers `can_create: false` rather than raising when the target
  // is outside the space or this user may not create it — a picker with no
  // Create row is the right shape for that.
  linkNewSpec: (spaceCode, screen, fieldname, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_new_spec',
      { space_code: spaceCode, screen, fieldname, target },
      { silent: true, method: 'GET' },
    ),

  // Create one, and hand back the picker row for it so the field can adopt the
  // record without a second search.
  linkNew: (spaceCode, screen, fieldname, values, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_new',
      { space_code: spaceCode, screen, fieldname, values, target },
      { successMessage: 'Created' },
    ),

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
  linkPreview: (spaceCode, screen, fieldname, name, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_preview',
      { space_code: spaceCode, screen, fieldname, name, target },
      { silent: true, method: 'GET' },
    ),

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
  dashboard: (spaceCode, screen, { layout = '', overrides = null } = {}) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.dashboard_data',
      {
        space_code: spaceCode,
        screen,
        layout: layout || undefined,
        overrides: overrides ? JSON.stringify(overrides) : undefined,
      },
      { silent: true, method: 'GET' },
    ),

  // --- mail ---------------------------------------------------------------
  // Addresses, who holds each, and what they sign with. See
  // `oneapp_core/email/addresses.py` — the model is Frappe's Email Account and
  // User Email, so none of this is a parallel permission system.
  mail: () =>
    callMethod('oneapp.oneapp_core.email.addresses.listing', {}, {
      silent: true, method: 'GET',
    }),

  mailCreate: (localPart, label, grantTo) =>
    callMethod(
      'oneapp.oneapp_core.email.addresses.create',
      { local_part: localPart, label, grant_to: JSON.stringify(grantTo || []) },
      { successMessage: 'Address created' },
    ),

  mailUpdate: (name, values) =>
    callMethod(
      'oneapp.oneapp_core.email.addresses.update',
      { name, ...values },
      { successMessage: 'Saved' },
    ),

  mailRemove: (name) =>
    callMethod(
      'oneapp.oneapp_core.email.addresses.remove',
      { name },
      { successMessage: 'Address removed' },
    ),

  mailGrant: (name, user) =>
    callMethod('oneapp.oneapp_core.email.addresses.grant', { name, user }),

  mailRevoke: (name, user) =>
    callMethod('oneapp.oneapp_core.email.addresses.revoke', { name, user }),

  mailSetDefault: (name) =>
    callMethod(
      'oneapp.oneapp_core.email.addresses.set_default',
      { name },
      { successMessage: 'Sending address set' },
    ),

  mailUsage: () =>
    callMethod('oneapp.oneapp_core.email.outbound.usage', {}, {
      silent: true, method: 'GET',
    }),

  mailDomain: (domain) =>
    callMethod(
      'oneapp.oneapp_core.email.verify.status',
      { domain },
      { silent: true, method: 'GET' },
    ),

  mailDomainConfirm: (domain) =>
    callMethod(
      'oneapp.oneapp_core.email.verify.confirm',
      { domain },
      { successMessage: 'Domain verified' },
    ),

  mailSuppressed: () =>
    callMethod('oneapp.oneapp_core.email.suppression.listing', {}, {
      silent: true, method: 'GET',
    }),

  mailRelease: (email) =>
    callMethod(
      'oneapp.oneapp_core.email.suppression.release',
      { email },
      { successMessage: 'Sending to that address again' },
    ),

  // --- the mailbox --------------------------------------------------------
  // Reading is a Communication list asked the right questions — see
  // `oneapp_core/email/mailbox.py`. Which addresses a person may read is the
  // query's filter, not the render's.
  mailFolders: () =>
    callMethod('oneapp.oneapp_core.email.mailbox.folders', {}, {
      silent: true, method: 'GET',
    }),

  mailThreads: (folder, start = 0, search = '') =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.threads',
      { folder, start, search },
      { silent: true, method: 'GET' },
    ),

  mailThread: (key, folder) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.thread',
      { key, folder },
      { silent: true, method: 'GET' },
    ),

  mailUnread: () =>
    callMethod('oneapp.oneapp_core.email.mailbox.unread', {}, {
      silent: true, method: 'GET',
    }),

  mailMarkRead: (names) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.mark_read',
      { names: JSON.stringify(names) },
      { silent: true },
    ),

  mailSend: (values) =>
    callMethod('oneapp.oneapp_core.email.mailbox.send', values, {
      successMessage: 'Sent',
    }),

  // --- connecting a mailbox somebody already has ---------------------------
  mailConnected: () =>
    callMethod('oneapp.oneapp_core.email.connect.mine', {}, {
      silent: true, method: 'GET',
    }),

  mailSuggestion: (emailId) =>
    callMethod(
      'oneapp.oneapp_core.email.connect.suggestion',
      { email_id: emailId },
      { silent: true, method: 'GET' },
    ),

  mailConnect: (values) =>
    callMethod('oneapp.oneapp_core.email.connect.connect', values, {
      successMessage: 'Mailbox connected',
    }),

  mailDisconnect: (name) =>
    callMethod(
      'oneapp.oneapp_core.email.connect.disconnect',
      { name },
      { successMessage: 'Mailbox disconnected' },
    ),

  // --- naming -----------------------------------------------------------
  //
  // Frappe's `Document Naming Settings`, gated to the doctypes this
  // workspace's spaces granted. See `oneapp_core/naming.py`.

  naming: () =>
    callMethod('oneapp.oneapp_core.workspace.naming', {}, { silent: true, method: 'GET' }),

  setNaming: (doctype, series) =>
    callMethod(
      'oneapp.oneapp_core.workspace.set_naming',
      { doctype, series: JSON.stringify(series) },
      { successMessage: 'Series saved' },
    ),

  setNamingCounter: (doctype, prefix, value) =>
    callMethod(
      'oneapp.oneapp_core.workspace.set_naming_counter',
      { doctype, prefix, value },
      { successMessage: 'Counter moved' },
    ),

  namingPreview: (doctype, prefix) =>
    callMethod(
      'oneapp.oneapp_core.workspace.naming_preview',
      { doctype, prefix },
      { silent: true, method: 'GET' },
    ),

  // --- bringing their data with them ------------------------------------
  //
  // See `oneapp_core/importer.py`. The panel is one read and two buttons; the
  // rest of this is watching a job somebody else is running.
  importConsole: () =>
    callMethod('oneapp.oneapp_core.importer.console', {}, { silent: true, method: 'GET' }),

  saveImportSource: (name, baseUrl, apiKey, apiSecret) =>
    callMethod(
      'oneapp.oneapp_core.importer.save_source',
      { name, base_url: baseUrl, api_key: apiKey, api_secret: apiSecret },
      { successMessage: 'Saved' },
    ),

  installImportPlan: (plan, source) =>
    callMethod(
      'oneapp.oneapp_core.importer.install_plan',
      { plan, source },
      { successMessage: 'Set up' },
    ),

  verifyImportSource: (source) =>
    callMethod('oneapp.oneapp_core.importer.verify', { source }, { silent: true }),

  checkImportPlan: (plan) =>
    callMethod('oneapp.oneapp_core.importer.check', { plan }, { silent: true }),

  startImport: (plan, dryRun) =>
    callMethod('oneapp.oneapp_core.importer.start', { plan, dry_run: dryRun ? 1 : 0 }),

  importProgress: (run) =>
    callMethod('oneapp.oneapp_core.importer.progress', { run },
               { silent: true, method: 'GET' }),

  importIssues: (run) =>
    callMethod('oneapp.oneapp_core.importer.issues', { run }, { silent: true, method: 'GET' }),

  // --- printing ---------------------------------------------------------
  //
  // Frappe renders the format and Frappe makes the PDF; these are the screen's
  // own gate over both. See `oneapp_core/printing.py`.

  printOptions: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.print_options',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  printPreview: (spaceCode, screen, name, { format = '', letterhead = '', language = '' } = {}) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.print_preview',
      { space_code: spaceCode, screen, name, format, letterhead, language },
      { silent: true, method: 'GET' },
    ),

  /**
   * A URL rather than a call.
   *
   * The PDF comes back as a download response with a filename on it, so the
   * browser should be handed the address and left to do what it does with one
   * — fetching the bytes and rebuilding a file loses the name and the
   * progress bar both.
   */
  printPdfUrl: (spaceCode, screen, name, { format = '', letterhead = '', language = '' } = {}) => {
    const asked = new URLSearchParams({
      space_code: spaceCode,
      screen,
      name,
      format,
      letterhead,
      language,
    })
    return `/api/method/oneapp.oneapp_core.spaceview.print_pdf?${asked}`
  },

  // --- where a document stands ---------------------------------------------
  //
  // Submit, cancel and amend are three permissions rather than one verb, and a
  // workflow transition is checked by the workflow — so four calls rather than
  // one taking a string. See `oneapp_core/docflow.py`.

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

  // --- print formats and letter heads -------------------------------------
  //
  // What is drawn on the page, as against the paper it comes out on — the
  // paper is a settings group and lives in `SettingsFields`. A drawn format is
  // a Frappe beta Print Format: our builder writes `format_data` and Frappe's
  // own generator renders it, so the same format prints identically wherever
  // it is opened. See `oneapp_core/printing.py`.

  printFormats: (doctype = '') =>
    callMethod(
      'oneapp.oneapp_core.workspace.print_formats',
      { doctype },
      { silent: true, method: 'GET' },
    ),

  printPalette: (doctype) =>
    callMethod(
      'oneapp.oneapp_core.workspace.print_palette',
      { doctype },
      { silent: true, method: 'GET' },
    ),

  printFormat: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.print_format',
      { name },
      { silent: true, method: 'GET' },
    ),

  savePrintFormat: (doctype, label, layout, setup, name = '') =>
    callMethod(
      'oneapp.oneapp_core.workspace.save_print_format',
      {
        doctype,
        label,
        layout: JSON.stringify(layout),
        setup: JSON.stringify(setup || {}),
        name,
      },
      { successMessage: 'Format saved' },
    ),

  deletePrintFormat: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.delete_print_format',
      { name },
      { successMessage: 'Format deleted' },
    ),

  setDefaultPrintFormat: (doctype, name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.set_default_print_format',
      { doctype, name },
      { successMessage: 'Default set' },
    ),

  printFormatPreview: (doctype, layout, setup, { name = '', letterhead = '' } = {}) =>
    callMethod(
      'oneapp.oneapp_core.workspace.print_format_preview',
      {
        doctype,
        layout: JSON.stringify(layout),
        setup: JSON.stringify(setup || {}),
        name,
        letterhead,
      },
      { silent: true },
    ),

  letterHeads: () =>
    callMethod('oneapp.oneapp_core.workspace.letter_heads', {}, { silent: true, method: 'GET' }),

  letterHead: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.letter_head',
      { name },
      { silent: true, method: 'GET' },
    ),

  saveLetterHead: (label, values, name = '') =>
    callMethod(
      'oneapp.oneapp_core.workspace.save_letter_head',
      { label, values: JSON.stringify(values || {}), name },
      { successMessage: 'Letter head saved' },
    ),

  deleteLetterHead: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.delete_letter_head',
      { name },
      { successMessage: 'Letter head deleted' },
    ),

  // --- tags and sharing ---------------------------------------------------
  //
  // Frappe's `_user_tags` and `DocShare`, screen-gated. See
  // `oneapp_core/collab.py` for what each one is and why neither is ours.

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
  rename: (spaceCode, screen, name, newName) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.rename',
      { space_code: spaceCode, screen, name, new_name: newName },
      { successMessage: 'Renamed' },
    ),

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
  resetLayout: (spaceCode, screen, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.reset_layout',
      { space_code: spaceCode, screen, view_type: viewType || undefined },
      { successMessage: 'Back to the default screen' },
    ),

  books: () => callMethod('oneapp.oneapp_core.books.status', {}, { silent: true, method: 'GET' }),

  charts: (country) =>
    callMethod(
      'oneapp.oneapp_core.books.charts',
      { country },
      {
        silent: true,
        method: 'GET',
      },
    ),

  resetBooks: () =>
    callMethod(
      'oneapp.oneapp_core.books.reset',
      {},
      {
        successMessage: 'Cleared — set your books up again below',
      },
    ),

  setUpBooks: (payload) =>
    callMethod('oneapp.oneapp_core.books.create', payload, {
      successMessage: 'Books are ready',
    }),
}
