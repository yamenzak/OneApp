/** Addresses, the mailboxes behind them, and everything the Mail screen does. */

import { callMethod } from '../resource'

export const mail = {
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

  mailAddFolder: (address, name) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.add_folder',
      { address, name },
      { successMessage: 'Folder made' },
    ),

  mailDropFolder: (address, name) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.drop_folder',
      { address, name },
      { successMessage: 'Folder removed' },
    ),

  mailFileThread: (key, address, folder, fromFolder) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.file_thread',
      { key, address, folder, from_folder: fromFolder },
      { successMessage: 'Filed' },
    ),

  mailStar: (key, folder, on) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.star',
      { key, folder, on: on ? 1 : 0 },
      { silent: true },
    ),

  mailMarkUnread: (key, folder) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.mark_unread',
      { key, folder },
      { successMessage: 'Marked unread' },
    ),

  mailBin: (key, address, folder) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.bin',
      { key, address, folder },
      { successMessage: 'Moved to Trash' },
    ),

  mailArchive: (key, address, folder) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.archive',
      { key, address, folder },
      { successMessage: 'Archived' },
    ),

  mailDraft: (message, kind) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.draft',
      { message, kind },
      { silent: true, method: 'GET' },
    ),

  // --- filing rules and the out-of-office ----------------------------------
  //
  // `oneapp_core/email/rules.py`. A rule belongs to a mailbox, so every one of
  // these checks the address is one the caller holds — which is why they are
  // whitelisted endpoints rather than a screen over `Mail Rule`.

  // --- filing rules and the out-of-office ----------------------------------
  //
  // `oneapp_core/email/rules.py`. A rule belongs to a mailbox, so every one of
  // these checks the address is one the caller holds — which is why they are
  // whitelisted endpoints rather than a screen over `Mail Rule`.
  mailRules: (address) =>
    callMethod(
      'oneapp.oneapp_core.email.rules.listing',
      { address },
      { silent: true, method: 'GET' },
    ),

  mailSaveRule: (values) =>
    callMethod(
      'oneapp.oneapp_core.email.rules.save',
      { values: JSON.stringify(values) },
      { successMessage: 'Rule saved' },
    ),

  mailDropRule: (name) =>
    callMethod(
      'oneapp.oneapp_core.email.rules.drop',
      { name },
      { successMessage: 'Rule removed' },
    ),

  mailAway: (address) =>
    callMethod(
      'oneapp.oneapp_core.email.rules.away',
      { address },
      { silent: true, method: 'GET' },
    ),

  mailSetAway: (values) =>
    callMethod('oneapp.oneapp_core.email.rules.set_away', values, {
      successMessage: 'Saved',
    }),

  mailUnsend: (name) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.unsend',
      { name },
      { successMessage: 'Unsent' },
    ),

  mailKeep: (values) =>
    callMethod(
      'oneapp.oneapp_core.email.mailbox.keep',
      { values: JSON.stringify(values) },
      { silent: true },
    ),

  mailKept: () =>
    callMethod('oneapp.oneapp_core.email.mailbox.kept', {}, {
      silent: true, method: 'GET',
    }),

  mailForget: () =>
    callMethod('oneapp.oneapp_core.email.mailbox.forget', {}, { silent: true }),

  mailSuggest: (text) =>
    callMethod(
      'oneapp.oneapp_core.email.people.suggest',
      { text },
      { silent: true, method: 'GET' },
    ),

  mailProfile: (email) =>
    callMethod(
      'oneapp.oneapp_core.email.people.profile',
      { email },
      { silent: true, method: 'GET' },
    ),

  // --- connecting a mailbox somebody already has ---------------------------

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

  mailRefreshFolders: (name) =>
    callMethod(
      'oneapp.oneapp_core.email.connect.refresh',
      { name },
      { successMessage: 'Folders refreshed' },
    ),

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
}
