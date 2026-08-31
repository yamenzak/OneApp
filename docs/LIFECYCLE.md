# The tenant lifecycle

What happens to a workspace from the moment it is created to the moment nothing
of it is left. Most of it runs on a timer with nobody watching, and the last rung
destroys customer data, so this document is written for the person who has to
explain a decision the software made months ago.

---

## 1. The states

| Status | The site | The data | Back in |
|---|---|---|---|
| `Draft` | none yet | none | — |
| `Provisioning` | being built | none | minutes |
| `Active` | running | live | — |
| `Suspended` | deactivated on Frappe Cloud | untouched | **seconds** |
| `Archived` | **deleted** from Frappe Cloud | a cold copy in R2 | **minutes** |
| `Purged` | gone | **deleted** | never |
| `Failed` | half-built | none | — |

Two of those are worth stating plainly because they are easy to conflate.

**Suspended** is a switch. The site still exists, we still pay Frappe Cloud for
it, and turning it back on takes one API call. Nothing has been deleted.

**Archived** is not. The site is gone, we have stopped paying for it, and what
remains is the copy under `cold/<tenant>/`. Coming back means building a fresh
site and restoring into it.

## 2. The ladder

```
Active
  │  payment fails → Subscription: Past Due; Tenant: dunning_started_on = today
  ▼
Grace          dunning_grace_days      site works; two emails
  ▼
Suspended      suspended_days          site off; cold copy taken on the way in
  ▼
Archived       cold_retention_days     site deleted; the copy is what is left
  ▼
Purged                                 everything deleted; irreversible
```

`oneapp_control/lifecycle/sweep.py` walks this once a day. Every rung is a
comparison between two dates, so running it twice, or after a week of downtime,
does the same thing once.

### The clock

`Tenant.dunning_started_on`, set the first time a subscription is seen unpaid and
cleared the moment it recovers. A workspace that recovers and fails again
restarts at the top rather than resuming mid-fall.

Stripe stamps it directly from the webhook rather than leaving it to the nightly
sweep, so the first email goes out within minutes of a failed payment instead of
within a day. Recovery is immediate for the same reason in reverse.

### What counts as unpaid

* a subscription in `Past Due`, `Canceled` or `Incomplete`;
* a trial whose `trial_ends_on` has passed with nothing bought.

A workspace with **neither** a subscription nor a trial is not on the ladder at
all. That is an operator's own creation — an internal instance, a migration in
progress — and duning it would be automation surprising the person who built it.

### Coming back

| From | How | Time |
|---|---|---|
| Grace | nothing to do | instant |
| Suspended | `Resume Site` — Frappe Cloud activate | seconds |
| Archived | `Restore Site` — a new site, restored from the cold copy | minutes |
| Purged | nothing to restore; we say so and offer a refund | — |

## 3. Backups

Frappe Cloud keeps its own. Ours go into R2, and they are what the cold copy is
made of.

* **Taken by the site**, because the files only exist there and it already holds
  the bench, the database credentials and the bucket keys.
* **On the plan's schedule.** `backups_per_day` is a plan term, so the job runs
  hourly and decides whether this hour is one of the slots — evenly spaced from
  midnight. The first slot of the day takes files as well; the rest are
  database-only, which is what actually changes.

  | Plan | Backups | Kept |
  |---|---|---|
  | Starter | 1 a day | 7 days |
  | Pro | 2 a day | 14 days |
  | Business | 3 a day | 30 days |
  | Enterprise | 4 a day | 60 days |

  R2 is cheap enough that this is a product lever rather than a cost one. What
  actually grows with the tier is how much work a customer can afford to lose:
  an Enterprise workspace losing a day of invoicing is a different conversation
  from a personal one losing a day of notes.
* **Retention is the control plane's**, along with noticing that new ones stopped
  arriving. Both have to keep working for a workspace whose site is suspended,
  off, or gone, which is exactly when the site cannot do them.

Retention expires whole sets rather than individual objects — half a set looks
like a backup and is not one — and never expires the newest, whatever the window
says. A workspace whose scheduler stalled a month ago has one copy left, and a
literal seven-day window would delete it.

### The layout

```
tenants/<tenant>/{public,private}/…    attachments, live
backups/<tenant>/<stamp>/…             rolling, expired by retention
cold/<tenant>/<stamp>/…                promoted, expired only by the lifecycle
```

`tests/test_backup_layout.py` asserts both apps spell these the same way. They
deploy separately, and neither mistake shows up as an error: a rolling backup
under a prefix retention does not sweep is a bill nobody notices, and a cold copy
under one it does sweep is a workspace that cannot be restored.

## 4. The cold copy

A cold copy is a backup, promoted by a server-side copy — so moving a 4 GB backup
between two prefixes costs a request rather than four gigabytes through a control
plane with no business carrying them.

Beside the artifacts goes `manifest.json`. The database says what the workspace
*contained*; only the manifest says what it *was* — which plan, which terms,
which domains, who could sign in, which region and bucket the files came from.
Plain JSON, readable by somebody who no longer has this codebase.

**The site config in a backup is redacted.** Frappe copies `site_config.json`
verbatim, which is right for a restore you perform yourself and wrong for one
stored in the bucket its own keys open. The shape survives; the secrets are
minted again on restore. A restore therefore never sends the config back to
Frappe Cloud — doing so would overwrite the working keys with a set of nulls and
produce a site that comes up unable to reach the control plane.

### Why the copy is taken *before* suspension

Frappe Cloud's deactivate puts a site into maintenance mode, and Frappe's
scheduler refuses to run at all under maintenance mode. A suspended site cannot
sync, cannot back itself up, and cannot be asked for anything. Whatever copy we
want, we take on the way in.

