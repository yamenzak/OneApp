# OneAdmin

The platform behind OneSpace: where tenants come from, what they cost, what
happens when nobody pays, and the console we run it from.

The customer-facing half is `ONESPACE.md`. This is everything a customer never
sees, plus how to bring it up and how to work on it.

---

## 1. Two apps, one repository

| Source | Mirror | Consumed by |
|---|---|---|
| `apps/oneapp` | `yamenzak/oneapp-app` | tenant bench groups |
| `apps/oneapp_control` | `yamenzak/oneapp-control` | the control-plane bench |

Frappe is one-app-per-repo by construction — `bench get-app` expects the
repository root to be the app root — so CI publishes each subdirectory to a
standalone mirror. Mirrors are build artifacts, never committed to directly.
Branch names are preserved, so pushing `canary` updates `canary` on both.

**The two apps stay separate deployment artifacts**, which is the point.
Combining them would mean every control-plane change — billing, provisioning,
credit logic, all of which iterate fast — ships as a new tenant-app version and
triggers `bench migrate` across every tenant site. It would also put
`Credit Ledger Entry`, `Tenant` and our Frappe Cloud credentials as real tables
on customer-administered sites.

**The frontends are not separate**, and that is deliberate. `oneapp` is
installed on the control plane too, for its shell and its Space runtime — so the
operator console and the customer's account area are Spaces on the control site
rather than a second SPA. Improvements to the screen machinery reach the console
instead of stopping at the tenant boundary.

A site says which kind it is with `oneapp_role` in `site_config.json`. Three
things gate on it: the R2 File override and the two scheduled jobs that talk to
a control plane the control plane does not have.

Shared code between the apps is limited to HMAC signing and the request
contract, duplicated deliberately: the two deploy on independent schedules, so
the tenant side must tolerate a control plane running a version ahead.

**Routes.** `/one` on every site is the whole product; `/signup` on the control
site is the one page somebody reaches before they have an account. `/admin` and
`/portal` were two SPAs and are gone — an operator and a customer are two Spaces
in one shell, and which opens is decided by the roles they hold.

---

## 2. Tenancy

**One Frappe site per tenant.** Shared-site multi-tenancy is rejected: ERPNext
masters — Item, Customer, Account, Warehouse — are site-global, and a single
missed `ignore_permissions=True` anywhere in ~1,200 doctypes we do not own is a
cross-tenant breach. Site-per-tenant gives real isolation, per-tenant
backup/restore/export, natural storage accounting, and a bespoke app for one
tenant without touching anyone else.

### Shards

Every tenant records **which server and bench its site lives on**
(`Tenant.shard → Shard`). This is the address book behind provisioning, backup,
restore, suspend, delete, deploy ordering and moving a heavy tenant to a bigger
box. With one server it is a single row — but adding server #2 without it means
backfilling a tenant→server mapping across a live system.

**Benches are deploy rings, not just capacity.** `bench migrate` runs *per
site*, so a few hundred sites is a multi-hour window; internal and beta tenants
live on a `canary` bench that migrates first.

**MariaDB is the ceiling**, not Frappe and not any Frappe Cloud limit. A fresh
ERPNext site is 150–250 MB with ~1,200 tables before any data, and disk fills
before CPU does.

| Server | RAM | Disk | Active tenants |
|---|---|---|---|
| cpx22 ($40) | 4 GB | 80 GB | ~20–40 |
| cpx42 ($140) | 16 GB | 320 GB | ~80–150 |
| cpx62 ($260) | 32 GB | 640 GB | ~150–250 |

The shard form reads a server's specs from Frappe Cloud and recommends a soft
cap from that table (7 tenants per GB of RAM, 0.35 per GB of disk). It is a
starting number an operator can change, not a limit.

### Adding capacity

Buy a server, add a bench group, register the pair as a Shard. Nothing else —
the allocator picks it up on the next signup: least-loaded first among shards
that are Active, accepting and under their soft cap. A region becomes selectable
the moment one shard in it has headroom, and stops being offered when none does.

Two shards must never cover one bench group; both would count capacity against
the same machine and the allocator would overfill it. The form refuses.
Draining is `accepts_new_tenants = 0`.

**Reachable is not editable.** A shard's press identity — server, bench group,
version, domain and mode — is what its tenants were created against, so
`update_shard` refuses it. Replacing a shard is registering a new one and
draining the old.

### Regions

