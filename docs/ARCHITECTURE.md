# OneApp — Architecture Decisions

Status: agreed, pre-implementation.

OneApp is a single Frappe application presenting a unified SPA over multiple bespoke
solutions, with ERPNext underneath. Customers never see Frappe or ERPNext — the SPA is
their only access point.

---

## 1. Tenancy

**One Frappe site per tenant.**

Shared-site multi-tenancy (a tenant field on every doctype + permission query conditions)
is rejected: ERPNext masters — Item, Customer, Account, Warehouse — are site-global, and a
single missed `ignore_permissions=True` anywhere in ~1,200 doctypes we don't own is a
cross-tenant data breach.

Site-per-tenant gives us real isolation, per-tenant backup/restore/export, natural storage
accounting, and the ability to enable a bespoke app for one tenant without touching anyone
else.

### Shards

Every tenant records **which server + bench its site lives on**:

```
Tenant.shard → Shard (server, bench)
```

This is the address book behind every operation: provisioning (which server?), backup and
restore, suspend/delete, deploy ordering, log lookup, and moving a heavy tenant to a bigger
box. With one server today it is a single row — but adding server #2 later without it means
backfilling a tenant→server mapping across a live system and rewriting every provisioning,
backup and deploy path.

### Benches as deploy rings

Multiple benches per server are a safety mechanism, not just capacity. Internal and beta
tenants live on a `canary` bench that migrates first; customers roll in waves. This matters
because `bench migrate` runs **per site** — a few hundred sites is a multi-hour deploy
window, and a bad nightly caught on the canary is minutes to unwind instead of hours.

### Capacity

MariaDB is the ceiling, not Frappe and not any Frappe Cloud limit. A fresh ERPNext site is
~150–250 MB with ~1,200 tables before any real data. Practical guide:

| Server | RAM | Disk | Active tenants |
|---|---|---|---|
| cpx22 ($40) | 4 GB | 80 GB | ~20–40 |
| cpx42 ($140) | 16 GB | 320 GB | ~80–150 |
| cpx62 ($260) | 32 GB | 640 GB | ~150–250 |

Disk fills before CPU does.

### Bench composition

One bench group for everyone: `frappe + erpnext + oneapp`. Uniform deploys are worth the
wasted schema on tenants who don't use ERPNext features.

---

## 2. Domains and TLS

**Tenant sites: `<tenant>.4dl.app`.** Flat, single wildcard level.

`*.4dl.app` is registered as a **wildcard domain on the Frappe Cloud server**, with FC
holding a scoped Cloudflare API token to complete the DNS-01 challenge. Consequence:
provisioning a tenant is just "create site" — no per-tenant DNS call, no certificate
issuance, no async wait, no failure mode.

Tenant traffic is **DNS-only (grey cloud)**; Frappe Cloud terminates TLS. Cloudflare proxying
is used for surfaces that benefit from it — marketing site, Workers, `cdn.4dl.app` — not for
authenticated app traffic.

`fourdegreelabs.com` remains the corporate/marketing brand. `4dl.app` is the product surface.

### Reserved slugs

`*.4dl.app` resolves for anything, so tenant slugs are validated against a blocklist at
signup: `www`, `api`, `cdn`, `admin`, `app`, `mail`, `one`, `status`, `docs`, `support`,
`billing`, plus profanity and anything phishable.

### Customer-owned custom domains

Handled by Frappe Cloud's Add Domain API, on demand and asynchronously:

1. Customer CNAMEs `erp.acmecorp.com` → `acme.4dl.app`
2. FC verifies the CNAME and issues the certificate
3. Set as primary; other domains redirect to it

Constraints to surface in our UI copy, since they are the predictable support tickets:

- **The CNAME must be DNS-only.** If the customer proxies it through Cloudflare it resolves
  to Cloudflare IPs rather than `acme.4dl.app`, and FC verification and cert issuance fail.
- **Subdomains only.** Apex domains cannot CNAME.

**`acme.4dl.app` remains the permanent internal address.** The control plane, webhooks, and
inbound email routing always address that hostname — never the custom domain, which the
customer owns and can break or remove.

---

## 3. Frontend

**The SPA is served from the Frappe app**, built with Vite into `oneapp/public/frontend` and
routed via `website_route_rules` under a prefix that does not collide with the desk at
`/app`.

Rationale, in order of weight:

1. **No deploy skew.** Each site serves exactly the frontend matching its own backend. An
   edge-hosted SPA against per-site backends means, during any rolling migration, a new
   frontend talking to a not-yet-migrated site.
2. **Auth.** Frappe's session is a same-origin `sid` cookie — no CORS, no token exchange, no
   refresh dance.
3. Frappe UI is built for this: doctype metadata, permissions, and file uploads come free.

The desk UI ships too, gated to admins, for support work.

A Cloudflare Worker serves only the **unauthenticated** surface: landing, signup, and tenant
lookup/redirect. It has no backend coupling.

---

## 4. Control plane

**A separate site running a separate app (`oneapp_control`)** — not a module inside tenant
sites gated by an environment variable. Env gating is one System Manager role away from being
no gating, and it would place billing records, the credit ledger, and our Frappe Cloud API
token on machines customers administer.

Owns:

- `Tenant`, `Shard`, `Plan`, `Subscription`
- `Credit Ledger Entry` (append-only)
- `App Entitlement`
- `Provisioning Job` (FC API orchestration; idempotent and retryable)
- Storage usage rollups, Frappe Cloud credentials, feature flags

