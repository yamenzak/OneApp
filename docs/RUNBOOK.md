# Bring-up runbook

From an empty Frappe Cloud account to a control plane that can provision a
tenant. Follow in order — later steps depend on earlier ones.

Stages 1–3 get you a working control plane. Stage 4 is needed before the first
tenant. Stage 5 can wait until you actually want files, mail or AI.

---

> **Developing?** Do not start here. `docs/DEVLOOP.md` describes the local
> bench, which answers most questions in seconds rather than minutes. This
> runbook is for bringing up real infrastructure.

## Stage 0 — A fresh control site

Once the site exists on Frappe Cloud, hand it its own Frappe Cloud keys before
signing in. It cannot be told them through its own UI, because nothing is
configured yet and that is the thing being configured.

```bash
ONEAPP_FC_ENV=~/.oneapp/fc.env scripts/bootstrap_site.py oneadmin.frappe.cloud
```

The script reads the config back after writing it: press drops empty values
silently, so a write that reports success is not proof the key landed.

Then sign in as Administrator and work down Setup. It goes from red to green as
you go, and signup opens by itself once provisioning, billing and capacity are
all satisfied — there is no switch to throw.

| # | Where | What |
| --- | --- | --- |
| 1 | Settings → Frappe Cloud | Control plane URL (this site's own https address) and tenant domain |
| 2 | Settings → Regions → New | e.g. code `nuremberg`, name "Nuremberg, Germany" |
| 3 | Shards → Register server | Pick the server and bench group — both read live from Frappe Cloud, so the names cannot be mistyped |
| 4 | Settings → Plans → New | At least one, with its Stripe price ids |
| 5 | Settings → Billing | Stripe keys and the webhook secret |
| 6 | Settings → Cloudflare | R2 and the DNS token |

**Set the shard's Environment** deliberately. It is the shard, not the tenant,
that decides — tenants inherit it — and the default is Production so that
forgetting protects rather than exposes.

It is what `admin.bench_environment` reports before a deploy, and what
`advance_lifecycle_clock` refuses to touch: the lifecycle rehearsal in §6 will
not age a Production workspace, so a rehearsal tenant needs a Staging shard.

---

## Stage 1 — Frappe Cloud

1. **Create the server.** Servers → New Server. The $40 `cpx22` covers the whole
   machine with unlimited benches and sites. Note the server name.

2. **Create the control bench group.** Version: `Nightly` (develop).
   Add apps from GitHub:
   - `https://github.com/yamenzak/oneapp-control` — branch `main`
   - `erpnext` — from the app registry, matching branch
   - `payments` — from the app registry

   Confirm Frappe Cloud detects the app name as `oneapp_control`, not the repo
   name. If the repositories are private, install the Frappe Cloud GitHub app on
   them first, or make them public — they contain no secrets.

3. **Create the tenant bench group.** Version: `Nightly`.
   - `https://github.com/yamenzak/oneapp-app` — branch `main` (detects as `oneapp`)
   - `erpnext`

   Note this group's **name** — it goes on the Shard as `press_release_group`.

4. **Deploy both bench groups** and wait for the builds to go green. A build
   failure here is an app problem, not a configuration one — read the build log
   before continuing.

5. **Create the control site** on the control bench group. Any subdomain; it is
   internal. Install `oneapp_control`, `erpnext` and `payments` on it.

6. **Attach `admin.4dl.app` to the control site.** In Cloudflare DNS add a
   **DNS-only** (grey cloud) CNAME from `admin.4dl.app` to the site's Frappe Cloud
   hostname, then Site → Domains → Add Domain, wait for the certificate, and set
   it primary. This is the same flow provisioning automates for tenants; the
   control site is the one you do by hand.

7. **Generate a Frappe Cloud API key.** Account settings → API access. Keep the
   key and secret.

8. **Note the values the Shard needs.** All are readable from the API:

   | Shard field | Where it comes from |
   | --- | --- |
   | `press_server` | Servers list, e.g. `u25-nuremberg-3.frappe.cloud` |
   | `press_release_group` | the bench group's *name*, e.g. `bench-46799`, not its title |
   | `press_cluster` | the server's cluster, e.g. `Nuremberg-3` |
   | `press_version` | the bench group's version, e.g. `Nightly` |
   | `press_default_domain` | `press.api.site.get_domain`, normally `frappe.cloud` |
   | `press_site_plan` | on a dedicated server, an `Unlimited - <provider>` plan at $0.00 |

   `press_version` matters more than it looks. On a dedicated server press
   ignores the bench group you name and re-derives it from
   (server, version, apps). With no version it matches nothing, then silently
   falls back to its public marketplace path, which cannot resolve private app
   sources and fails with "Source not found for app frappe".

---

## Stage 2 — Cloudflare, minimum to provision

Only DNS is needed to create a tenant. The rest can follow.

9. **Zone id for `4dl.app`.** Overview → API section, bottom right.

10. **DNS token.** My Profile → API Tokens → Create Token, permission
    **Zone → DNS → Edit**, scoped to the `4dl.app` zone only.

---

## Stage 3 — Configure the control plane

All of this is in the desk UI at `admin.4dl.app/app`.

11. **OneSpace Control Settings → Frappe Cloud**
    | Field | Value |
    | --- | --- |
    | `press_api_url` | `https://cloud.frappe.io` (frappecloud.com redirects here and the redirect drops auth) |
    | `press_api_key` / `press_api_secret` | from step 7 |
    | `tenant_domain` | `4dl.app` |
    | `control_plane_url` | `https://admin.4dl.app` |

12. **OneSpace Control Settings → Cloudflare DNS**
    `cf_zone_id` and `cf_dns_token` from steps 9–10.

13. **Create a Shard** — this is what makes provisioning possible at all.
    | Field | Value |
    | --- | --- |
    | `shard_name` | e.g. `hetzner-cpx22-01` |
    | `status` | `Active` |
    | `deploy_ring` | `Fleet` (use `Canary` for a shard holding only your own tenants) |
    | `press_release_group` | tenant bench group name from step 3 |
    | `press_server` | server name from step 1 |
    | `domain` | `4dl.app` |
    | `domain_mode` | `Per-tenant` |
    | `press_default_domain` | Frappe Cloud's root domain for your sites, e.g. `frappe.cloud` |
    | `press_version` | the bench group's version, exactly — e.g. `Nightly` |
    | `site_apps` | apps to install, e.g. `frappe,erpnext,oneapp` — must all be on the bench group |
    | `press_site_plan` | from step 8, e.g. `Unlimited - Hetzner` |
    | `capacity_tenants` | `30` — a soft cap; see ARCHITECTURE §1 |

14. **Set `default_shard`** in Settings to the shard you just made.

15. **Provision a test tenant.** From the desk console or an API call:

    ```python
    frappe.call("oneapp_control.api.admin.create_tenant",
                tenant_slug="testco", tenant_name="Test Co",
                owner_email="you@fourdegreelabs.com", plan="personal-starter")
    ```

    Watch **Provisioning Job**. It advances on a two-minute cron, so it will not
    complete instantly. Each step is idempotent — a failure retries with backoff,
    and `state = Failed` with `last_error` is where to look if it stops.

    Expect `testco.4dl.app` to be live once the job reaches `Succeeded`.

---

## Stage 4 — Before real customers

16. **Stripe.** Create products and prices, then put the Price IDs on each Plan
    (`stripe_price_id_monthly` / `_yearly`). Configure the `payments` app's Stripe
    Settings with the secret key. Add a webhook to
    `https://admin.4dl.app/api/method/oneapp_control.billing.webhooks.stripe`
    subscribed to `checkout.session.completed`, `customer.subscription.*`,
    `invoice.paid`, `invoice.payment_failed`, and put its signing secret in
    `stripe_webhook_secret`.

17. **Review the plan ladder.** `fixtures/plan.json` seeds four plans; everything
    above the $22 entry is a placeholder. Size `monthly_credit_grant` against
    measured model cost — that grant, not infrastructure, is the margin variable.

---

## Stage 5 — Storage, mail and AI

Each is independent. Fill the fields in **OneSpace Control Settings → Tenant bench
config**, then use **Push Bench Config** on the Shard.

18. **R2.** Create the bucket, an R2 API token, and bind `cdn.4dl.app` to the
    bucket for public objects. Fill `r2_account_id`, `r2_bucket`,
    `r2_access_key`, `r2_secret_key`, `r2_public_base`.

19. **Email — outbound.** Onboard the sending domain in Cloudflare Email Service
    (it adds MX, SPF, DKIM and DMARC). Create a token with
    **Email Sending: Edit** → `cf_email_token`. Set `mail_domain`.

20. **Email — inbound.** `wrangler kv namespace create TENANTS`, put the id in
    `workers/email-inbound/wrangler.toml`, deploy the worker, and point Email
    Routing's catch-all for `t.4dl.app` at it. Then in Settings → Cloudflare KV
    set `cf_kv_namespace_id` and `cf_kv_token` (permission
    **Workers KV Storage: Edit**).

    Tenants provisioned before this exists are missing from the routing map —
    `cloudflare.kv.resync_all` backfills them.

21. **AI.** Create an AI Gateway, then fill `cf_account_id`, `ai_gateway`,
    `ai_gateway_token`, `google_ai_key`, `cf_api_token`.

22. **Push Bench Config** on each Shard. Tenant sites pick the values up on their
    next sync — within fifteen minutes, with no per-site work.

---

## Stage 6 — The lifecycle rehearsal

Do this once, on a **staging shard**, before any real customer exists. It is the
only way to find out whether a restore works before somebody needs one — and
`press.api.site.restore` is the one call in this system that has never run
against real Frappe Cloud.

**Before you start, the readiness board must be green on all four of:**
the scheduler, this site can send email, R2 storage, and the R2 client library.
The first two are blocking and the sweep will refuse without them; the second two
are marked optional because sites work without storage, but a lifecycle rehearsal
without them is testing nothing — there is no backup to promote and no cold copy
to restore from.

> **The scheduler and the client library both fail silently.** A stopped
> scheduler means nothing is synced, backed up or swept, and the console still
> looks healthy. A missing `boto3` means every upload and backup raises
> `ImportError` behind an exception handler, so attachments and backups are
> simply absent. Both are on the readiness board precisely because neither
> announces itself.

### The walk

The windows have floors — `cold_retention_days` will not go below seven — so the
shortest honest walk from a failed payment to a purge is about nine days. The
rehearsal moves **the calendar**, not the rules: every window, warning and
refusal behaves exactly as it will in production.

```bash
# Age a staging workspace's whole lifecycle by N days, then apply the ladder.
# Refuses outright on a Production tenant.
bench --site <control-site> execute \
  oneapp_control.api.admin.advance_lifecycle_clock \
  --kwargs "{'tenant': 'rehearsal', 'days': 8}"

bench --site <control-site> execute \
  oneapp_control.api.admin.run_lifecycle --kwargs "{'tenant': 'rehearsal'}"
```

Repeat the two together, checking the workspace's **Lifecycle** tab after each,
and confirm in order:

| Step | What to see |
| --- | --- |
| 1. Sign up and pay with a Stripe test card | The site is built; the owner gets a link that works |
| 2. Wait for the first backup, or take one | `Last backup` fills in; objects appear under `backups/<tenant>/` in R2 |
| 3. Fail the renewal in Stripe | Subscription goes `Past Due`; the clock starts; **the first email arrives** |
| 4. Age past the grace window, apply | `Suspend Site` runs; the site is off; **a cold copy exists** |
| 5. Check `cold/<tenant>/` in R2 | Database, both file tarballs, and `manifest.json` |
| 6. Age past the suspension window, apply | `Archive Site` runs; the site is gone from Frappe Cloud; `purge_after` is set |
| 7. **Pay the invoice** | `Restore Site` runs on its own; the site is rebuilt and **your data is in it** |
| 8. Sign in and check a record and an attachment | This is the step the whole thing exists for |

Then, on a second throwaway workspace, take it to the end:

| Step | What to see |
| --- | --- |
| 9. Age to within the warning window, apply | The final warning email arrives; `Warned on` fills in |
| 10. Age past `purge_after`, apply | Every prefix under the tenant is deleted; status `Purged` |
| 11. Look in R2 | `cold/`, `backups/` and `tenants/` for that tenant are all empty |

**If step 7 fails, stop and fix it before launching.** Everything upstream of a
restore is reversible; a restore that does not work turns the whole ladder from
a safety net into a way of deleting customers on a schedule.

### What the rehearsal will not tell you

* **Nothing alerts you.** Failures land in Error Log and `Tenant Lifecycle Event`
  and wait to be looked at. Until something pages you, "automated" means
  "unattended", not "unwatched".
* **The control plane is not backed up by any of this.** It holds every HMAC
  secret, the credit ledger, and the tenant-to-Stripe mapping — lose it and every
  tenant site is fine and none of them is billable or reachable. Confirm Frappe
  Cloud is backing up the control site itself, and restore it once, somewhere
  else, before you rely on it.

---

## Notes

**Two token boundaries.** The DNS and KV tokens stay on the control plane and are
never pushed to bench config — each can act across all tenants, and bench config
is readable by every tenant site. Everything under *Tenant bench config* is
deliberately safe to share.

**Certificate ceiling.** In `Per-tenant` mode each tenant consumes a Let's Encrypt
certificate, and the limit is **50 per registered domain per 7 days**. That is
fine to launch on. Before it bites, ask Frappe support for a wildcard root domain
on the server and switch `Shard.domain_mode` to `Wildcard` — one certificate then
covers every tenant. See ARCHITECTURE §2.

**Adding a second server** is steps 1, 3, 4 and 13 again: new server, new tenant
bench group, new Shard. The allocator places new tenants on the least-loaded
shard with headroom.