Customers pick where their workspace runs; the price does not change. `Region`
groups shards under a name a customer recognises. Adding Frankfurt later is a
Region row and a Shard row, no code.

### Domains and TLS

Tenant sites are `<tenant>.4dl.app` — flat, one wildcard level. Two ways to get
there, per shard via `Shard.domain_mode`:

**Per-tenant** (works today): create the site on Frappe Cloud's root domain, add
a DNS-only CNAME, ask press for our hostname, wait for its certificate, set it
primary. Every API in that chain is one we can call.

**Wildcard** (the destination): `*.4dl.app` registered on the server with a
wildcard certificate, sites created directly on it — one call, no DNS work, no
certificate wait. On hosted Frappe Cloud that is press-side configuration, so it
is a support request.

Why both: Let's Encrypt allows **50 certificates per registered domain per 7
days**, so per-tenant certificates cap signups at roughly 50 a week and add a
renewal that can fail on its own. Per-tenant is the right way to start and the
wrong way to scale, which is why the mode is a field.

Tenant traffic is **DNS-only (grey cloud)** in both modes; Frappe Cloud
terminates TLS. Proxying breaks certificate validation.

Slugs are validated against a blocklist (`www`, `api`, `admin`, `mail`, `one`,
`billing`, plus profanity and anything phishable) because `*.4dl.app` resolves
for anything.

**Customer domains** go through Frappe Cloud's Add Domain API. Two constraints
belong in the UI copy because they are the predictable tickets: the CNAME must
be DNS-only, and apex domains cannot CNAME. `<tenant>.4dl.app` remains the
permanent internal address — webhooks and the control plane always use it, never
the custom domain the customer can break.

---

## 3. The control plane

A separate site running a separate app, not a module gated by an environment
variable. Env gating is one System Manager role away from being no gating, and
it would put billing records, the credit ledger and our Frappe Cloud token on
machines customers administer.

Owns `Tenant`, `Shard`, `Region`, `Plan`, `Subscription`, `Add-on`,
`Credit Pack`, `Promo Code`, `Credit Ledger Entry` (append-only),
`Credit Reservation`, `Space Entitlement`, `Provisioning Job`, `Standby Site`,
`Account Request`, `Storage Bucket`, `Stripe Webhook Event`, `AI Model`,
`AI Feature`, `AI Usage Record`, `Support Login`, `Tenant Lifecycle Event`,
`Workspace Role`.

Tenant sites hold a **cached** copy of their own entitlements and balance,
refreshed every fifteen minutes and on demand. Anything authoritative is an
HMAC-signed call; calls the other way are signed the same, with a per-tenant
secret in `site_config.json`. This keeps tenant sites dumb and disposable, which
is what you want when restoring one at 2am.

**Provisioning** is a `Provisioning Job` — idempotent and retryable, because
half of it is Frappe Cloud API calls that can fail anywhere.

---

## 4. The operator console

`/one` on the control site, as a Space (`entitlements/operator.py`). It was
~6,000 lines of Vue over eighteen doctypes; almost none of it did anything the
screen machinery does not do better, and every improvement to that machinery had
been stopping at the tenant boundary.

So the console is declared the same way a customer's space is: doctypes it may
reach, and screens over them. Editing that file and running a migration is how
the console changes shape.

Twenty-three screens over Tenants, Provisioning, Shards, Standby, Signups,
Subscriptions, Credits, Reservations, Webhooks, Plans, Add-ons, Credit packs,
Promo codes, Regions, Buckets, Spaces, Entitlements, Workspace roles, AI models,
AI features, AI usage, Support logins and Lifecycle.

Three are genuinely not lists and stay `component` screens — which is what that
escape hatch is for: **Readiness** (a checklist with blockers), **Frappe Cloud**
(a live view of press's own state), and **Workspace** (one tenant seen from both
sides at once, reached from Tenants through a declared action).

Declared actions carry what a list cannot: open a workspace, hold and release it
from the lifecycle, apply the lifecycle now, take a cold copy, restore, purge,
move to the plan's current terms, replay a Stripe webhook.

The Space is **Restricted and entitled to nobody**, which is what makes it
operator-only rather than merely hidden. It was General on the argument that
`visible_spaces` narrows by role anyway — both halves true and the conclusion
wrong, because `spaces_for_tenant` hands every General space to every tenant, so
each tenant site was being told to create an `OneSpace Operator` role with
permissions over Tenant, Subscription and the credit ledger.

