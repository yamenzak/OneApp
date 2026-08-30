# OneSpace — Development Roadmap

From an empty Frappe Cloud server to a self-provisioning platform, at which point all
remaining work is product features rather than infrastructure.

Companion to [`ARCHITECTURE.md`](ARCHITECTURE.md), which records *what* we decided and why.
This records *in what order we build it*.

---

## Platform inventory

| App | Where | Why |
| --- | --- | --- |
| `frappe` (nightly) | everywhere | framework |
| `erpnext` | tenant sites | the engine under the bespoke solutions |
| `erpnext` | control site | Customer, Sales Invoice, Payment Entry — real books for our own business |
| [`payments`](https://github.com/frappe/payments) | control site | Stripe gateway plumbing (`Stripe Settings`, `Payment Gateway`, `Payment Request`) |
| `oneapp` | tenant sites | the product |
| `oneapp_control` | control site | tenants, shards, plans, credits, provisioning |

The control plane runs ERPNext deliberately. Tenants are Customers, subscriptions and credit
packs produce Sales Invoices and Payment Entries, and our own revenue is bookkept in the same
system we sell — rather than in a bespoke billing table we would have to reconcile by hand.

---

## What Frappe Cloud gives us for provisioning

Frappe Cloud runs [`press`](https://github.com/frappe/press), which drives a per-server
`agent` daemon. **We are a press *customer*, not its operator** — we never talk to `agent`
directly. Press's whitelisted HTTP API is our entire provisioning boundary, authenticated as
any Frappe API is:

```
Authorization: token <api_key>:<api_secret>
```

Confirmed against `press/api/` at the time of writing:

| Need | Method |
| --- | --- |
| Create a site | `press.api.site.new({name, domain, group, server, cluster, apps, plan})` → `{site, job}` |
| Subdomain availability | `press.api.site.exists(subdomain, domain)` |
| Poll provisioning | `press.api.site.job(job)` → `Undelivered / Pending / Running / Success / Failure / Delivery Failure` |
| Lifecycle | `press.api.site.backup / archive / migrate / activate / deactivate / reinstall / restore` |
| Plan change | `press.api.site.change_plan(name, plan)` |
| Support impersonation | `press.api.site.login(name, reason)` |
| Custom domains | `press.api.client.run_doc_method("Site", name, "add_domain" \| "set_host_name" \| "remove_domain", args)` |
| Anything else | `press.api.client.get_list / get / insert / set_value / delete` |

Two findings worth designing around:

- **`Root Domain` + wildcard `TLS Certificate`** is a first-class press concept
  (`proxy.setup_wildcard_hosts()`), which confirms the `*.4dl.app` approach in
  ARCHITECTURE §2. On *hosted* Frappe Cloud this is press-side configuration, so it is a
  support request to Frappe rather than something we can call. **Confirm this early — it
  gates Phase 0.**
- **`Site.is_standby` / `standby_for_product`** — press natively supports a pool of
  pre-created sites claimed instantly at signup. A fresh ERPNext install takes minutes; a
  claimed standby site is immediate. This is the difference between a signup that feels
  broken and one that doesn't. Deferred to Phase 7, but the provisioning engine is built to
  accommodate it from the start.

Press API rate limits are undocumented to us. Every provisioning operation is therefore
idempotent and retry-safe by construction, not by later patching.

**Nothing here is blocked on Frappe support.** Sites can be provisioned today in
per-tenant domain mode: create on Frappe Cloud's root domain, add a DNS-only
CNAME through the Cloudflare API, attach our hostname with `add_domain`, wait for
the certificate, set it primary.

The wildcard root domain remains worth requesting, but as a scaling move rather
than a prerequisite: Let's Encrypt allows 50 certificates per registered domain
per 7 days, so per-tenant certificates cap signups at roughly 50 per week and add
a renewal per tenant. `Shard.domain_mode` selects between the two, so adopting
the wildcard later is a field change.

---

## Phase 0 — Foundations

Mostly account setup, not code. Blocks everything.

- Frappe Cloud server; bench group on nightly `frappe` + `erpnext` + `oneapp`
  (frappe `develop` is v17 and requires **Python 3.14** — Frappe Cloud handles this;
  a local bench needs `uv python install 3.14`, or [`pilot`](https://github.com/frappe/pilot),
  which manages the interpreter for you)
- Separate bench group for the control plane: `frappe` + `erpnext` + `payments` + `oneapp_control`
- `*.4dl.app` DNS → server; root domain + wildcard certificate configured with Frappe (see above)
- Control-plane site created by hand at `admin.4dl.app`
- Press API key + secret issued and stored
- Cloudflare: R2 bucket, `cdn.4dl.app`, email routing zone, AI Gateway
- Stripe account in test mode
- Cloudflare: DNS zone id and a `Zone.DNS: Edit` token, for per-tenant domain mode
- Optionally request a wildcard root domain from Frappe support (see above) — a
  scaling improvement, not a prerequisite

**Exit:** control site reachable; a script of ours can call `press.api.site.exists` and get an
answer back.

## Phase 1 — Control-plane data model

- `Shard`, `Tenant`, `Plan`, `Subscription`, `Space Entitlement`, `Provisioning Job`,
  `Credit Ledger Entry`
- `Tenant` ↔ ERPNext `Customer` link
- Slug validation with the reserved-name blocklist
- HMAC request signing helper, both directions

**Exit:** a Tenant can be created by hand in the desk UI, with no automation behind it yet.

## Phase 2 — Provisioning engine

The keystone phase.

- Press API client wrapper with retry and error classification
- `Provisioning Job` as an explicit state machine — `Requested → Creating → Bootstrapping →
  Active`, plus `Failed` with a resumable cursor. Idempotent at every step so a retry after a
  timeout never double-creates
- Agent-job polling with backoff
- Site bootstrap: inject `site_config.json` (tenant id, control-plane URL, HMAC secret),
  create the owner user, mark the setup wizard complete
- Lifecycle operations: suspend, resume, backup, archive
- Custom domain add / verify / set-primary via `run_doc_method`

**Exit:** one API call on the control plane produces a working, reachable tenant site with the
owner able to log in. **This is the milestone that makes everything after it routine.**

## Phase 3 — Identity and the app shell

- `oneapp` SPA: Frappe UI, Vite build, router, auth against the same-origin session
- App registry and manifest; launcher UI
- Entitlement enforcement via `has_permission` on module, with the SPA reading the manifest
- Entitlement and balance cache on the tenant site, refreshed from the control plane
- Signup flow on the marketing surface → provision → redirect into the new site

**Exit:** sign up from a landing page, land in a working tenant site, see only entitled apps.

## Phase 4 — Billing

- `payments` configured with Stripe on the control site
- **Credit packs** → `Payment Request` → Stripe Checkout (one-off)
- **Subscriptions** → Stripe Checkout in subscription mode. Stripe owns the recurring
  schedule, dunning, SCA and card updates; we do not rebuild any of it
- Webhook endpoint for `invoice.paid`, `invoice.payment_failed`,
  `customer.subscription.updated/deleted` → drives `Subscription` state and credit grants
- Mirror into ERPNext: Customer, Sales Invoice, Payment Entry
- Seat and storage quota enforcement from the active plan
- Dunning → suspend (site deactivate), then archive with an export window

**Exit:** a real card in test mode produces a paid tenant with a credit grant, and a failed
renewal suspends it.

## Phase 5 — Credits and AI

- Append-only ledger; balance as a sum of unexpired entries
- `reserve → execute → commit/release`, verified under concurrent load
- Grant expiry at period end; consumption order soonest-expiring first, packs last
- Cloudflare AI Gateway integration, provider behind an interface
- Per-request tenant tagging and cost reconciliation against gateway logs

**Exit:** parallel AI calls debit correctly, grants expire on schedule, gateway spend
reconciles against the ledger.

## Phase 6 — Storage and email

- `File` doctype override → R2; presigned redirect for private, `cdn.4dl.app` for public
- Quota counter, rollup to control plane, hard block at upload
- Backup sync to R2 alongside Frappe Cloud's own
- Inbound: Cloudflare catch-all → Worker → HMAC POST → tenant site; `ap@`, `support@`, `leads@`
- Outbound: Cloudflare Email Service over SMTP, wired as a Frappe `Email Account`
- Per-tenant send rate limits, bounce and complaint handling

**Exit:** attachments live in R2, quotas block at the limit, a supplier invoice email creates a
document on the right tenant.

## Phase 7 — Operations

What turns this from working into operable.

- **Standby site pool** so signup is instant rather than minutes
- **Canary bench** carrying internal tenants, plus a written deploy runbook: canary → wave →
  fleet
- Support impersonation via `press.api.site.login`, audit-logged
- Restore rehearsal — an untested backup is not a backup
- Monitoring: provisioning failure rate, quota breaches, credit anomalies, email bounce rate
- Tenant offboarding: export, then archive

**Exit:** onboarding and offboarding a tenant requires no terminal.

---

## Then: the apps

With Phase 7 done, adding a bespoke app is a module, a manifest entry and an entitlement row.
No infrastructure work. That is the point of everything above.

---

## Sequencing notes

- **Phase 2 is the keystone.** Phases 3–7 all assume a tenant site can be created on demand.
- **Phase 4 is unblocked.** The pricing questions are answered (ARCHITECTURE §11);
  what remains is choosing the plan ladder above the $22 entry and sizing the
  credit grant against measured model cost. Both are data, not schema.
- **Phases 5 and 6 are independent of each other** and can be built in either order, or in
  parallel.
- **Phase 3 can start alongside Phase 2** — the SPA shell can be developed against a
  hand-created site before provisioning is automated.
- Do not defer Phase 7's canary bench until the end if tenant count grows quickly. The moment
  there are paying tenants, deploying straight to the fleet stops being acceptable.