Tenant sites hold a **cached** copy of their own entitlements and credit balance, refreshed on
a schedule and on demand. Anything authoritative is an HMAC-signed call to the control plane;
control-plane → tenant calls are signed the same way, with a per-tenant secret in
`site_config.json`.

This keeps tenant sites dumb and disposable, which is what you want when restoring one at 2am.

---

## 5. Storage

**User attachments go to Cloudflare R2**, via an override of the `File` doctype. Objects are
keyed `tenants/<tenant_id>/…`.

- **Private files** — the route runs Frappe's permission check on the attached document, then
  302s to a short-TTL presigned R2 URL.
- **Public files** — served from a public bucket behind `cdn.4dl.app`.

### Quotas

R2 exposes no per-prefix usage metric, so we maintain the counter ourselves: sum of
`File.file_size` per site, rolled up to the control plane on a schedule.

Enforcement is in the `File` validate hook **at upload time** — warn at 80%, hard block at
100%. Never auto-delete. A tenant discovering they are 3 GB over after the fact is a worse
experience than a clear rejection at the moment of upload.

### Backups

Frappe Cloud's managed backups **and** an independent sync to R2. Two custodians.

---

## 6. Email

Cloudflare handles both directions.

### Inbound

Catch-all → Worker → parse recipient → HMAC POST to the correct tenant site.

Per-tenant **functional** addresses: `ap@` (supplier invoice ingestion — the highest-value
one, given ERPNext underneath), `support@`, `leads@`.

Per-user mailboxes are explicitly out of scope. That is a mailbox product — spam filtering,
storage quotas, IMAP expectations, abuse handling — not a feature.

### Outbound

Cloudflare email sending, verified working.

If Cloudflare exposes SMTP credentials, an outgoing `Email Account` per site is all that is
required. If it is Workers-binding-only, `oneapp` overrides Frappe's outbound sender to
HMAC-POST the rendered message to a Worker, which sends and posts delivery/bounce status back.
See open questions.

Ours to build regardless of provider: **per-tenant send rate limits**, bounce and complaint
handling, and DMARC on the sending domain. On a shared sending identity, one tenant importing
a purchased list degrades deliverability for everyone.

---

## 7. AI and credits

**Cloudflare AI Gateway is the gateway, not the model provider.** Gemini and others sit behind
it. We get caching, rate limiting, retries, and — critically — per-request logging tagged with
tenant ID for cost attribution. Workers AI local models are a cost lever for bulk work
(classification, embeddings, summarization), not the primary path.

Providers sit behind an interface so a task type can move between models on measured cost.

### Ledger

Lives **only** in the control plane. Append-only entries; balance is a sum, never a mutable
field.

Spending uses **reserve → execute → commit/release**: reserve an estimated maximum before the
call, commit actual usage after, release on failure. Without this, two concurrent requests both
read the same balance and both spend it.

### Non-rollover grants

Modelled as ledger entries with `expires_on = period_end`; balance is the sum of unexpired
entries.

Consumption order: **soonest-expiring grant first, purchased packs last.** Packs roll over —
that is what makes them worth buying.

---

## 8. Plans, apps and entitlements

**Plan = quotas only**: storage, seats, background job concurrency, credit grant. No feature
flags. Every feature is available on every plan.

**App entitlement is orthogonal to plan.** That is the mechanism for bespoke single-tenant
solutions.

Each app is a **Frappe module inside `oneapp`**, with a manifest (id, label, icon, routes,
entitlement key). The SPA fetches the manifest and renders the launcher; each workspace picks
from the apps it is entitled to.

Every app's code ships to every site, gated rather than absent. Per-tenant benches would
multiply the deploy problem by the customer count.

Entitlements are enforced **server-side** via a `has_permission` hook keyed on the doctype's
module. Hiding a nav item is a UX affordance, never a boundary.

---

## 9. Cost model

At ~30 tenants on a $40 cpx22:

| Line | Per tenant / month |
|---|---|
| Server | ~$1.35 |
| R2 (10 GB @ $0.015/GB, zero egress) | ~$0.15 |
| Email routing + sending | ~$0.05 |
| AI Gateway | $0 (model cost is separate) |
| **Total** | **~$1.60** |

Against a $22 entry tier, infrastructure is noise. The margin variable is the **AI credit grant
inside each plan**, not infrastructure — which is why per-tenant AI Gateway logging is wired in
from day one rather than retrofitted.

---

## 10. Open questions

Pricing inputs, not architecture. None of them change the design above.

1. **Does Frappe Cloud bill per-site plans on our own dedicated server?** At even $5/site this
   is 3× total infrastructure cost and reshapes the entry tier.
2. **Is the quoted server price app-server-only, with the database server billed separately?**
   Likely a ~$80 real floor rather than $40.
3. **Does Cloudflare email sending expose SMTP credentials, or only a Workers binding?**
   SMTP → configure an `Email Account`. Binding-only → build the outbound shim (§6).

---

## 11. Build order

1. Control-plane doctypes — `Tenant`, `Shard`, `Plan`, `Subscription`, `App Entitlement`
2. Frappe Cloud provisioning job (idempotent, retryable)
3. `oneapp` skeleton + Frappe UI SPA shell + auth
4. R2 file layer and quota enforcement
5. Credit ledger and reserve/commit
6. Email, both directions
