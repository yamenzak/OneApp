# What else is out there, and what we should take from it

An assessment of our own infrastructure against two repositories that look, at
a glance, like they do the same job for a fraction of the code:

* **`vyogotech/saas_platform`** (MIT) — a Frappe app that makes one ERPNext site
  multi-tenant by putting a `tenant_id` column on every table.
* **`vyogotech/erpnext-microservices-lib`** (MIT) — a Python library for
  building Flask microservices on Frappe, each owning its own database, with a
  Central Site as the identity provider.

Read at commit-time HEAD of both, 2026-09-11. Everything below is from the code
rather than the README.

---

## 1. The short version

The two repositories are not one system and should not be judged as one.

`saas_platform` is 1,228 lines of Python. It is an early prototype with a
**broken isolation model** — not "weaker than ours", but one that leaks every
tenant's data to every other tenant by default, for reasons in §3. It is not a
candidate to replace anything we have.

`erpnext-microservices-lib` is 20,676 lines, with 41 test files, a BDD suite, a
coverage gate, published container images and a real changelog. It is
competently built and well documented. It also solves a **different problem** —
decomposing an ERPNext monolith into independently deployable services — and
doing so requires running Frappe outside bench, in containers, under Gunicorn,
on Frappe v16. That is structurally incompatible with Frappe Cloud, which is the
substrate our entire provisioning story stands on. Adopting it means operating
our own Kubernetes.

So: nothing here replaces what we have. Several things here are worth stealing,
and they are in §6.

---

## 2. What we actually have

For a fair comparison, stated plainly:

| | OneApp |
|---|---|
| Tenancy | One Frappe **site** per tenant: own database, own files, own backups, own app set |
| Provisioning | `Provisioning Job` state machine, resumable, driven by a two-minute cron |
| Substrate | Frappe Cloud (press) through `press/client.py`, 512 lines |
| Python | ~71,000 lines across `oneapp` and `oneapp_control` |
| Frontend | ~93,000 lines |
| Tests | 3,966, plus a Playwright suite across two viewports |
| Doctypes | 75 |

The provisioning pipeline (`provisioning/steps.py`, 1,030 lines) is: check
availability, create the site, poll the agent job, push `site_config`, create
the DNS record, attach the domain, wait for the certificate, promote the domain,
register mail routing. Each step is idempotent and records itself on the job, so
a worker restart mid-provision resumes rather than restarts. Errors are sorted
into `PressTransientError` and `PressPermanentError`; transients back off
exponentially to thirty minutes over twelve attempts. There is a reverse
pipeline for archive. Around it: Stripe billing, a credit ledger, a metering AI
gateway, per-jurisdiction R2 buckets, Cloudflare email, a dunning ladder, cold
storage with restore, over-quota grace, daily backups, a marketplace and an
operator console.

That is the thing being compared. It is not 1,228 lines because it is not doing
what 1,228 lines does.

---

## 3. `saas_platform`: why the isolation does not hold

This section is specific because the conclusion is severe and should be
checkable rather than taken on trust.

**The model.** `ALTER TABLE` adds a `tenant_id` column to every non-single
DocType — 689 tables — and a `permission_query_conditions` hook filters reads to
`tenant_id IN (<yours>, 'SYSTEM') OR tenant_id IS NULL`. A `before_insert` hook
on `"*"` stamps new documents with the session's tenant.

**Failure 1 — the column is only real for 21 doctypes.** The patch adds the SQL
column to all 689 (`patches/add_tenant_id_to_all_tables.py:87`), but the
*Custom Field* — the thing that makes Frappe's ORM aware of it — is added to
only 21 (`docs/architecture.md:164`). Frappe writes a document through
`get_valid_dict()`, which reads the doctype's meta. For the other 668 doctypes
`set_tenant_id` sets an attribute that is then dropped on the way to the
database, and the column takes its `ALTER TABLE` default, which is **`'SYSTEM'`**
(`:89`). `'SYSTEM'` is explicitly readable by every tenant. So every row of
every tenant in 668 doctypes is visible to every other tenant, permanently, by
construction.

**Failure 2 — document reads are not filtered at all.**
`permission_query_conditions` applies to `frappe.get_list` and the report view.
It does not apply to `frappe.get_doc`, `frappe.client.get`,
`/api/resource/<doctype>/<name>`, `frappe.db.get_value`, `frappe.db.sql`, query
reports, or child rows fetched with a parent. The guard for that is a
`has_permission` hook. The repository *has* one — `permissions.py:70` — and
`hooks.py` leaves it **commented out** (`hooks.py:131-132`). Knowing a document
name is enough to read another tenant's document.

**Failure 3 — every tenant admin is a System Manager.** The onboarding flow
gives the tenant's admin user `System Manager`
(`docs/architecture.md:104`). In Frappe that role is effectively root: it can
edit Custom Fields, write and run Script Reports, and reach the API console.
Row-level filtering is advisory against a role that can rewrite the rules.

**Failure 4 — `IS NULL` is a hole, and the two exclusion lists disagree.** The
read filter admits `tenant_id IS NULL`, so anything written by a path that
skipped the hook — a patch, a fixture, a bulk insert, `db_insert`, a background
job running as Administrator — is global. And the list of doctypes excluded
from *stamping* (`utils/tenant.py:44-50`) is not the list excluded from
*filtering* (`:117-125`): the first contains `'Usera'`, `'aSubscription Plan'`,
`'aCustomer'` and `'aToken Cache'` — typo'd entries that disable the exclusion
they were meant to express.

