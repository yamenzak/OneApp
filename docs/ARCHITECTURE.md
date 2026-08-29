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

Two ways to get a tenant onto that hostname, selected per shard by
`Shard.domain_mode`:

**Per-tenant** (default, works today). The site is created on Frappe Cloud's own
root domain; we then create a DNS-only CNAME, ask press to add our hostname, wait
for its certificate, and set it primary. Every API in that chain is one we can
call ourselves, so it needs nothing from Frappe support.

**Wildcard** (the destination). `*.4dl.app` is registered as a root domain on the
server with a wildcard certificate, and sites are created directly on it —
provisioning becomes a single call with no DNS work, no certificate wait and no
failure mode. On hosted Frappe Cloud this is press-side configuration, so it is a
support request rather than an API call.

**Why both exist.** Let's Encrypt allows **50 certificates per registered domain
per 7 days**. `4dl.app` is one registered domain, so per-tenant certificates cap
signups at roughly 50 per week and add a renewal for every tenant, each one able
to fail on its own. A wildcard is a single certificate covering all of them. Per-
tenant is the right way to start and the wrong way to scale, which is why the
mode is a field on Shard: switching later is data, not a rewrite.

Tenant traffic is **DNS-only (grey cloud)** in both modes; Frappe Cloud terminates
TLS. Proxying breaks certificate validation, because the hostname then resolves
to Cloudflare's IPs rather than the origin press is trying to reach.

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

**The desk is not used at all** — not by customers, and not by us. See DECISIONS §7.

### Surfaces

Three, across two SPAs:

| Route | Site | Who | Served by |
| --- | --- | --- | --- |
| `/one` | tenant | the workspace's users | `oneapp` |
| `/admin` | control | us | `oneapp_control` |
| `/portal` | control | customers: signup, billing, domains | `oneapp_control` |

`/admin` and `/portal` are **one built bundle behind two website routes**. Sharing the build
is what keeps the component set, error handling and socket wiring from drifting into two
frontends; the separate routes are what let `www/admin.py` require System Manager while
`www/portal.py` admits a visitor with no session — otherwise nobody could sign up.

Because one bundle answers on two paths, the Vue router's history base is `/` and every route
carries its own prefix. A base of `/admin` would mis-resolve every URL under `/portal`.

### Layout

Rail → sidebar → content, the frappe-ui shell pattern:

| Region | Tenant SPA | Control `/admin` | Control `/portal` |
| --- | --- | --- | --- |
| **Rail** | the workspace's apps | none — one surface | the customer's workspaces |
| **Sidebar** | sections of the active app | console sections | account sections |
| **Content** | whatever the sidebar selected | | |

Every sidebar entry is its own route, never a tab index: an entry you cannot
link to is one you cannot send to someone.

**`AppShell` is the only component allowed to compose the layout primitives.**
`DesktopShell` and `MobileShell` are different components with different slots,
so something has to choose between them — and a surface choosing for itself is
how one account comes to look like two products on the same tablet. It is
generated into both apps, guarded by an eslint rule on the imports and a test on
the markup.

`MobileShell` has no rail slot, so below 768px app switching would simply
disappear. `AppShell` puts it in a `BottomSheet` opened from the bottom bar —
a touch target per app rather than a menu row.

Appearance is a three-way `ThemeSwitcher` (light / dark / system) in settings,
not a toggle in the user menu. A two-state toggle cannot express "follow the
system", so anyone wanting that ends up flipping it by hand twice a day.

### The frappe-ui API is read, not remembered

Every UI defect found in this project so far was the same mistake: giving a
component a prop, a slot, or an option it does not declare. Vue turns an unknown
prop into a fallthrough attribute on the root element and never renders an
unknown slot, and `useCall` ignores option keys it does not know. Nothing throws,
nothing logs, the page loads — and the thing is simply missing. Eight page
headers were empty, eight lists rendered zero rows beside a correct count, three
dialogs opened with no title and no body, nine alerts dropped their text, and
three sidebars lost their footers, all without a single error.

So `tests/frappe_ui_api.py` reads the declarations out of the installed package,
and four checks compare them against what we write:

| Check | Catches |
| --- | --- |
| unknown props | `<Alert variant>` when the prop is `theme` |
| unknown slots | `<Dialog #body-content>` when the body is the default slot |
| content with nowhere to go | `<Alert>body</Alert>` when Alert has no default slot |
| missing required props | `<ListRows>` with no `:items` |
| values outside a union | `<Badge theme="orange">` when the themes are gray…violet |
| unknown call options | `useResource(…, { enabled })` when the option is `immediate` |
| deprecated components | re-exporting `ThemeSwitcher` after 1.0 replaced it |
| a local component shadowing one | a `Badge.vue` of our own beside the barrel's |
| markup pretending to be a component | a page built from `<div>`s and raw palette colours |
| verbs and whitelists | POSTing to a method whitelisted `methods=["GET"]` |