Beside it, `entitlements/account.py` is the customer's own Space on the same
site: Overview, Apps, Billing, Plan, People, Roles, Domain. No doctypes and no
grant — every screen is a component calling whitelisted methods that resolve the
workspace from the session.

### No desk

**The desk is not part of the product, for customers or for us.** The cost is
deliberate: any new operational capability has to be built rather than getting a
free doctype form. The reason is that the desk exposes the whole schema — every
tenant's billing, every credential — behind a UI that was never designed to be a
boundary, and "it is only for admins" stops being true the first time it isn't.

The claim decays quietly, so it is checked rather than remembered.
`tests/test_no_desk.py` enumerates every doctype the control plane defines and
fails the build on any the console cannot reach, by name or through an endpoint
the SPA calls. Exemptions are listed with a reason. It also fails on any link
into `/app` from either SPA — one would be enough to teach that the real
interface is elsewhere.

That audit found five surfaces with none: account requests, the standby pool,
Stripe webhook events, app entitlements per workspace, and a workspace's
subscription and credit ledger.

---

## 5. Plans, entitlements and billing

**Plan = quotas only.** Storage, seats, background job concurrency, credit
grant. No feature flags anywhere in the codebase — every feature is on every
plan. Four tiers, named to be unambiguous rather than clever: Starter and Pro
(personal), Business and Enterprise (commercial).

**App entitlement is orthogonal to plan.** That is the mechanism for bespoke
single-tenant solutions. Every app's code ships to every site, gated rather than
absent — per-tenant benches would multiply the deploy problem by the customer
count. Entitlements are enforced server-side by a `has_permission` hook keyed on
the doctype's module; hiding a nav item is a UX affordance, never a boundary.

### The Plan doctype is the source of truth; Stripe holds the money

Saving a plan creates its Stripe Product and Prices. Nobody pastes a `price_...`
id between two systems, because dual entry is how a page ends up advertising one
number while the card is charged another and nothing notices.

Stripe Prices are immutable, so **changing what a plan costs mints a new Price
and archives the old**. That is what makes grandfathering real: everyone already
subscribed keeps billing on the Price they bought, and `Plan Price` keeps every
id we have ever minted so a webhook can still say which plan an old price was.

Stripe being unreachable never blocks a plan being saved — the failure lands in
`Plan.sync_error` and the next save retries.

### Quotas are captured when a subscription is sold

Enforcement reads the terms copied onto the **Subscription**, not the Plan.
Reading the plan live made every price-sheet edit retroactive: tidying a tier
re-quotaed everyone on it, and somebody who bought 50GB could wake up with 20GB.
So `is_active = 0` retires a plan and takes nothing from anyone on it; moving an
existing customer onto newer terms is a deliberate act.

### Plan changes do not go through Stripe's billing portal

The portal is better than us at cards, invoices and cancellation and keeps all
three. It cannot be given plan switching for one reason: **it does not know our
quotas.** It would sell a downgrade to a workspace already holding more than the
smaller plan allows, and the customer would find out afterwards, over quota,
with no way back except paying again.

So the switch is ours, and it runs the same fit check the plans page renders,
from the same function. Proration is immediate and symmetric — a change that
charges today and applies next month is a split nobody can reason about from a
receipt. Stripe can still be repriced without us (a coupon, a dashboard edit),
so `customer.subscription.updated` follows the price actually being charged back
to a plan and applies it.

### Add-ons

Monthly, not permanent: a recurring line on the existing subscription — one
invoice, one dunning cycle, one card, prorated both ways. A permanent
entitlement is revenue collected once for a cost incurred every month, and a
workspace that churns keeps the room it stopped paying for.

Two kinds, sold per unit: **file storage** (R2, our cost, linear) and **database
storage** (the server's disk is ours in full, so the per-tenant limit is a number
we choose — which is what makes it sellable). What a workspace holds is captured
on its subscription, same as plan terms. **Releasing below what is in use is
refused**, naming the resource.

`Tenant.extra_storage_gb` survives as something else entirely: an operator's
grant. Never billed, never expiring, no price. Goodwill, a migration allowance,
room on a demo.

### Promo codes and the free instance

Ours to declare, Stripe's to enforce: a `Promo Code` creates a Stripe Coupon
(the money) and a Promotion Code (the string somebody types). A coupon is
immutable once created, so changing a percentage mints a new one and retires the
old; anyone already redeemed keeps what they were given.