The control plane cannot reach into a tenant site — every wire runs the other
way, over HMAC — so asking for a fresh copy is a flag the site picks up on its
next sync. If it never answers, after three days the newest copy there is gets
promoted and the log records that it is stale. A workspace whose scheduler died
cannot hold the ladder open indefinitely, and it must not be archived with
nothing behind it either.

## 5. Missing payments for storage and database

Two halves, and they behave differently.

**A missing add-on payment is a missing subscription payment.** Stripe bills the
plan and every add-on line on one invoice against one card. There is no such
thing as "the storage add-on failed" — the invoice failed, the subscription goes
`Past Due`, and the ladder above is the whole answer. A second dunning cycle per
line would be inventing a failure mode Stripe does not have.

**An add-on going away is different.** Stripe can drop a line — dunning, a
dashboard edit, a cancellation — and `webhooks._reconcile_addons` follows it,
because Stripe is the authority on what is being charged. The quota shrinks under
a workspace that is using the space, and from inside the next upload fails on an
ordinary day for no reason anybody can see.

So going over a limit opens a window rather than a wall:

* enforcement pauses for `overage_grace_days`, and the owner is emailed at the
  moment it happens with the date it ends;
* **but usage may not grow.** The ceiling is what the workspace was holding when
  it went over, recorded at that moment rather than at the first refused upload —
  taking it later would ratchet upward every time one more file got through.

The database has no ceiling of that kind. Its block is on inserts, and
half-blocking those gives a workspace that can be typed into and not saved, so
inside the window database enforcement is simply off. A workspace whose
accounting stops because a *storage* add-on lapsed is the worse outcome.

## 6. The refusals

This is the only part of the product that destroys customer data, so it is built
to stop rather than to proceed.

| Refusal | Why |
|---|---|
| A workspace on `lifecycle_hold` moves not at all | A demo instance, a dispute, a legal hold |
| A workspace with no clock is never advanced | Automation must not finish a human's half-finished action |
| Archiving refuses without a cold copy | Archiving would *be* the deletion |
| Purging refuses without the full window | — |
| Purging refuses without a warning sent `purge_warning_days` ago | A window widened then narrowed must not delete somebody who was never told |
| Purging refuses when `auto_purge_enabled` is off | — |
| `cold_retention_days` under 7 is read as the default | Below a week there is no realistic chance for somebody who has been away to notice and stop it |
| `delete_prefix` refuses a prefix that names no tenant | One missing f-string argument would otherwise empty the bucket for every tenant sharing it |
| Purging a workspace that still has a site is refused | That would delete the backups of something that is running |

Every transition writes a `Tenant Lifecycle Event`, before the work is attempted
as well as after. A purge that stopped halfway leaves its intent behind, which is
what you want to find a year later in a dispute.

## 7. The windows

Settings, not constants — the day somebody's card fails over a long weekend is
the day you want the grace period to be a field. Under **Settings → Lifecycle**.

| Setting | Default | From |
|---|---|---|
| `dunning_grace_days` | 7 | the first failed payment |
| `suspended_days` | 14 | suspension |
| `cold_retention_days` | 60 | archiving |
| `purge_warning_days` | 7 | before the purge |
| `overage_grace_days` | 7 | going over a limit |
| `auto_purge_enabled` | on | — |

Each has a floor in `lifecycle/policy.py`, and a value under it is read as the
default. Zero is not a policy anybody types on purpose, and reading it literally
would suspend the fleet.

## 8. Doing it by hand

Every rung has an operator door, on the workspace's **Lifecycle** tab and as
actions on the Tenants screen.

| Action | What it does |
|---|---|
| Hold / Release | Freeze a workspace out of the ladder, or put it back. The clock keeps running while held — only the consequences stop |
| Apply now | Run the ladder on one workspace immediately. How a policy change is tested: widen a window, run this, read the event log |
| Take a cold copy | Promote a backup now — before a migration, or to unstick a workspace the ladder refused to archive |
| Restore | Rebuild an archived workspace. Normally automatic on payment; this is the door for a bank transfer, a mistake, or a restore rehearsal |
| Purge | Delete everything now. For a deletion request under data-protection law, or a retention that is pointless |

## 9. Rehearsing it

The windows have floors, so the shortest honest walk from a failed payment to a
purge is about nine days — right for production, useless for finding out whether
a restore works.

`admin.advance_lifecycle_clock(tenant, days)` ages every lifecycle date on a
workspace, and the next `run_lifecycle` sees it further down the ladder. It moves
**the calendar, not the rules**: every window, warning and refusal behaves as it
will in production, which is the only reason the rehearsal is worth anything.

It refuses on a Production tenant, and `Tenant.environment` comes from the shard
rather than from the workspace — so pointing it at a customer would mean moving
them onto a staging shard first, which is deliberate and visible. It is also not
a button in the console: a control that fast-forwards a deletion has no business
in a row of ordinary actions where somebody can reach it while meaning to click
the one above.

The ordered walk, and what to check at each step, is docs/RUNBOOK.md §6.

## 10. Where it lives

| | |
|---|---|
| `lifecycle/sweep.py` | the ladder |
| `lifecycle/policy.py` | the windows and their floors |
| `lifecycle/cold.py` | promotion, the manifest, the purge |
| `lifecycle/backups.py` | retention, staleness, orphaned cold copies |
| `lifecycle/overage.py` | the over-quota window |
| `lifecycle/events.py` | the audit trail |
| `oneapp/oneapp_core/backup.py` | taking a backup and pushing it to R2 |
| `cloudflare/r2.py` | objects: list, copy, delete, presign |
| `provisioning/steps.py` | `Suspend`, `Resume`, `Archive`, `Restore Site` |
| `notifications/emails.py` | the six emails the ladder sends |
