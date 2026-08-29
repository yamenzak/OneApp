# Bring-up runbook

From an empty Frappe Cloud account to a control plane that can provision a
tenant. Follow in order — later steps depend on earlier ones.

Stages 1–3 get you a working control plane. Stage 4 is needed before the first
tenant. Stage 5 can wait until you actually want files, mail or AI.

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

8. **Note the site plan** offered when creating a site on your own server. If
   sites require a plan selection, that plan's name goes on the Shard as
   `press_site_plan`. If none is required, leave it blank.

---

## Stage 2 — Cloudflare, minimum to provision

Only DNS is needed to create a tenant. The rest can follow.

9. **Zone id for `4dl.app`.** Overview → API section, bottom right.

10. **DNS token.** My Profile → API Tokens → Create Token, permission
    **Zone → DNS → Edit**, scoped to the `4dl.app` zone only.

---

## Stage 3 — Configure the control plane

All of this is in the desk UI at `admin.4dl.app/app`.

11. **OneApp Control Settings → Frappe Cloud**
    | Field | Value |
    | --- | --- |
    | `press_api_url` | `https://cloud.frappe.io` (frappecloud.com redirects here and the redirect drops auth) |
    | `press_api_key` / `press_api_secret` | from step 7 |
    | `tenant_domain` | `4dl.app` |
    | `control_plane_url` | `https://admin.4dl.app` |

12. **OneApp Control Settings → Cloudflare DNS**
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
    | `press_site_plan` | from step 8, or blank |
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

Each is independent. Fill the fields in **OneApp Control Settings → Tenant bench
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