**Scope is ours**, enforced where a checkout is created — subscriptions, add-ons
and credit packs are three separate switches.

**A demo or training workspace is a 100%-off-forever code**, not a comped
tenant. Stripe collects no payment method at zero, and the result is a real
subscription — real terms, real quotas, and `invoice.paid` still fires so it
receives its monthly credit grant. The alternative, a tenant with no
subscription, is a second lifecycle: no period boundaries, no grants, its own
branch in every billing path, and a demo that stops resembling the thing being
demonstrated.

### Overage: never a surprise charge, never destroyed data

| Resource | At the limit |
|---|---|
| **Storage** | Warn at 80%, block new uploads at 100%. Existing files stay. |
| **Database** | Warn at 80%, block writes that grow it at 100%. |
| **Users** | Hard cap; inviting past it prompts an upgrade. |
| **AI credits** | Stop. Buy a pack or wait for the next grant. |

A hard block is recoverable in seconds by deleting something; silently charging
for overage is not, and deleting data to enforce a quota is indefensible.
Storage is never paid for with credits — mixing the two currencies means a large
upload silently drains the AI budget somebody was saving.

**Going over is a window, not a wall**, because there are two ways to get there
and they feel completely different. *They filled it up*: warned at 80%, watching
it climb, and the block is the thing they were told about. *The limit came
down*: an add-on line left the subscription and the next upload fails on an
ordinary day for no visible reason. After the fact the two are
indistinguishable, so both get `overage_grace_days` and an email naming the date
it ends.

**Usage may not grow inside the window.** The ceiling is what was held at the
moment it went over, recorded then rather than at the first refused upload —
taking it later would ratchet upward every time one more file squeezed through.
Database enforcement is simply off inside the window: its block is on inserts,
and half-blocking those gives a workspace that can be typed into and not saved.

There is no such thing as "the storage add-on failed" — Stripe bills the plan
and every line on one invoice against one card. The invoice fails, the
subscription goes Past Due, and the lifecycle ladder is the whole answer.

---

## 6. The lifecycle

What happens to a workspace from creation to nothing left. Most of it runs on a
timer with nobody watching, and the last rung destroys customer data.

| Status | The site | The data | Back in |
|---|---|---|---|
| `Draft` / `Provisioning` | being built | none | minutes |
| `Active` | running | live | — |
| `Suspended` | deactivated on Frappe Cloud | untouched | **seconds** |
| `Archived` | **deleted** from Frappe Cloud | a cold copy in R2 | **minutes** |
| `Purged` | gone | **deleted** | never |
| `Failed` | half-built | none | — |

Suspended is a switch — the site exists, we still pay for it, one API call turns
it back on. Archived is not — the site is gone, we have stopped paying, and what
remains is the copy under `cold/<tenant>/`.

```
Active
  │  payment fails → Past Due; dunning_started_on = today
  ▼
Grace          dunning_grace_days      site works; two emails
  ▼
Suspended      suspended_days          site off; cold copy taken on the way in
  ▼
Archived       cold_retention_days     site deleted; the copy is what is left
  ▼
Purged                                 irreversible
```

`lifecycle/sweep.py` walks it once a day. Every rung is a comparison between two
dates, so running it twice, or after a week of downtime, does the same thing
once. The clock is `Tenant.dunning_started_on`, stamped directly from the Stripe
webhook rather than left to the sweep, so the first email goes out within
minutes; cleared the moment it recovers, so a workspace that fails again
restarts at the top rather than resuming mid-fall.

A workspace with **neither** a subscription nor a trial is not on the ladder at
all — that is an operator's own creation, and dunning it would be automation
surprising the person who built it.

### The refusals

This is the only part of the product that destroys customer data, so it is built
to stop rather than to proceed.

| Refusal | Why |
|---|---|
| A workspace on `lifecycle_hold` moves not at all | A demo, a dispute, a legal hold |
| A workspace with no clock is never advanced | Automation must not finish a human's half-finished action |
| Archiving refuses without a cold copy | Archiving would *be* the deletion |
| Purging refuses without the full window | — |
| Purging refuses without a warning sent `purge_warning_days` ago | A window widened then narrowed must not delete somebody who was never told |
| Purging refuses when `auto_purge_enabled` is off | — |
| `cold_retention_days` under 7 reads as the default | Below a week nobody who has been away can notice and stop it |
| `delete_prefix` refuses a prefix naming no tenant | One missing f-string argument would empty the bucket for every tenant sharing it |
| Purging a workspace that still has a site is refused | That would delete the backups of something running |