**Smaller things, listed because together they say what the code is.**
`apply_tenant_filter` (`utils/tenant.py:108`) references a table called
`` `tabtenantid` `` that does not exist. `permissions.py:33` hardcodes
`` `tabDocType` `` into a condition meant for any doctype. `tenant_id` is
interpolated into SQL with an f-string in four places. `saas_platform/utils.py`
and `saas_platform/utils/` both exist, so the module is shadowed by the package
and its copy of `set_tenant_id` is dead. `after_app_install` is assigned twice
in `hooks.py`, the second shadowing the first.

**And the repository contradicts itself.** `tasks.py:5` provisions a tenant with

```python
cmd = ["bench", "new-site", site_name, "--admin-password", password, ...]
subprocess.run(cmd, cwd=frappe.get_bench_path())
```

which is a **site per tenant** — the opposite of the row-level model the docs
describe. It hardcodes `.localhost`, never checks the return code, passes the
admin password on the argv where `ps` can read it, has no retry, no idempotency
and no resume, blocks a worker for the minutes `new-site` takes, and requires
that worker to hold bench and database-root privileges. The signup endpoint
feeding it is `allow_guest=True` and takes a plaintext password
(`api.py:3`), with no verification, rate limit or captcha.

**Verdict.** Not a candidate. Not because it is small — because the one thing it
exists to do, it does not do.

---

## 4. `erpnext-microservices-lib`: good, and not for us

This one is genuinely well made. `isolation.py` (890 lines) patches Frappe's app
and hook resolution so a service sharing a database with the Central Site cannot
load the Central Site's apps; `presync.py` (995) syncs doctype schema once
before Gunicorn forks; `tenant.py` (1,215) threads tenancy through reads,
writes, naming and link presentation. The changelog reads like someone who has
run this in anger. The container story — an entrypoint in the base image, a
service that is one `server.py`, immutable `sha-<full>` tags, `/health` and
`/health/ready` — is better than ours.

Three reasons it does not fit.

**It needs a different substrate.** It runs Frappe as a pip package under
Gunicorn in a container, with `site_config.json` written from environment
variables at boot. Frappe Cloud runs benches, not our containers. Taking this
means taking on our own cluster, our own database operations, our own backups —
all of which press currently does for us, and all of which we chose press
precisely in order not to do.

**It needs Frappe v16.** We are on v15 and our tenants are on whatever the bench
group carries.

**Its tenancy is the row-level model from §3, with the enforcement written
properly.** Which is the point: if we wanted row-level tenancy we would be
choosing to give up per-tenant databases, per-tenant backups, per-tenant app
sets and per-tenant restore. `docs/APPS-AND-SPACES.md` explains why we do not —
a Space declares `custom_fields`, and per-customer schema is only safe because
the schema is per-customer.

One honest caution about its security posture: `PERMISSION_MODE`, `CSRF_MODE`
and `TENANT_STRICT` all default to `warn`, which logs and blocks nothing, and
only flip to `enforce` in 2.0. A team that deploys it and does not read that
table is running unenforced.

---

## 5. Where the "simpler" impression comes from

`bench install-app saas_platform` and you have multi-tenancy. Against that, our
control plane wants a press account, a Cloudflare token, an R2 bucket per
jurisdiction, Stripe keys and a Shard row before a single tenant exists. That
difference is real and it is worth naming honestly.

But it is not a difference in how much machinery each approach needs. It is a
difference in what each one is doing:

* Their provisioning is one `subprocess.run`. Ours is DNS, a TLS certificate we
  have to wait for, a per-tenant app set computed from what the bench group
  actually carries, mail routing, and resumability. `bench new-site` does none
  of those, so a one-line provisioner is only one line while the product has no
  custom domains, no HTTPS, no email and no tolerance for a worker restart.
* The thing that already makes our provisioning simple **is Frappe Cloud.** We
  do not run a database, take a backup, renew a certificate or patch a host.
  `press/client.py` is 512 lines and that is the whole of our infrastructure
  operations.

Our complexity is not in provisioning. It is in billing, credits, metering,
lifecycle and storage — none of which either repository attempts.

---

## 6. What is worth taking

Four things, in order of how much they are worth.

**1. Staged enforcement.** Their risky features ship in `warn` mode, log
`[would-deny]` for what they *would* have blocked, and flip to `enforce` in the
next major. Deploy, grep, fix, enforce. We have no equivalent, and we have
shipped several things — the permission layer, the AI write lane, the upload
door — where we would have wanted one. Worth adopting as a pattern for the next
one.

**2. Empty is not off.** `MULTI_TENANT=""` resolves to *on*, deliberately, so a
missing ConfigMap key cannot silently disable isolation. That is the right
default direction for every safety flag, and it is worth auditing our own
`site_config` and environment reads against it: any flag where the unset case is
the permissive case is a flag waiting to be dropped from a deploy.

**3. A release artifact.** They publish `frappe-microservice` to PyPI and
immutable `sha-<full>` container tags, with a CHANGELOG. We publish by mirroring
a subdirectory to a branch, and a bench installs whatever that branch is today.
There is no version, no changelog and no way for a tenant bench to say what it
is running. That is a real gap and it will bite the first time two tenants are
on different code.

**4. A published API description.** `register_resource("Sales Order")` gives
documented REST plus Swagger at `/apidocs`. `spaceview` already derives the same
thing from a manifest; it just never emits an OpenAPI document. Cheap, and the
first customer who wants to integrate will ask.

Not worth taking: the row-level tenancy, the microservice decomposition, or the
container runtime. Each would cost us Frappe Cloud.

---

## 7. The one thing that would change this

If we ever sell to a customer who requires their data in a database of their
own — which, for German public-transit operators, is the normal requirement
rather than the exceptional one — row-level tenancy is disqualified before the
code is read, and this comparison stops being a judgement call.
