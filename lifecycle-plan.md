# Tenant lifecycle, grace periods, cold storage and backups

**Status: done.** A–H are built, tested and pushed.

What follows is the assessment this started from — what existed, what was
missing, and the batches that closed the gap. The durable half now lives in
`docs/LIFECYCLE.md`, which is where to look for how the thing works; this file
is the record of the decision and can go once it has been read.

Two things came out differently from the plan and are worth naming:

* **The cold copy is taken at suspension, not at archiving.** Frappe Cloud's
  deactivate puts a site into maintenance mode, and Frappe's scheduler refuses
  to run at all under maintenance mode — so a suspended site can never sync,
  back itself up, or be asked for anything. That ordering is the difference
  between a workspace that can be brought back and one that cannot, and it is
  invisible from either end on its own.
* **The restore pipeline needed a second `await_agent`,** and the runner
  resumes by looking a step name up in its pipeline with `list.index`, which
  returns the first match — so two steps sharing a name loop until the attempt
  ceiling. Named apart, and now guarded by a test over every pipeline.

---

## 1. What already exists

| Piece | Where | State |
|---|---|---|
| Tenant statuses | `Tenant.status` | `Draft / Provisioning / Active / Suspended / Archived / Failed` |
| Suspend / resume / archive | `provisioning/steps.py` PIPELINES | Built, and **only ever fired by hand or on cancellation** |
| Stripe dunning | Stripe | Stripe retries; `invoice.payment_failed` sets `Past Due` |
| Consequence of Past Due | `webhooks.apply_subscription_status` | **None, deliberately.** Only `Canceled` suspends |
| Quota enforcement | `oneapp_core/storage/quota.py` | Hard block at upload, hourly database verdict |
| Backup to R2 | `oneapp_core/storage/r2.sync_backup_to_r2` | A function with **no caller** |
| R2 buckets | `cloudflare/r2.py` | Bucket admin over the Cloudflare API. **No object-level access** |
| Trial | `Tenant.trial_ends_on` | A date **nothing reads** |

So: every mechanical part of the lifecycle exists and nothing drives it. A
workspace whose card fails sits at `Past Due` forever, keeps its site, keeps
costing us a Frappe Cloud site plan, and is never asked again.

## 2. What is missing

1. **A clock.** No dunning ladder, no dates, no sweep. Suspension is manual.
2. **Deprovisioning.** `Archive Site` deletes the Frappe Cloud site and takes
   nothing with it — the workspace is simply gone, unrecoverable, and the R2
   objects are left orphaned and billed for forever.
3. **A way back.** Nothing restores. Resume works only from `Suspended`, where
   the site still exists.
4. **Add-on lapse.** When Stripe drops an add-on line, `_reconcile_addons`
   shrinks the quota silently and the next upload fails with no warning.
5. **Backups.** Frappe Cloud takes its own; we take none. The one function we
   wrote for it is dead code.
6. **Purge.** Nothing ever deletes anything. R2 grows without bound.

## 3. The shape

### 3.1 One ladder, driven by dates

Stripe owns retries and card updates. We own consequences. The tenant carries
one clock, `dunning_started_on`, set the first time we see a subscription go
`Past Due` (or a trial lapse with nothing bought), and cleared the moment it
recovers.

```
Active
  │  payment fails → Subscription: Past Due; Tenant: dunning_started_on = today
  ▼
Grace          (grace_days, default 7)      site works, two emails
  ▼
Suspended      (suspend_days, default 14)   site deactivated on FC
  │                                          cold copy taken on the way in
  ▼
Archived       (cold_days, default 60)      FC site deleted; we stop paying for it
  │                                          cold copy + files kept in R2
  ▼
Purged                                       cold copy and every object deleted
```

Payment succeeds anywhere on the ladder and the workspace comes back:

| From | How it returns | Time |
|---|---|---|
| Grace | nothing to do | instant |
| Suspended | `Resume Site` — FC activate | seconds |
| Archived | `Restore Site` — new site, restored from the cold copy | minutes |
| Purged | nothing to restore; a new empty workspace, and we say so | — |

Statuses gain exactly one member: **`Purged`**. `Archived` keeps its meaning —
the Frappe Cloud site is gone — and gains a guarantee it did not have: a cold
copy was taken first.

### 3.2 Cold storage is a promoted backup, not a separate mechanism

The dump the user asked for and the daily backup are the same artifact. So:

