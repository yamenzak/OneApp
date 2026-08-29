# Cloudflare Workers

One worker sits between Cloudflare and the tenant sites.

| Worker | Purpose |
| --- | --- |
| `email-inbound` | Email Routing catch-all → parse MIME → HMAC-POST to the tenant's site |

There is no outbound worker. Cloudflare Email Service exposes SMTP
(`smtps://smtp.mx.cloudflare.net:465`, user `api_token`), so tenant sites send
through Frappe's own Email Queue — which already handles batching, retries,
unsubscribe and attachments better than a shim would.

## Tenant map

The worker reads a KV namespace binding `TENANTS`:

```
key:   acme
value: {"url": "https://acme.4dl.app", "secret": "<tenant hmac secret>"}
```

Written by the control plane when a tenant is provisioned. KV rather than a
lookup call to the control plane on purpose: a control-plane outage should not
bounce customer mail.

Addresses are `<local>@<tenant>.t.4dl.app`, so routing is decided from the
hostname alone. `src/routing.js` is kept dependency-free so that decision is
testable in plain node:

```bash
node --test workers/email-inbound/test/routing.test.mjs
```

## Setup

1. `wrangler kv namespace create TENANTS`, then put the id in `wrangler.toml`.
2. Point Email Routing's catch-all for `t.4dl.app` at `oneapp-email-inbound`.
3. `npm install && npm run deploy`.
