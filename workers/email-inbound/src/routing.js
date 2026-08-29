/**
 * Recipient parsing. Kept dependency-free so it is testable in plain node —
 * this is the code that decides which tenant a message belongs to, and getting
 * it wrong means delivering one customer's mail to another.
 */

// Keep in step with oneapp_control/utils/slug.py.
export const MIN_SLUG_LENGTH = 3
export const MAX_SLUG_LENGTH = 40

export function parseRecipient(recipient, mailDomain) {
  if (!recipient || typeof recipient !== 'string') return null
  if (!mailDomain) return null

  const at = recipient.indexOf('@')
  if (at < 1) return null

  const localPart = recipient.slice(0, at).toLowerCase()
  const host = recipient.slice(at + 1).toLowerCase()

  const suffix = `.${mailDomain.toLowerCase()}`
  if (!host.endsWith(suffix)) return null

  const tenant = host.slice(0, -suffix.length)

  // Exactly one label. `a.b.t.4dl.app` is not an address we issued, and treating
  // it as tenant "a.b" would be a routing error.
  if (!tenant || tenant.includes('.')) return null

  // Mirrors the control plane's slug rules, length bounds included. The pattern
  // alone would accept a single character, which is not a slug we ever issue.
  if (tenant.length < MIN_SLUG_LENGTH || tenant.length > MAX_SLUG_LENGTH) return null
  if (!/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(tenant)) return null
  if (tenant.includes('--')) return null

  return { tenant, localPart }
}