**We are on `1.0.0-beta.55`, and npm's `latest` tag still points at the `0.1.x`
line.** That is why v0 API shapes keep appearing — `Dialog :options`,
`#body-content`, `Dropdown placement` are all what the older, still-default
package documents. The checks compare against the version actually installed,
so the answer is never a matter of which docs someone happened to read.

There is no blanket exemption for components that forward attributes with
`useAttrs()`. That was the first shape of this guard, and it turned the check
off for Button, Dropdown, Avatar, Tooltip and the whole form-control family —
which is how `<Dropdown placement="top-start">` survived on three surfaces even
though frappe-ui removed `placement` in 1.0 and warns about it in dev. What each
forwarding component may legitimately be handed is an explicit list instead.

frappe-ui declares components four different ways — an inline `defineProps<{…}>`
literal, a named type in `types.ts`, a runtime props object, and the options API
— plus `defineModel('open')` for named v-models. A reader that understands only
some of them reports the rest as taking nothing, which reads exactly like a clean
run, so `tests/test_frappe_ui_usage.py` pins one component per form.

Upgrading frappe-ui runs these against the new declarations. A renamed prop
fails the suite instead of quietly emptying a page.

The guards sweep `apps/*/frontend/src`, which covers all four surfaces — the
tenant workspace, the operator console, customer self-service and signup. Each
is named in `tests/test_frappe_ui_usage.py` with a file that must exist, so a
fifth surface added somewhere the sweep does not reach fails rather than going
unguarded.

### Geometry comes from the family's own hooks

`SidebarItem` is a full-width rounded row with no gutter, so the scroll region
around it supplies one (`viewport-class="px-2"`, as frappe-ui's own sidebar
stories do) — without it the active row's surface runs edge to edge and its
shadow is clipped. Lists share a content inset between header and rows through
`--list-row-padding-x` (the `list-row-px-*` utility); frappe-ui pads only
interactive rows, so a static list sets its own vertical rhythm.

`SettingsRow` is label-left, control-right, with the control `shrink-0`. That is
the shape for a `Switch` or a `Select`. A full-width text input in one collapses
the label to a word per line on a phone, so settings forms stack `FormControl`s
directly in `SettingsBody` — which is what Gameplan's own profile panel does.

**SettingsDialog is not responsive in `1.0.0-beta.55`**, despite documenting
itself as full-screen on mobile. Measured at 390px: the Dialog's own chrome
(`px-4 py-4` on the scroll container, `my-8` on the content) leaves the
`w-screen` panel clipped by 16px, `SettingsHeader` and `SettingsBody` both pad
`px-[4.4rem]` with no responsive variant — 141px of a 390px screen — and the tab
sidebar takes `max-h-[38vh]`. Frappe's own consumers, Gameplan and Pilot, are
desktop-first and never hit it, so there is nothing upstream to copy. One scoped
block in `index.css` corrects the three, keyed to Dialog's named
`.dialog-scroll-container` / `.dialog-content` hooks and ScrollArea's
`data-slot`, and `tests/test_settings_dialog_geometry.py` pins each upstream
value it compensates for so the override cannot outlive the problem.

A `bare` Dialog renders no close button, which on a full-screen phone dialog
leaves Escape as the only exit — and a phone has no Escape. `SettingsShell` adds
one, `sm:hidden`, since desktop still has a backdrop to click.

### Status trails, it does not lead

Every list here puts its `Badge` in a trailing cell. The readiness page led with
one, which indented every check name behind a column of identical pills and put
a repeated word where the eye lands first. Frappe-ui's own list stories lead
with identity — an avatar and a name — for the same reason.

Every customer-facing URL the server builds — Stripe return URLs, signup links, the billing
portal — comes from `oneapp_control/portal.py`, and `tests/test_portal_urls.py` parses the
router to prove they resolve. Nothing fails loudly when those disagree: Stripe accepts any
URL and the redirect succeeds, so the customer lands on a 404 holding a receipt.

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

Enforcement is a `before_insert` hook on `File`, **at upload time** — warn at 80%, hard block
at 100%. Never auto-delete. A tenant discovering they are 3 GB over after the fact is a worse
experience than a clear rejection at the moment of upload.

**Database size** is capped separately, by `Plan.database_gb`, and it is the cap that actually
constrains how many sites fit on a server. Over the limit, *inserts* pause; updates and
deletes keep working, so deleting something is always a way back out. Recovery doctypes are
exempt — Frappe writes a `Deleted Document` when you delete, and blocking that would block the
only escape — as are installs, migrations and patches.

