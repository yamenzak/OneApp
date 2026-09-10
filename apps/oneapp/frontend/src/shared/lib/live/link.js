/**
 * The secret this page was opened with, if it was opened with one.
 *
 * A link a stranger can edit through is `/one/link/<secret>`, and the secret
 * is the only credential that browser has — there is no account, no share row
 * and no cookie worth anything. Five places need it and none of them is on a
 * path from the router to the next: the socket handshake (a websocket cannot
 * carry a header), the workbook's load and save, the document's, the page
 * that decides which editor to draw, and the editor itself, which draws no
 * breadcrumb and no rails when this is how it was reached.
 *
 * So it is read from the address bar rather than passed down. Threading it
 * through the router, the page, the editor and the persistence layer would
 * mean five signatures changing to carry a value that is already right there
 * and cannot disagree with itself.
 */

const AT = /\/one\/link\/([^/?#]+)/

export function linkSecret() {
  if (typeof window === 'undefined') return ''
  const found = AT.exec(window.location.pathname)
  return found ? decodeURIComponent(found[1]) : ''
}

/** Whether this page is somebody following a link rather than signed in. */
export function throughLink() {
  return !!linkSecret()
}