Every transition writes a `Tenant Lifecycle Event` **before** the work is
attempted as well as after. A purge that stopped halfway leaves its intent
behind, which is what you want to find a year later in a dispute.

The windows are settings, not constants — the day somebody's card fails over a
long weekend is the day you want the grace period to be a field. Defaults: 7
grace, 14 suspended, 60 cold retention, 7 purge warning, 7 overage grace. Each
has a floor, and a value under it reads as the default: zero is not a policy
anybody types on purpose, and reading it literally would suspend the fleet.

Every rung has an operator door on the workspace's Lifecycle tab. Rehearsal is
`admin.advance_lifecycle_clock`, which moves **the calendar, not the rules** —
it refuses on a Production tenant, and it is deliberately not a button in the
console: a control that fast-forwards a deletion has no business in a row of
ordinary actions.

---

## 7. Credits and AI

**Cloudflare AI Gateway is the gateway, not the model provider.** We get
caching, rate limiting, retries and — critically — per-request logging tagged
with tenant id.

Everything turns on one sentence: **we never invent a price.**

Every charge starts from a count the provider returned — tokens by modality,
tiles, audio minutes — or from a parameter we set on the request. Nothing is
derived from the length of a string. A model whose rate we could not read is not
sellable; a call we could not meter is not billed. This was worth confirming
rather than assuming, because AI Gateway does **not** return a cost: the figure
lives in its log, arrives after the fact, and Cloudflare's own documentation
calls it an estimate. What is exact and immediate is the usage the model
reports.

**The reservation is a ceiling, not a forecast.** Something must be held before
the answer exists, and the honest way to choose that number is to make it a
limit we enforce. A feature declares the most it may consume; that is priced at
catalogue rates and held; the hold collapses to the measured actual when the
provider answers. Spending is **reserve → execute → commit/release** — without
it two concurrent requests read the same balance and both spend it.

**The catalogue is fetched, not typed.** Providers ship models weekly and
reprice without notice, and the way you find out about a hand-maintained table
is a margin rather than an error. Models, capabilities and prices sync nightly.
What stays ours is the commercial layer: whether to sell a model, what to charge
on top, which to recommend. Prices are therefore **not editable** in the console
— a field the next sync overwrites is a control that silently stops working.

**The ledger lives only in the control plane.** Append-only; balance is a sum,
never a mutable field. Non-rollover grants are entries with
`expires_on = period_end`, and consumption is **soonest-expiring grant first,
purchased packs last** — packs roll over, and that is what makes them worth
buying.

**Reconciliation** is hourly against the gateway's own logs. Small gaps are
adjusted; refunds always are (a cache hit costs the provider nothing). Gaps
beyond 25% or 5 credits are **not** adjusted: the disagreement is no longer
about price but about what happened, and re-billing a customer on the strength
of a number its own vendor calls an estimate is not automatic. Those are flagged
for a person.

**Markup** is one multiplier with a per-model override. Credits are
`cost_usd × 100 × markup`, rounded up so a million tiny calls are not free.
Credits stay deliberately abstract: customers buy credits, not tokens, so a
provider repricing a model is our problem rather than a pricing announcement.

Two edges worth knowing: `commit_usage` never charges more than was held — right
for a hold, wrong for a bill — so a call that overran posts the remainder as an
adjustment rather than being absorbed silently; and a response that cannot be
metered at all releases the hold and charges nothing.

---

## 8. Storage, backups and email

**Attachments go to Cloudflare R2** via a `File` override, keyed
`tenants/<tenant_id>/…`. Private files run Frappe's permission check on the
attached document, then 302 to a short-TTL presigned URL; public files come from
a public bucket behind `cdn.4dl.app`.

R2 exposes no per-prefix usage metric, so the counter is ours: sum of
`File.file_size` per site, rolled up on a schedule. Enforcement is a
`before_insert` hook **at upload time** — a tenant discovering they are 3 GB
over after the fact is a worse experience than a clear rejection.

**Database size** is capped separately and is the cap that actually constrains
how many sites fit on a server. Over the limit, *inserts* pause; updates and
deletes keep working, so deleting is always a way back out. Recovery doctypes
are exempt — Frappe writes a `Deleted Document` when you delete, and blocking
that would block the only escape — as are installs, migrations and patches.
Measuring it is an `information_schema` scan over ~1,200 tables, far too
expensive per insert, so it runs hourly and only the verdict is read. An absent
verdict reads as *not over*, so a stopped scheduler unblocks rather than
freezes.

