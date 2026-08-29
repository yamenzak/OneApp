# Cloudflare Workers

Two workers sit between Cloudflare and the tenant sites.

| Worker | Purpose |
| --- | --- |
| `email-inbound` | Email Routing catch-all → parse MIME → HMAC-POST to the tenant's site |
| `mail-send` | Outbound shim, only needed if Cloudflare email sending is binding-only |

## Shared tenant map

Both read a KV namespace binding `TENANTS`:

```
key:   acme
value: {"url": "https://acme.4dl.app", "secret": "<tenant hmac secret>"}
```

Written by the control plane when a tenant is provisioned. It is KV rather than a
lookup call to the control plane on purpose: a control-plane outage should not
bounce customer mail.

Addresses are `<local>@<tenant>.t.4dl.app`, so routing is decided from the
hostname alone.

## Setup

1. `wrangler kv namespace create TENANTS`, then put the id in both `wrangler.toml` files.
2. Point Email Routing's catch-all for `t.4dl.app` at `oneapp-email-inbound`.
3. `npm install && npm run deploy` in each directory.

## Outbound

`mail-send` is only needed if Cloudflare's email sending is binding-only. If it
exposes SMTP credentials, configure a Frappe Email Account instead and delete
this worker — Frappe's Email Queue already handles batching, retries and
unsubscribe better than a shim will.

The `[[send_email]]` binding is commented out in `wrangler.toml` and the
`env.MAILER.send(...)` call is the one step in the pipeline not pinned by a test.
Confirm both against the current Cloudflare docs before deploying.