Measuring the database is an `information_schema` scan over ~1,200 tables, far too expensive
for a hook that runs on every insert on the site. It is measured hourly and only the verdict
is read per insert. An absent verdict reads as *not over*, so a stopped scheduler unblocks
rather than freezes.

**Background job concurrency** is capped by `Plan.background_workers`, counted from RQ rather
than a counter of our own — a counter has to be decremented by something, and a worker killed
mid-job never decrements it. Counting fails open: a Redis blip must not become an outage. See
DECISIONS §6 for what plan-based priority can and cannot do.

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

## 9. Repository layout

**One monorepo, two Frappe apps, published to generated mirrors.**

Frappe is one-app-per-repo by construction: `bench get-app` expects the repository root to be
the app root, and a Frappe Cloud bench group is a list of `(repo URL, branch)` pairs. There is
no subdirectory option.

The apps are nonetheless kept in a single repository — `yamenzak/OneApp` — because day-to-day
development, particularly in repo-scoped tooling, is significantly better with one checkout.
CI publishes each app subdirectory to a standalone mirror that Frappe Cloud consumes:

| Source | Mirror | Consumed by |
| --- | --- | --- |
| `apps/oneapp` | `yamenzak/oneapp-app` | tenant bench groups |
| `apps/oneapp_control` | `yamenzak/oneapp-control` | control-plane bench |

Mirrors are build artifacts. They are never committed to directly, and their READMEs say so.
Branch names are preserved through the sync, so pushing `canary` updates `canary` on both
mirrors and a canary bench group tracks it without extra configuration.

Local development symlinks `apps/*` into a bench, so there is no sync step while working.

**The two apps stay separate deployment artifacts**, which is the point that matters. Combining
them into one app — or gating a single app by role via `site_config` — would mean every
control-plane change (billing, provisioning, credit logic, all of which iterate fast) ships as
a new tenant-app version and triggers `bench migrate` across every tenant site. It would also
place `Credit Ledger Entry`, `Tenant` and Frappe Cloud credential doctypes as real tables on
customer-administered sites, undoing the boundary §4 exists to create.

Shared code between the two is limited to HMAC signing and the request/response contract. That
is duplicated deliberately: the two sites deploy on independent schedules, so the tenant side
must tolerate a control plane running a version ahead.

---

## 10. Cost model

The Frappe Cloud server plan is the whole server — **unlimited benches and sites,
no per-site charge**. Infrastructure cost per tenant is therefore purely the
server divided by how many tenants fit on it.

At ~30 tenants on a $40 cpx22:

| Line | Per tenant / month |
| --- | --- |
| Server ($40 / 30) | ~$1.33 |
| R2 (10 GB @ $0.015/GB, zero egress) | ~$0.15 |
| Email (Cloudflare Email Service) | ~$0.05 |
| AI Gateway | $0 (model cost is separate) |
| **Total** | **~$1.53** |

Against a $22 entry tier that is roughly 7% of revenue, and it improves as a
server fills: the same $40 across 40 tenants is $1.00 each.

Because there is no per-site fee, the economic pressure is entirely on **how many
sites fit before MariaDB degrades** (§1), not on anything Frappe Cloud bills. That
makes the capacity numbers in §1 the figure to watch, and adding a second server
a capacity decision rather than a pricing one.

The margin variable is the **AI credit grant inside each plan**, not
infrastructure — which is why per-tenant AI Gateway logging is wired in from day
one rather than retrofitted.

---

## 11. Resolved questions

Three questions gated pricing rather than design. All are now answered, and none
changed the architecture.

1. **Does Frappe Cloud bill per-site plans on our own server?** No. The server
   plan covers unlimited benches and sites. Capacity, not billing, sets the
   tenant ceiling.
2. **Is the server price app-server-only?** No. $40 is the entire server.
3. **Does Cloudflare email sending expose SMTP?** Yes —
   `smtps://smtp.mx.cloudflare.net:465`, authenticating as `api_token` with a
   token carrying *Email Sending: Edit*. Frappe therefore sends through its own
   Email Queue and the outbound Worker shim was deleted rather than built. A REST
   API and a Workers binding also exist if SMTP is ever blocked.

---

## 12. Build order

Superseded in detail by [`ROADMAP.md`](ROADMAP.md); the summary:

1. Control-plane doctypes — `Tenant`, `Shard`, `Plan`, `Subscription`, `App Entitlement`
2. Frappe Cloud provisioning job (idempotent, retryable)
3. `oneapp` skeleton + Frappe UI SPA shell + auth
4. R2 file layer and quota enforcement
5. Credit ledger and reserve/commit
6. Email, both directions