**Buckets are rotated at a cap.** A `Storage Bucket` tracks jurisdiction, tenant
count and bytes; at the cap it is marked Full and a fresh one is created.
Customers choose Global or EU jurisdiction. The reason is blast radius: one
bucket holding every tenant's files is a single credential, a single
misconfiguration and a single accidental lifecycle rule away from losing
everything at once. Consequence: the bucket is per-tenant, so it belongs in
*site* config; bench config keeps only the account-wide credentials.

**Backups: two custodians.** Frappe Cloud's managed backups and our own into R2,
because one provider holding both your site and the only copy of it is not a
backup strategy. Ours are taken by the tenant site at the frequency its plan
bought, under `backups/<tenant>/<stamp>/`. Retention and staleness detection are
the control plane's, not the site's — both have to keep working for a workspace
whose site is suspended or gone.

**Email is Cloudflare in both directions.** Inbound: catch-all → Worker → parse
recipient → HMAC POST to the right tenant, giving per-tenant functional
addresses (`ap@` for supplier invoice ingestion, `support@`, `leads@`).
Per-user mailboxes are out of scope — that is a mailbox product, not a feature.

Outbound goes through Cloudflare Email Service over SMTP
(`smtps://smtp.mx.cloudflare.net:465`, username `api_token`), so Frappe's own
Email Queue handles batching, retries and unsubscribe.
`ensure_email_account()` creates the Email Account at install and reconciles it
on every sync, so the token is set once on the bench and every tenant picks it
up.

Ours to build regardless of provider: **per-tenant send rate limits**, bounce
and complaint handling, and DMARC. On a shared sending identity, one tenant
importing a purchased list degrades deliverability for everyone.

### Background jobs

`Plan.background_workers` caps how many jobs a workspace may have in flight,
counted from RQ rather than from a counter of our own — a counter has to be
decremented by something, and a worker killed mid-job never decrements it.
Counting fails open: a Redis blip must not become an outage.

Be straight about what plan-based priority can do. There is no supported way to
make a worker prefer one site's jobs, and patching the queue is not something to
carry across framework upgrades. What works is capping what a small plan can
consume, routing *our own* long work by plan, and rate limiting per tenant.
Preempting framework-internal jobs is not achievable. The real lever on RAM is
MariaDB's buffer pool, not the queue.

---

## 9. Cost model

The Frappe Cloud server plan is the whole server — unlimited benches and sites,
no per-site charge. Confirmed, along with two other questions that gated pricing
rather than design: $40 is the entire server, not app-server-only; and
Cloudflare email does expose SMTP, so the outbound Worker shim was deleted
rather than built.

At ~30 tenants on a $40 cpx22:

| Line | Per tenant / month |
|---|---|
| Server ($40 / 30) | ~$1.33 |
| R2 (10 GB, zero egress) | ~$0.15 |
| Email | ~$0.05 |
| **Total** | **~$1.53** |

Against a $22 entry tier that is ~7% of revenue, improving as a server fills.
Because there is no per-site fee, the pressure is entirely on **how many sites
fit before MariaDB degrades**, which makes the capacity table §2 the figure to
watch and a second server a capacity decision rather than a pricing one.

The margin variable is the **AI credit grant inside each plan**, not
infrastructure — which is why per-tenant gateway logging was wired in from day
one rather than retrofitted.

---

## 10. Configuration

Frappe merges the bench's `common_site_config.json` into every site, so
configuration splits by whether a value is per-tenant or shared.

| Level | Holds | Set how |
|---|---|---|
| **Bench common** | Everything identical across tenants — R2, the email token, AI keys | **Control Settings → Tenant bench config**, then **Push Bench Config** |
| **Site config** | Only what is unique to one tenant — its name, its secret | Injected by the provisioning engine |

**You never configure a tenant site by hand.** Shared keys are set once on the
bench; identity is injected at provisioning; and the fifteen-minute sync
reconciles anything derived from them, so rotating a shared key reaches every
existing tenant on its own.

**Identity** (per site, injected): `oneapp_tenant`, `oneapp_control_url`,
`oneapp_hmac_secret`, `oneapp_site_name`. A site missing these is orphaned —
running, but unable to prove who it is.

