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

Addresses are `<tenant>.<local>@<mail domain>` — the tenant is in the local
part, not the hostname, because a zone may have at most 30 domains configured
for Email Routing or Sending and there is no wildcard. `docs/EMAIL.md` §1a is
the whole argument. `src/routing.js` is kept dependency-free so that decision is
testable in plain node:

```bash
node --test workers/email-inbound/test/routing.test.mjs
```

## Deploying

Normally you do not. The control plane does it — **Bring up mail** on the
readiness screen creates the KV namespace, uploads this worker with its
bindings, enables Email Routing and points the catch-all at it, all from one
account token. See `oneapp_control/api/admin/mail.py`.

What that uploads is the bundle, not this directory: Cloudflare's script API
takes one file, `postal-mime` is an import, and a deployed control plane has no
`workers/` on disk. So after changing anything here:

```bash
cd workers/email-inbound && npm install && npm run build
```

which writes `apps/oneapp_control/oneapp_control/cloudflare/worker/`.
`tests/test_worker_bundle.py` fails if you forget.

`wrangler deploy` still works for local iteration — fill in the namespace id in
`wrangler.toml` first — but it is not how production gets its worker.
