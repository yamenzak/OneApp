/**
 * Recipient parsing. Kept dependency-free so it is testable in plain node —
 * this is the code that decides which tenant a message belongs to, and getting
 * it wrong means delivering one customer's mail to another.
 *
 * The tenant is in the **local part**, not the hostname: `acme.ap@4dl.app`
 * rather than `ap@acme.4dl.app`. That is not a style choice. Cloudflare caps a
 * zone at 30 domains configured for Email Routing or Email Sending combined,
 * including the apex, and there is no wildcard — every subdomain is onboarded
 * one at a time. A subdomain per workspace therefore caps the platform at about
 * twenty-nine of them. One domain with the tenant in the local part costs one
 * onboarding and one catch-all rule, for ever.
 *
 * Two shapes arrive here and both are ours:
 *
 *     acme.ap@4dl.app     an address a workspace issued
 *     t-acme@4dl.app      the envelope sender outbound uses, so bounces land
 */

// Keep in step with oneapp_control/utils/slug.py.
export const MIN_SLUG_LENGTH = 3
export const MAX_SLUG_LENGTH = 40

// The one the outbound side sends as. `oneapp_core/email/outbound.py`.
const BOUNCE_PREFIX = 't-'

// What a workspace's own local part may contain, once the tenant is off the
// front. Dots are gone by then — the first one is the separator — so this is
// deliberately narrower than the address grammar RFC 5322 permits, and matches
// `oneapp_core/email/addresses.validate_local_part`.
const LOCAL = /^[a-z0-9](?:[a-z0-9._+-]*[a-z0-9+])?$/

const SLUG = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/

/** Whether a string is a slug the control plane would have issued. */
export function isSlug(value) {
  if (!value || value.length < MIN_SLUG_LENGTH || value.length > MAX_SLUG_LENGTH) return false
  if (!SLUG.test(value)) return false
  return !value.includes('--')
}

export function parseRecipient(recipient, mailDomain) {
  if (!recipient || typeof recipient !== 'string') return null
  if (!mailDomain) return null

  const at = recipient.indexOf('@')
  if (at < 1) return null

  const local = recipient.slice(0, at).toLowerCase()
  const host = recipient.slice(at + 1).toLowerCase()

  // Exactly our domain. Not a subdomain of it and not a domain that merely
  // ends with it: `notthe4dl.app` must never be read as ours.
  if (host !== mailDomain.toLowerCase()) return null

  // A bounce for a message we sent. No local part of its own — the whole
  // address identifies the tenant — and the site decides what to do with it.
  if (local.startsWith(BOUNCE_PREFIX)) {
    const tenant = local.slice(BOUNCE_PREFIX.length)
    return isSlug(tenant) ? { tenant, localPart: '', bounce: true } : null
  }

  const dot = local.indexOf('.')
  if (dot < 1) return null

  const tenant = local.slice(0, dot)
  const localPart = local.slice(dot + 1)

  if (!isSlug(tenant)) return null
  if (!localPart || !LOCAL.test(localPart)) return null

  return { tenant, localPart, bounce: false }
}