**Kind** (by hand, once): `oneapp_role = "control"` on the control plane;
absent means a tenant. Declared rather than derived — asking "is `oneapp_control`
installed?" would make this a consequence of an app list, and its failure mode
is silence: install an app for an unrelated reason and a customer's attachments
quietly stop going to R2.

**R2**: `oneapp_r2_account_id`, `oneapp_r2_bucket`, `oneapp_r2_access_key`,
`oneapp_r2_secret_key`, `oneapp_r2_public_base`. Absent, the File override falls
back to Frappe's filesystem behaviour rather than failing every upload.

**AI**: `oneapp_cf_account_id`, `oneapp_ai_gateway`, `oneapp_ai_gateway_token`,
`oneapp_google_ai_key`, `oneapp_cf_api_token`, `oneapp_ai_markup`.

**Email**: `oneapp_cf_email_token` (Email Sending: Edit), `oneapp_mail_domain`,
`oneapp_mail_hourly_limit`. The sending domain must be onboarded through the
Cloudflare dashboard, which adds MX, SPF, DKIM and DMARC — and the domain has to
be on Cloudflare DNS.

Frappe `develop` is **v17 and requires Python 3.14** and Node ≥ 24. On older
Node, yarn refuses the install and leaves `node_modules` empty; the build then
fails with `MODULE_NOT_FOUND`, pointing at the wrong problem.

---

## 11. Bringing it up

In order — later steps depend on earlier ones. Stages 1–3 get a working control
plane; stage 4 is needed before the first tenant; stage 5 can wait until you
actually want files, mail or AI.

1. **A fresh control site** with `oneapp_control` and `oneapp` installed, and
   `oneapp_role = "control"`.
2. **Frappe Cloud** — an API token, a server, a bench group tracking the
   `oneapp-app` mirror, and the same for the control mirror.
3. **Configure the control plane** — Control Settings: the press credentials,
   Stripe keys, the bench config to push, and at least one Region and Shard.
4. **Before real customers** — plans synced to Stripe, the webhook endpoint
   registered, the signup flow walked once end to end.
5. **Storage, mail and AI** — the R2 bucket and `cdn.4dl.app`, the Cloudflare
   email domain, the AI gateway.
6. **The lifecycle rehearsal** — a workspace walked from a failed payment to a
   purge with `advance_lifecycle_clock`, checking the event log at each rung.

The **Readiness** screen is the checklist: it names what is missing and what is
blocked by it, so this list is where to start and that screen is where to find
out how far you got.

### Staging and production

Frappe Cloud allows **one bench group per server for our purposes**: creating a
site on a dedicated server makes press re-derive the bench from
`(server, version, apps)` and ignore the `group` argument, so two groups with
the same version and apps are indistinguishable. `version_upgrade` is not the
way to move one afterwards — it is built for cross-version moves and raises
`IndexError` between two same-version groups.

So separation costs a second server. Today everything ships from `main` to every
site; `Tenant.environment` and `Shard.environment` are kept because they are
what the split will be built on, and reconstructing which tenant was which at
that moment is exactly the wrong time.

Splitting later is supported and costs a backup-and-restore window:
`add_server_to_release_group`, then `change_server`, which creates a Site
Migration — deactivate, back up, restore, swap proxies, archive, reactivate.
**The site is offline for all of it.** Move workspaces while they are small.

---

## 12. Working on this repo

Frappe Cloud is where tenants run. It is not where you develop — a push to a
mirror builds a **new bench image**, which is minutes per change and restarts
every site on the bench.

```bash
scripts/dev.sh up          # MariaDB, Redis, the site on :8000
scripts/dev.sh worker      # a background worker, for anything that enqueues
scripts/dev.sh spa         # Vite dev server, hot reload
scripts/dev.sh migrate     # after adding a doctype
scripts/dev.sh shell       # a REPL bound to the site
scripts/dev.sh down
```

Two SPAs want two sites; both run at once, the pid file named after the port:

```bash
scripts/dev.sh up                                             # OneAdmin, :8000
ONEAPP_SITE=space.localhost ONEAPP_PORT=8001 scripts/dev.sh up  # OneSpace, :8001
```

A OneSpace site is an ordinary Frappe site with `oneapp` installed. **No erpnext
needed** — every erpnext import is deferred and gated, and the hard requirement's
only real effect was that OneSpace could not run on a development bench, which
is why it went so long without being opened in a browser.

