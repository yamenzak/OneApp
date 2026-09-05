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
  // Whether this person holds an address at all, and how much of it is unread.
  // Here rather than in the bell that draws them, because a phone never renders
  // the rail — so a bell that owned the polling meant a phone that never knew
  // there was any mail, and no Mail row in the sheet that is its only way in.
  held: false,
  unread: 0,
})

// A minute, which is slow for a mail client and right for this. The Mail page
// refreshes on open; this only decides whether a number in the rail is stale,
// and polling it faster would be a request a minute per open tab for a badge
// most people are not looking at.
const EVERY = 60_000
let ticking = null

/**
 * Keep `held` and `unread` current for as long as there is a session.
 *
 * Started by the app the way notifications are, and for the same reason: the
 * things that decide what the shell offers cannot be owned by the parts of the
 * shell they decide about.
 */
export function followMail() {
  const look = async () => {
    try {
      const folders = await workspace.mailFolders()
      mail.held = (folders?.addresses || []).length > 0
      mail.unread = mail.held ? await workspace.mailUnread() : 0
    } catch {
      // A workspace with no mail set up answers with a refusal rather than a
      // zero, and a shell that toasted about it once a minute would be worse
      // than one that quietly offers nothing.
      mail.held = false
      mail.unread = 0
    }
  }

  clearInterval(ticking)
  look()
  ticking = setInterval(look, EVERY)
}

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


// `<img src="https://…">` — every remote image in a message body.
//
// Frappe strips the dangerous half of inbound HTML on save (a `<script>` and an
// `onerror` never reach the database), so what is left is the *privacy* half,
// and it is the half nobody strips: a 1×1 image on somebody else's server tells
// them the moment a message was opened, by whom, from where. Every mail client
// worth using blocks these until asked, and this is that.
const REMOTE_IMAGE = /(<img\b[^>]*?\bsrc=)(["'])(https?:\/\/[^"']*)\2/gi

/**
 * A message body with its remote images held back, and a count of them.
 *
 * The URL is kept on a `data-` attribute rather than thrown away, so showing
 * them is a swap in the browser and not another request to the server. Images
 * the site already holds — an attachment, an inline image saved with the
 * message — are left alone: they are ours, and fetching them tells nobody
 * anything.
 */
export function holdImages(html) {
  let held = 0
  const body = String(html || '').replace(REMOTE_IMAGE, (whole, prefix, quote, url) => {
    held += 1
    return `${prefix}${quote}${quote} data-held=${quote}${url}${quote}`
  })
  return { body, held }
}

/** The same body with the images put back. */
export function showImages(html) {
  return String(html || '').replace(
    /<img\b([^>]*?)\bsrc=(["'])\2([^>]*?)\bdata-held=(["'])([^"']*)\4/gi,
    (whole, before, q1, between, q2, url) => `<img${before}src=${q2}${url}${q2}${between}`,
  )
}
