/**
 * Inbound mail for OneApp tenants.
 *
 * Cloudflare Email Routing delivers every message on the catch-all here. We work
 * out which tenant a recipient belongs to, parse the MIME, and HMAC-POST it to
 * that tenant's site.
 *
 * Addresses are <local>@<tenant>.t.4dl.app, so the tenant is in the hostname and
 * a message can be routed without touching the control plane. The tenant map
 * lives in KV for the same reason: a control-plane outage should not bounce
 * customer mail.
 */

import PostalMime from 'postal-mime'

import { parseRecipient } from './routing.js'

export default {
  async email(message, env, ctx) {
    const recipient = (message.to || '').toLowerCase()
    const routing = parseRecipient(recipient, env.MAIL_DOMAIN)

    if (!routing) {
      // Nothing we can route. Reject at SMTP time so the sender is told, rather
      // than silently swallowing their mail.
      message.setReject('Unknown recipient')
      return
    }

    const tenant = await lookupTenant(env, routing.tenant)
    if (!tenant) {
      message.setReject('Unknown recipient')
      return
    }

    let parsed
    try {
      parsed = await new PostalMime().parse(message.raw)
    } catch (err) {
      // A message we cannot parse is still a message someone sent. Forward the
      // envelope so it is visible, rather than dropping it.
      parsed = { subject: message.headers.get('subject') || '(unparsable)', text: '' }
    }

    const payload = {
      message_id: message.headers.get('message-id') || parsed.messageId || null,
      from: message.from,
      to: recipient,
      local_part: routing.localPart,
      subject: parsed.subject || '',
      text: parsed.text || '',
      html: parsed.html || '',
      attachments: collectAttachments(parsed, Number(env.MAX_ATTACHMENT_BYTES || 25000000)),
    }

    await deliver(tenant, payload)
  },
}

async function lookupTenant(env, slug) {
  const raw = await env.TENANTS.get(slug)
  if (!raw) return null
  try {
    const tenant = JSON.parse(raw)
    return tenant.url && tenant.secret ? tenant : null
  } catch {
    return null
  }
}

function collectAttachments(parsed, maxBytes) {
  const out = []
  for (const attachment of parsed.attachments || []) {
    const content = attachment.content
    if (!content) continue
    // Oversized attachments are skipped, not fatal — the message body still
    // reaches the tenant.
    if (content.byteLength > maxBytes) continue
    out.push({
      filename: attachment.filename || 'attachment',
      mime_type: attachment.mimeType || 'application/octet-stream',
      content: base64(content),
    })
  }
  return out
}

function base64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk))
  }
  return btoa(binary)
}

export async function sign(secret, body) {
  const timestamp = Math.floor(Date.now() / 1000).toString()
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const signature = await crypto.subtle.sign(
    'HMAC',
    key,
    new TextEncoder().encode(`${timestamp}.${body}`),
  )
  const hex = [...new Uint8Array(signature)]
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
  return { signature: hex, timestamp }
}

async function deliver(tenant, payload) {
  // Must match the site's canonicalisation exactly or the signature will not
  // verify: compact separators, sorted keys.
  const body = JSON.stringify(payload, Object.keys(payload).sort())
  const { signature, timestamp } = await sign(tenant.secret, body)

  const response = await fetch(
    `${tenant.url}/api/method/oneapp.oneapp_core.email.inbound.receive`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-OneApp-Signature': signature,
        'X-OneApp-Timestamp': timestamp,
      },
      body,
    },
  )

  if (!response.ok) {
    // Throwing tells Cloudflare to retry. The site dedupes on message_id, so a
    // retry after a partial success is harmless.
    throw new Error(`Delivery failed ${response.status}: ${await response.text()}`)
  }
}