### Four things that cost an hour each, once

* **`up` runs Werkzeug without the reloader**, so a Python edit is *not* live on
  the next request. It looks exactly like the code being wrong: the endpoint
  answers, the shape is the old shape, and nothing says why. `down` then `up`.
* **Anything that enqueues needs a worker.** Every notification the framework
  produces is enqueued, so on a bench with no worker an assignment writes no
  Notification Log at all — and the empty panel looks exactly like our bug.
* **Start the site you are about to test last.** `webserver_port` is one
  bench-wide setting that socketio reads at startup, so whichever site started
  most recently owns realtime. The symptom is the realtime specs failing alone,
  with no error anywhere.
* **`yarn build` before a Playwright pass.** The browser suite runs the built
  bundle, not Vite.

### The test suites

`python -m pytest` is ~1,580 tests with `frappe` stubbed — signature
verification, slug rules, retry backoff, filter shaping, every guard. It runs on
every push and needs no bench.

`npx playwright test` is ~110 browser tests against a real site (OneSpace's
suite; OneAdmin has one spec, because its screens are the same engine), at
desktop and phone widths — because the bugs worth catching here, an empty list
or a dialog that will not open or a panel a third of which is off-screen, all
render without throwing. It is serialised on purpose: every spec drives the same seeded
space, and four workers finish in 2.6 minutes with two specs failing on data
another worker changed. The real fix is a seeded space per worker.

The guards are the point of the suite, not a side effect. They exist because
each one caught something that had already shipped: a manifest naming a doctype
nothing granted, a UI property nothing declares, a class Tailwind never emitted,
a setting an operator could change that was wired to nothing, a doctype
maintained by hand outside the generator.

### Deploying

| | Builds an image | Moves a site |
|---|---|---|
| `bench.deploy` | yes | no |
| `site.update` | no | yes |
| `site.migrate` | no | runs patches on the current bench |

A successful build changes nothing a customer can see until a site is updated
onto it. `deploy_and_update` looks like the obvious call and is not — with
`use_new_deploy_flow` on it runs a Release Pipeline, which failed in "Preparing
deployment" with nothing exposed to the API to say why. `bench.deploy` then
`site.update` builds the same image and is honest about the two halves.

Do not watch the bench's `deploy_in_progress` flag: it is false for the first
few seconds, so a watcher started immediately reports the *previous* deploy's
result and calls it done.

---

## 13. What a field is allowed to be

Four rules, found by auditing every field on all 34 doctypes and enforced by
`tests/test_field_purpose.py`, because each failure was a class rather than an
accident.

**A setting an operator can change has to change something.** The R2 rotation
threshold sat in the settings dialog, described itself as the cap a new bucket
is created with, and was wired to nothing — narrowing the blast radius to 50
tenants produced buckets that still took 200, silently. A setting is either read
outside the form that offers it or it comes off the form.

**A derived field is read-only.** `Tenant.environment` is overwritten from the
shard on every save; as an editable Select it was a control whose value was
discarded the moment it was used. `Tenant.hmac_secret` went the same way for a
sharper reason: `ensure_hmac_secret` keeps what is already there, so a typo
would stick and every signed call from that workspace would start failing with
nothing to point at.

**A field that is only written is not a record of anything.** The lifecycle
sweep stamped what it did onto a Single every night, which on a site with no
desk is unreachable — so the one question worth asking about the ladder, *did it
run*, had no answer. It is a readiness check now.

**Data or Link is a question about where the record lives.** A Link is right
when the target exists on the same site: `Region.country` is not a label — it
rides the sync into every workspace created there, names its ERPNext Company and
picks its chart of accounts by exact string match, so free text meant a typo
produced a workspace whose books quietly never got set up. Data is right when
the record is on the other side of the wire (`OneSpace Site State.tenant`), when
it is somebody else's identifier (everything `press_*` and `stripe_*`), when the
casing is theirs too (Stripe's `usd` against Frappe's `USD` — a Link there fails
validation on every row), or when the value is a report rather than a reference
(`Tenant Lifecycle Event.from_status` is what was true then, and stays true when
the Select it came from is edited).

And **every doctype is declared in `scripts/gen_doctypes.py`**. `OneSpace Site
State` was not, which made it the one doctype the drift check could not see —
the generator's whole purpose is that a field cannot be added to a JSON by hand,
so a doctype outside it is the failure the generator exists to prevent, wearing
the generator's clothes.
