# Setup

What has to exist before any of this runs, and every configuration key the code
reads. Follow [`ROADMAP.md`](ROADMAP.md) for order; this is the reference.

---

## Python version

Frappe `develop` is **v17 and requires Python 3.14** (`requires-python = ">=3.14,<3.15"`
in its own `pyproject.toml`; `v15` runs on 3.10–3.11). Frappe Cloud handles this
for hosted benches; a local machine needs the interpreter provisioned.

Two ways to get it:

```bash
uv python install 3.14        # uv 0.12+; older uv only offers 3.14 release candidates
```

or [`pilot`](https://github.com/frappe/pilot), Frappe's bench replacement, which
uses `uv` internally and manages the interpreter for you:

```bash
curl -fsSL https://raw.githubusercontent.com/frappe/pilot/develop/install.sh | bash
pilot new dev-bench
```

Use 3.14 **final**, not a release candidate — pydantic's namespace resolution
fails on 3.14.0rc2 inside `frappe.integrations.utils`, which breaks site
creation.

---

## Repositories

Work happens in this monorepo. CI publishes each app to a mirror that Frappe
Cloud clones — see the root [`README`](../README.md).

| Source | Mirror |
| --- | --- |
| `apps/oneapp` | `yamenzak/oneapp-app` |
| `apps/oneapp_control` | `yamenzak/oneapp-control` |

Repository secret `MIRROR_TOKEN`: a fine-grained PAT with **Contents: Read and
write**, scoped to those two repositories only.

---

## Frappe Cloud

Two bench groups:

| Group | Apps | Sites |
| --- | --- | --- |
| Tenant | `frappe` + `erpnext` + `oneapp` | one per tenant |
| Control | `frappe` + `erpnext` + `payments` + `oneapp_control` | `admin.4dl.app` |

**Wildcard domain.** `*.4dl.app` must be registered as a root domain on the
server, with Frappe holding a wildcard certificate. Press models this as a
`Root Domain` with a wildcard `TLS Certificate`, but on hosted Frappe Cloud that
is press-side configuration — **it is a support request to Frappe, not an API
call**. Raise it early; provisioning cannot work without it.

Once it exists, creating a tenant is a single `press.api.site.new` call with no
DNS or certificate work per tenant.

**API credentials.** Generate an API key and secret on the Frappe Cloud account
and put them in OneSpace Control Settings.

---

## Control-plane configuration

In **OneSpace Control Settings** (Single doctype):

| Field | Notes |
| --- | --- |
| `press_api_url` | `https://cloud.frappe.io` (frappecloud.com redirects here and the redirect drops auth) |
| `press_api_key` / `press_api_secret` | from Frappe Cloud |
| `tenant_domain` | `4dl.app` |
| `control_plane_url` | `https://admin.4dl.app` — tenant sites call back here |
| `default_shard` | optional; the allocator picks least-loaded otherwise |
| `reserved_slugs` | additions to the built-in blocklist |
| `stripe_webhook_secret` | signing secret from the Stripe webhook endpoint |
| `ai_gateway_url` / `ai_gateway_token` | Cloudflare AI Gateway |

At least one **Shard** must exist, with `press_release_group` set to the tenant
bench group. Without a shard that has headroom, `pick_shard` returns `None` and
provisioning refuses rather than placing a tenant nowhere.

**Stripe** is configured through the `payments` app's Stripe Settings, so there
is one place to rotate the secret key. Point a Stripe webhook at:

```
https://admin.4dl.app/api/method/oneapp_control.billing.webhooks.stripe
```

subscribed to `checkout.session.completed`, `customer.subscription.*`,
`invoice.paid`, `invoice.payment_failed`.

---

## Configuration: two levels

Frappe merges the bench's `common_site_config.json` into every site's
`frappe.conf`, so configuration splits cleanly by whether a value is per-tenant
or shared:

| Level | Holds | Set how | How often |
| --- | --- | --- | --- |
| **Bench common config** | Everything identical across tenants — R2 credentials, the Cloudflare email token, AI keys | Fill in **OneSpace Control Settings → Tenant bench config**, then **Push Bench Config** on the Shard (or *Push to All Shards* from Settings). Equivalently: the Frappe Cloud dashboard, Bench Group → Config | **Once per bench.** A rotation is one push, not one per tenant |
| **Site config** | Only what is unique to one tenant — its name, its HMAC secret | Injected by the provisioning engine (`push_site_config`) | Automatically, at site creation |

**You never configure a tenant site by hand.** Shared keys are set once on the
bench; identity is injected at provisioning; and `sync_from_control_plane` (every
15 minutes) reconciles anything derived from them — including the outgoing Email
Account — so adding or rotating a shared key reaches every existing tenant on its
own.

### Identity — per site, injected at provisioning

| Key | Purpose |
| --- | --- |
| `oneapp_tenant` | tenant name on the control plane |
| `oneapp_control_url` | control-plane base URL |
| `oneapp_hmac_secret` | shared secret, scoped to this tenant alone |
| `oneapp_site_name` | permanent internal address |

A site missing these is orphaned: running, but unable to prove who it is. It will
log a sync error and serve no apps.

> Set these in **OneSpace Control Settings**, not by hand on each bench — the push
> action writes them to the bench group for you, and never overwrites an existing
> bench value with a blank.

### R2 storage — bench common config

| Key | Purpose |
| --- | --- |
| `oneapp_r2_account_id` | Cloudflare account id |
| `oneapp_r2_bucket` | bucket name |
| `oneapp_r2_access_key` / `oneapp_r2_secret_key` | R2 API token |
| `oneapp_r2_public_base` | `https://cdn.4dl.app` |

Absent, the File override falls back to Frappe's filesystem behaviour rather than
failing uploads.

### AI — bench common config

| Key | Purpose |
| --- | --- |
| `oneapp_cf_account_id` | Cloudflare account id |
| `oneapp_ai_gateway` | gateway name |
| `oneapp_ai_gateway_token` | gateway auth, if enabled |
| `oneapp_google_ai_key` | Google AI Studio key |
| `oneapp_cf_api_token` | for Workers AI |
| `oneapp_ai_markup` | multiplier on measured cost, default `1.5` |

### Email — bench common config

| Key | Purpose |
| --- | --- |
| `oneapp_cf_email_token` | Cloudflare API token with **Email Sending: Edit** |
| `oneapp_mail_domain` | `mail.4dl.app` |
| `oneapp_mail_hourly_limit` | per-tenant send cap, default `200` |

Outbound goes through Cloudflare Email Service over SMTP. `ensure_email_account()`
creates the Frappe **Email Account** at install and reconciles it on every sync,
so the token is set once on the bench and every tenant picks it up without being
touched:

```
smtps://smtp.mx.cloudflare.net:465
username: api_token
password: <the token above>
```

Frappe's own Email Queue then handles batching, retries, unsubscribe and
attachments. A REST endpoint and a Workers binding also exist if SMTP is ever
blocked.

The sending domain must be onboarded through the Cloudflare dashboard, which adds
the MX, SPF, DKIM and DMARC records — and the domain has to be on Cloudflare DNS.

Per-tenant rate limiting is ours regardless of transport, enforced on
`Email Queue` insert.

---

## Cloudflare

- **R2 bucket** with `cdn.4dl.app` bound to it for public objects.
- **Email Routing** on `t.4dl.app`, catch-all to the `oneapp-email-inbound`
  Worker.
- **KV namespace** `TENANTS`, mapping tenant slug to `{url, secret}`. The email
  worker reads it; the control plane writes it during provisioning. KV rather
  than a control-plane call so an outage does not bounce mail.

  Put the namespace id and a token with **Workers KV Storage: Edit** in
  *OneSpace Control Settings → Cloudflare KV*. That token is control-plane only and
  is never pushed to bench config — it could rewrite mail routing for every
  tenant. If a namespace is ever recreated, `cloudflare.kv.resync_all` rebuilds
  the map.
- **AI Gateway** with per-request logging enabled — that is how AI spend gets
  attributed per tenant.

See [`workers/README.md`](../workers/README.md).

---

## Local development

```bash
git clone https://github.com/yamenzak/OneSpace ~/src/OneSpace

cd ~/frappe-bench
ln -s ~/src/OneSpace/apps/oneapp          apps/oneapp
ln -s ~/src/OneSpace/apps/oneapp_control  apps/oneapp_control
./env/bin/pip install -e apps/oneapp -e apps/oneapp_control
printf 'oneapp\noneapp_control\n' >> sites/apps.txt

bench --site control.localhost install-app oneapp_control
bench --site tenant.localhost  install-app oneapp
```

Frontend:

```bash
cd apps/oneapp/frontend && npm install && npm run dev
```

Tests that need no bench:

```bash
python -m pytest tests/ -q
python scripts/validate_doctypes.py
```

Doctype schemas are generated — edit `scripts/gen_doctypes.py` and re-run it
rather than hand-editing JSON.
