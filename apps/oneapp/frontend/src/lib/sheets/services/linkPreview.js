/**
 * The hover card for a URL in a cell.
 *
 * The server half is `onespace/link_preview.py`, vendored from Frappe with
 * its SSRF guards intact — the browser cannot fetch a foreign page, so the
 * tenant's server does, which is the whole reason that module is as careful as
 * it is. Off unless an operator turned it on, and a site that has not says so
 * by answering `{error: true}`, which is the same answer an unreachable host
 * gives: the card degrades to the bare URL and the link still works.
 *
 * Memoised per URL for the session. The server caches too — a dead link
 * hovered forty times is one fetch — and this saves even the round trip.
 */

import { callMethod } from '@/lib/runtime/resource'

const held = new Map()

export function fetchLinkPreview(url) {
  if (!/^https?:\/\//i.test(url || '')) return Promise.resolve({ error: true })
  if (held.has(url)) return Promise.resolve(held.get(url))

  const asked = callMethod(
    'oneapp.onespace.link_preview.get_link_preview',
    { url },
    { silent: true, method: 'GET' },
  )
    .then((answer) => answer || { error: true })
    .catch(() => ({ error: true }))
    .then((answer) => {
      held.set(url, answer)
      return answer
    })

  held.set(url, asked)
  return asked
}