* the tenant site takes backups and pushes them to `backups/<tenant>/<stamp>/`;
* at suspend time it takes one final full backup, and the control plane
  **copies** it to `cold/<tenant>/` — a prefix retention never touches;
* archive checks the cold copy exists before it lets Frappe Cloud delete
  anything;
* restore presigns the cold objects and hands the URLs to `press.api.site.restore`;
* purge deletes `cold/<tenant>/`, `backups/<tenant>/` and `tenants/<tenant>/`.

The cold copy is database + public files + private files + a sanitised
`site_config.json` + a manifest (plan, subscription, members, quotas, domains,
sizes, when). The secrets are stripped: the HMAC secret and R2 keys are minted
fresh on restore.

### 3.3 Who does what

The tenant site is the only place the files exist; the control plane is the only
place with an R2 admin token and a policy. So:

| Work | Side | Why |
|---|---|---|
| take a backup, upload it | tenant | it has the files and the bench |
| decide the frequency | control | it is a plan term |
| retention, promotion to cold, purge | control | policy, and it survives a suspended site |
| restore | control → press | a running site cannot drop its own database |

The control plane needs object-level R2 access it does not have today —
`list`, `copy`, `delete`, `presign` over the S3 API, added beside the existing
bucket admin.

### 3.4 Backups, and frequency by plan

Two new plan terms, captured onto the subscription like every other term so a
price-sheet edit is never retroactive:

* `backups_per_day` — 1 on entry plans, more as they go up;
* `backup_retention_days` — how long we keep them.

The tenant site runs hourly and decides whether this hour is a backup hour:
`24 / backups_per_day`. The first run of each day is a **full** backup (database
and files); the extra intra-day runs are database-only, which is what actually
changes. Retention prunes on the control plane's schedule, not the tenant's — a
suspended site does not prune itself.

Every backup is reported upward, so `Tenant.last_backup_on` is a number an
operator can alert on. A workspace that has not backed up in twice its interval
is a fault, not a quiet gap.

### 3.5 Missing payments for storage and database

The honest answer has two halves, and both need saying because they behave
differently.

**A missing add-on payment is a missing subscription payment.** Stripe bills the
plan and every add-on line on one invoice against one card. There is no such
thing as "the storage add-on failed" — the invoice failed, the subscription goes
`Past Due`, and the ladder above is the whole answer. Building a second dunning
cycle per line would be inventing a failure mode Stripe does not have.

**An add-on going away is different, and is the real gap.** Stripe can drop a
line — dunning, a dashboard edit, a cancellation — and `_reconcile_addons`
follows it, so the quota shrinks under a workspace that is using the space. Today
the next upload simply fails. Instead: when the quota drops below what is
already stored, stamp `over_quota_since`, email immediately with what to do, and
give `overage_grace_days` before enforcement bites. Nothing is deleted, nothing
is blocked, and they have a week to buy the add-on back or free space.

### 3.6 Safety

This ladder deletes customer data on a timer, so it is built to refuse:

* **`lifecycle_hold`** on the tenant freezes it out of the ladder entirely — a
  demo instance, a dispute, a legal hold.
* **Archive refuses without a cold copy.** No copy, no deletion; it raises and an
  operator sees it.
* **Purge requires all of**: the full retention window elapsed, a warning email
  sent at least `purge_warning_days` ago, no hold, and `cold_retention_days >= 7`.
* **Every transition is logged** to `Tenant Lifecycle Event` — what changed, why,
  which rung, and what it was triggered by. The audit trail is the point.
* The sweep is **idempotent and date-driven**, so running it twice, or after a
  week of downtime, does the same thing once.

---

## 4. Batches

All eight shipped.

| | Batch | What |
|---|---|---|
| A | The state model | `Purged` status, lifecycle dates, hold, backup fields, `Tenant Lifecycle Event`, plan backup terms, settings windows |
| B | Objects in R2 | S3 client on the control plane: list, copy, delete, presign, prefix size |
| C | Backups | Tenant-side backup + upload + report; plan-driven frequency; control-plane retention sweep |
| D | Cold storage | Promote to cold, the manifest, purge a tenant's prefixes |
| E | The ladder | `lifecycle/sweep.py`, the dunning clock in the webhook, the emails, recovery |
| F | Restore | `press.restore`, the `Restore Site` pipeline, automatic return from Archived |
| G | Over-quota grace | `over_quota_since`, grace in the sync payload, tenant-side enforcement |
| H | Surfaces and docs | Operator screens, the customer's notice, `docs/LIFECYCLE.md` |
