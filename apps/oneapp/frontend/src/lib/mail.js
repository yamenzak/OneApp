/**
 * What the mail rail knows, in one place.
 *
 * The rail is the shell's sidebar and the conversations are the page, so two
 * components need the same folder list. A module-level reactive rather than a
 * prop or a provide: the sidebar outlives the page — it is rendered by the
 * shell — so there is no parent for the page to receive it from, and fetching
 * it twice would draw two rails a beat apart.
 */
import { reactive } from 'vue'
import { workspace } from './workspace'

export const mail = reactive({
  folders: [],
  addresses: [],
  mailboxes: [],
  loaded: false,
  refreshing: false,
})

/** Fetch the rail once. Repeat calls are free; `reload` forces it. */
export async function loadMail({ reload = false } = {}) {
  if (mail.loaded && !reload) return mail
  const [found, connected] = await Promise.all([
    workspace.mailFolders(),
    workspace.mailConnected(),
  ])
  mail.folders = found?.folders || []
  mail.addresses = found?.addresses || []
  mail.mailboxes = connected || []
  mail.loaded = true
  return mail
}

/**
 * Ask each connected mailbox what folders it has now.
 *
 * A folder made in Outlook this morning is one this site has never heard of,
 * and IMAP has no folder-change notification worth relying on. So it is a
 * button rather than a nightly job that re-lists every mailbox on the site to
 * catch the once-a-month case.
 */
export async function refreshMail() {
  mail.refreshing = true
  try {
    for (const box of mail.mailboxes) await workspace.mailRefreshFolders(box.name)
    await loadMail({ reload: true })
  } finally {
    mail.refreshing = false
  }
}
