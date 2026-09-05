/**
 * The hover card for a URL in a cell — not built, and shaped so it can be.
 *
 * Upstream this calls `sheets.link_preview.get_link_preview`, which fetches the
 * page and reads its Open Graph tags. We have no such endpoint yet, and adding
 * one is not a small decision: it makes the tenant's server fetch a URL a
 * person typed into a spreadsheet, which is an outbound request to an arbitrary
 * host from inside our network, on somebody else's say-so. That wants a policy
 * before it wants code.
 *
 * So: every URL answers "no preview", the card renders nothing, and the link
 * still works. Replace the body, not the signature.
 */

export function fetchLinkPreview() {
  return Promise.resolve({ error: true })
}
