/** Addresses, the mailboxes behind them, and everything the Mail screen does. */

import { callMethod } from '@/lib/runtime/resource'
import { __ } from '@/lib/runtime/translate'

export const mail = {
  // --- mail ---------------------------------------------------------------
  // Addresses, who holds each, and what they sign with. See
  // `onemail/addresses.py` — the model is Frappe's Email Account and
  // User Email, so none of this is a parallel permission system.
  mail: () =>
    callMethod('oneapp.onemail.addresses.listing', {}, {
      silent: true, method: 'GET',
    }),

  mailCreate: (localPart, label, grantTo) =>
    callMethod(
      'oneapp.onemail.addresses.create',
      { local_part: localPart, label, grant_to: JSON.stringify(grantTo || []) },
      { successMessage: __('Address created') },
    ),

  mailUpdate: (name, values) =>
    callMethod(
      'oneapp.onemail.addresses.update',
      { name, ...values },
      { successMessage: __('Saved') },
    ),

  mailRemove: (name) =>
    callMethod(
      'oneapp.onemail.addresses.remove',
      { name },
      { successMessage: __('Address removed') },
    ),

  mailGrant: (name, user) =>
    callMethod('oneapp.onemail.addresses.grant', { name, user }),

  mailRevoke: (name, user) =>
    callMethod('oneapp.onemail.addresses.revoke', { name, user }),

  mailSetDefault: (name) =>
    callMethod(
      'oneapp.onemail.addresses.set_default',
      { name },
      { successMessage: __('Sending address set') },
    ),

  mailUsage: () =>
    callMethod('oneapp.onemail.outbound.usage', {}, {
      silent: true, method: 'GET',
    }),

  mailDomain: (domain) =>
    callMethod(
      'oneapp.onemail.verify.status',
      { domain },
      { silent: true, method: 'GET' },
    ),

  mailDomainConfirm: (domain) =>
    callMethod(
      'oneapp.onemail.verify.confirm',
      { domain },
      { successMessage: __('Domain verified') },
    ),

  mailSuppressed: () =>
    callMethod('oneapp.onemail.suppression.listing', {}, {
      silent: true, method: 'GET',
    }),

  mailRelease: (email) =>
    callMethod(
      'oneapp.onemail.suppression.release',
      { email },
      { successMessage: __('Sending to that address again') },
    ),

  // --- the mailbox --------------------------------------------------------
  // Reading is a Communication list asked the right questions — see
  // `onemail/mailbox.py`. Which addresses a person may read is the
  // query's filter, not the render's.
  mailFolders: () =>
    callMethod('oneapp.onemail.mailbox.folders', {}, {
      silent: true, method: 'GET',
    }),

  mailThreads: (folder, start = 0, search = '') =>
    callMethod(
      'oneapp.onemail.mailbox.threads',
      { folder, start, search },
      { silent: true, method: 'GET' },
    ),

  mailThread: (key, folder) =>
    callMethod(
      'oneapp.onemail.mailbox.thread',
      { key, folder },
      { silent: true, method: 'GET' },
    ),

  mailUnread: () =>
    callMethod('oneapp.onemail.mailbox.unread', {}, {
      silent: true, method: 'GET',
    }),

  mailMarkRead: (names) =>
    callMethod(
      'oneapp.onemail.mailbox.mark_read',
      { names: JSON.stringify(names) },
      { silent: true },
    ),

  mailSend: (values) =>
    callMethod('oneapp.onemail.mailbox.send', values, {
      successMessage: __('Sent'),
    }),

  mailAddFolder: (address, name) =>
    callMethod(
      'oneapp.onemail.mailbox.add_folder',
      { address, name },
      { successMessage: __('Folder made') },
    ),

  mailDropFolder: (address, name) =>
    callMethod(
      'oneapp.onemail.mailbox.drop_folder',
      { address, name },
      { successMessage: __('Folder removed') },
    ),

  mailFileThread: (key, address, folder, fromFolder) =>
    callMethod(
      'oneapp.onemail.mailbox.file_thread',
      { key, address, folder, from_folder: fromFolder },
      { successMessage: __('Filed') },
    ),

  mailStar: (key, folder, on) =>
    callMethod(
      'oneapp.onemail.mailbox.star',
      { key, folder, on: on ? 1 : 0 },
      { silent: true },
    ),

  mailMarkUnread: (key, folder) =>
    callMethod(
      'oneapp.onemail.mailbox.mark_unread',
      { key, folder },
      { successMessage: __('Marked unread') },
    ),

  mailBin: (key, address, folder) =>
    callMethod(
      'oneapp.onemail.mailbox.bin',
      { key, address, folder },
      { successMessage: __('Moved to Trash') },
    ),

  mailArchive: (key, address, folder) =>
    callMethod(
      'oneapp.onemail.mailbox.archive',
      { key, address, folder },
      { successMessage: __('Archived') },
    ),

  // One request for a whole selection, and the note that request hands back —
  // where each conversation was — passed straight to `mailUndoBulk` if somebody
  // presses Undo. The browser carries a note, not a model of the mailbox.
  //
  // Silent because the bar that offered the action says what happened, with an
  // Undo beside it; a toast on top of that is the same sentence twice.
  mailBulk: (action, keys, address, folder) =>
    callMethod(
      'oneapp.onemail.mailbox.bulk',
      { action, keys: JSON.stringify(keys), address, folder },
      { silent: true },
    ),

  mailUndoBulk: (was, address, folder) =>
    callMethod(
      'oneapp.onemail.mailbox.restore',
      { was: JSON.stringify(was), address, folder },
      { successMessage: __('Put back') },
    ),

  // The workspace's own message templates. Read by anybody who holds an
  // address, because using one is answering an email; writing one is an admin's
  // and lives in settings.
  mailTemplates: () =>
    callMethod(
      'oneapp.onespace.workspace.mail_templates',
      {},
      { silent: true, method: 'GET' },
    ),

  // Filled in — against a record where the composer was opened from one, and as
  // written where it was not.
  mailTemplate: (name) =>
    callMethod(
      'oneapp.onespace.workspace.render_mail_template',
      { name },
      { silent: true, method: 'GET' },
    ),

  recordMailTemplate: (spaceCode, screen, record, name) =>
    callMethod(
      'oneapp.onespace.spaceview.template',
      { space_code: spaceCode, screen, name: record, template: name },
      { silent: true, method: 'GET' },
    ),

  mailDraft: (message, kind) =>
    callMethod(
      'oneapp.onemail.mailbox.draft',
      { message, kind },
      { silent: true, method: 'GET' },
    ),

  // --- filing rules and the out-of-office ----------------------------------
  //
  // `onemail/rules.py`. A rule belongs to a mailbox, so every one of
  // these checks the address is one the caller holds — which is why they are
  // whitelisted endpoints rather than a screen over `Mail Rule`.
  mailRules: (address) =>
    callMethod(
      'oneapp.onemail.rules.listing',
      { address },
      { silent: true, method: 'GET' },
    ),

  mailSaveRule: (values) =>
    callMethod(
      'oneapp.onemail.rules.save',
      { values: JSON.stringify(values) },
      { successMessage: __('Rule saved') },
    ),

  mailDropRule: (name) =>
    callMethod(
      'oneapp.onemail.rules.drop',
      { name },
      { successMessage: __('Rule removed') },
    ),

  mailAway: (address) =>
    callMethod(
      'oneapp.onemail.rules.away',
      { address },
      { silent: true, method: 'GET' },
    ),

  mailSetAway: (values) =>
    callMethod('oneapp.onemail.rules.set_away', values, {
      successMessage: __('Saved'),
    }),

  mailUnsend: (name) =>
    callMethod(
      'oneapp.onemail.mailbox.unsend',
      { name },
      { successMessage: __('Unsent') },
    ),

  mailKeep: (values) =>
    callMethod(
      'oneapp.onemail.mailbox.keep',
      { values: JSON.stringify(values) },
      { silent: true },
    ),

  mailKept: () =>
    callMethod('oneapp.onemail.mailbox.kept', {}, {
      silent: true, method: 'GET',
    }),

  mailForget: () =>
    callMethod('oneapp.onemail.mailbox.forget', {}, { silent: true }),

  mailSuggest: (text) =>
    callMethod(
      'oneapp.onemail.people.suggest',
      { text },
      { silent: true, method: 'GET' },
    ),

  mailProfile: (email) =>
    callMethod(
      'oneapp.onemail.people.profile',
      { email },
      { silent: true, method: 'GET' },
    ),

  // --- connecting a mailbox somebody already has ---------------------------
  mailConnected: () =>
    callMethod('oneapp.onemail.connect.mine', {}, {
      silent: true, method: 'GET',
    }),

  mailSuggestion: (emailId) =>
    callMethod(
      'oneapp.onemail.connect.suggestion',
      { email_id: emailId },
      { silent: true, method: 'GET' },
    ),

  mailConnect: (values) =>
    callMethod('oneapp.onemail.connect.connect', values, {
      successMessage: __('Mailbox connected'),
    }),

  mailRefreshFolders: (name) =>
    callMethod(
      'oneapp.onemail.connect.refresh',
      { name },
      { successMessage: __('Folders refreshed') },
    ),

  mailDisconnect: (name) =>
    callMethod(
      'oneapp.onemail.connect.disconnect',
      { name },
      { successMessage: __('Mailbox disconnected') },
    ),

  // --- naming -----------------------------------------------------------
  //
  // Frappe's `Document Naming Settings`, gated to the doctypes this
  // workspace's spaces granted. See `onespace/naming.py`.

  // --- an address of your own, and who may add an outside one --------------
  //
  // `onemail/addresses.py`. The first two are a person's own — an
  // address on the workspace's domain is theirs to claim rather than an
  // admin's to remember — and the policy is readable by everybody, because the
  // person it refuses is owed the reason.
  mailMine: () =>
    callMethod('oneapp.onemail.addresses.mine', {}, {
      silent: true, method: 'GET',
    }),

  mailClaim: (localPart = '') =>
    callMethod(
      'oneapp.onemail.addresses.claim',
      { local_part: localPart },
      { successMessage: __('That address is yours') },
    ),

  mailSetConnectPolicy: (mode, domains) =>
    callMethod(
      'oneapp.onemail.addresses.set_connect_policy',
      { mode, domains },
      { successMessage: __('Saved') },
    ),

  // --- which address a message goes out as ---------------------------------
  mailSendingFrom: (values = {}) =>
    callMethod('oneapp.onemail.mailbox.sending_from', values, {
      silent: true, method: 'GET',
    }),

  mailSetDefaultSender: (address) =>
    callMethod(
      'oneapp.onemail.mailbox.set_default_sender',
      { address },
      { successMessage: __('Saved') },
    ),

  // --- a domain the workspace owns -----------------------------------------
  //
  // `onemail/verify.py` has answered these since the day it landed
  // and nothing drew them, so a workspace could put its own domain on an
  // address and had nowhere to be told what DNS to publish.
  mailDomainStatus: (domain) =>
    callMethod('oneapp.onemail.verify.status', { domain }, {
      silent: true, method: 'GET',
    }),

  mailDomainConfirm: (domain) =>
    callMethod('oneapp.onemail.verify.confirm', { domain }, {
      successMessage: __('Checked'),
    }),
}
