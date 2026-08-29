/**
 * Outbound mail for OneApp tenants.
 *
 * Only needed if Cloudflare's email sending is binding-only. If it exposes SMTP
 * credentials, configure a Frappe Email Account instead and delete this worker —
 * Frappe's own Email Queue already handles batching, retries and unsubscribe
 * better than a shim will.
 *
 * The tenant site signs each request with its own secret, so a leaked worker URL
 * cannot be used to send as anyone.
 */

export default {
  async fetch(request, env) {
    if (request.method !== 'POST') {
      return json({ error: 'Method not allowed' }, 405)
    }

    const body = await request.text()
    const tenantSlug = request.headers.get('X-OneApp-Tenant')

    const tenant = await lookupTenant(env, tenantSlug)
    if (!tenant) return json({ error: 'Unknown tenant' }, 403)

    const valid = await verify(
      tenant.secret,
      body,
      request.headers.get('X-OneApp-Signature'),
      request.headers.get('X-OneApp-Timestamp'),
    )
    if (!valid) return json({ error: 'Invalid signature' }, 403)

    let payload
    try {
      payload = JSON.parse(body)
    } catch {
      return json({ error: 'Malformed body' }, 400)
    }

    // The site claims a sender in its payload, but the signature only proves
    // which tenant it is. Pin the sender to that tenant so a compromised site
    // cannot send as another one.
    const from = `t-${tenantSlug}@${env.MAIL_DOMAIN}`

    try {
      const result = await sendMail(env, { ...payload, from })
      return json({ ok: true, ...result })
    } catch (err) {
      return json({ ok: false, error: String(err).slice(0, 300) }, 502)
    }
  },
}

async function sendMail(env, message) {
  if (!env.MAILER) {
    throw new Error(
      'No MAILER binding configured. Uncomment [[send_email]] in wrangler.toml.',
    )
  }

  const recipients = Array.isArray(message.to) ? message.to : [message.to]
  const sent = []

  for (const recipient of recipients) {
    // Binding surface to confirm against the current Cloudflare docs — this is
    // the one call in the pipeline that is not pinned by a test.
    await env.MAILER.send({
      from: message.from,
      to: recipient,
      replyTo: message.reply_to || undefined,
      subject: message.subject || '',
      html: message.html || undefined,
      text: message.text || undefined,
    })
    sent.push(recipient)
  }

  return { sent: sent.length, recipients: sent }
}

async function lookupTenant(env, slug) {
  if (!slug) return null
  const raw = await env.TENANTS.get(slug)
  if (!raw) return null
  try {
    const tenant = JSON.parse(raw)
    return tenant.secret ? tenant : null
  } catch {
    return null
  }
}

export async function verify(secret, body, signature, timestamp) {
  if (!secret || !signature || !timestamp) return false

  const ts = Number(timestamp)
  if (!Number.isFinite(ts)) return false
  if (Math.abs(Date.now() / 1000 - ts) > 300) return false

  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  const mac = await crypto.subtle.sign(
    'HMAC',
    key,
    new TextEncoder().encode(`${ts}.${body}`),
  )
  const expected = [...new Uint8Array(mac)]
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')

  return timingSafeEqual(expected, signature)
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false
  let diff = 0
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i)
  return diff === 0
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
