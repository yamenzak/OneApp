# One entry per question, not one per doctype

An audit of the operator console, screen by screen, against one test: **what
does a person do here that a machine could not have done, and how often?**

Read from `entitlements/operator.py` (the console's whole declaration),
`hooks.py`'s scheduler, and what each doctype's writers actually are.

---

## 1. The finding

The console is **32 screens**: 29 lists and 3 components. The rail has one
entry per doctype, which is how it was built and is not how anybody uses it.

Counted by who writes the records:

* **Six are authored by a person and by nothing else** — `Plan`, `Add-on`,
  `Credit Pack`, `Promo Code`, `Region`, `Space Claim Code`. Nothing in the
  app inserts one. These are the catalogue, and they are the real job.
* **Two are a decision a person makes over records a machine keeps** —
  `Space Entitlement` (give this workspace that app) and `Shard` (add
  capacity).
* **One is the fleet** — `Tenant`.
* **The other twenty are machine state or an audit trail.** Provisioning jobs,
  standby sites, signups, subscriptions, ledger entries, reservations, webhook
  events, buckets, spaces, redemptions, workspace roles, AI models, AI
  features, AI usage, support logins, lifecycle events, and three read-only
  views of Frappe Cloud's own records. A person opens one of these when
  something has gone wrong, and the rail gives no clue that anything has.

So twenty of twenty-nine rail entries are places to go *looking* for a problem.
That is the bloat: not that the screens are bad — most are one line in
`operator.py` and cost nothing to keep — but that **the console cannot tell you
anything is wrong.** It can only be searched.

---

## 2. What the shape should be

Six rail entries.

**Attention.** The one that does not exist and should. A single list of things
that need a person, assembled from what the crons already know: a provisioning
job past its attempts, a webhook that failed, a signup that never became a
tenant, a shard at capacity, a bucket near its cap, a press site with no
workspace against it, a reconciliation mismatch, a workspace whose backups have
stopped arriving, a standby pool under target three runs running. Every one of
those is a query that exists somewhere today, and every one of them is
currently found by remembering to open a screen.

**Workspaces.** `Tenant`, and everything about one workspace reached from its
record rather than from the rail: its provisioning job, its subscription, its
credits, its entitlements, its lifecycle, its support logins, its backups, its
press state. Most of this is already the `tenant` component screen's tabs
(`screens/ops/Tenant.vue` and the three beside it, 1,417 lines).

**Catalogue.** Plans, add-ons, credit packs, promo codes, claim codes — the six
authored things, as tabs of one screen. This is where a person actually types.

**Fleet.** Shards beside Frappe Cloud's sites, servers and bench groups,
because the questions are "which shard has headroom" and "which press site has
no workspace", and both cross the boundary. Four screens become one.

**Money.** Subscriptions, the credit ledger, reservations, webhooks, AI usage.
One screen, tabs.

**Setup.** `api/setup.py`'s readiness checklist, unchanged. It is the best
screen in the console and the only one that tells you what is wrong before you
go looking.

AI models and features move to a tab under Setup: both are synced daily
(`ai.catalogue.scheduled_sync`) and discovered from decorators, so neither is
authored. A price change that moves margin is an Attention row, not a screen.

---

## 3. What can actually be automated away

Ordered by how much manual work it removes.

### 3a. A shard is a bench group, and press knows the rest

Adding capacity today means filling eight required fields — `press_server`,
`press_release_group`, `press_cluster`, `region`, `domain`, `domain_mode`,
`deploy_ring`, `environment` — and six of them are facts Frappe Cloud already
holds. `press/client.py` answers `release_groups()`, `servers()`,
`group_regions()` and `site_plans()`. `api/admin/fleet.py::create_shard`
already takes the short form and fills the rest; the console's New button does
not use it and renders the raw doctype form instead, which is why the form asks
what to fill and why a wrong answer is a 500 rather than a validation error.

**Change:** "Add capacity" becomes a declared screen action with one field — a
bench group, picked from what press returns. Everything else is read off press
at insert. The remaining genuine choice is the domain, which we own.

**And one field goes.** `deploy_ring` was called unread in the first draft of
this document and the code disagreed: it has exactly one behaviour, `!=
'Canary'` in `pick_shard`, with Wave 1, Wave 2 and Fleet indistinguishable to
every query in the product. Which makes it *redundant with*
`accepts_new_tenants` rather than dead — a four-value Select doing a
checkbox's job, and two ways to exclude a shard that have to agree. Dropped,
same conclusion. `environment` stays: it guards one destructive dev operation
(`lifecycle.py` refuses a rehearsal on a Production tenant) and two values is
the right number for that.

### 3b. Regions come from clusters

`Region` is written by nothing, read in three places, and duplicates what
`group_regions()` already returns for a bench group. Keeping the two in step is
manual work with no upside. Seed the table from press's clusters on the same
cron that refreshes the press cache, and keep only the fields press does not
have — the country, which drives storage jurisdiction.

### 3c. Orphan sites find themselves

The `sites` screen exists, per its own comment, so that an operator can spot "a
site on the account with no workspace against it". That is a query
(`press.records.tenants_by_site()` already computes the mapping), not a screen
to scan. It becomes an Attention row, and the screen becomes a tab under Fleet
for the times you want the whole list.

### 3d. The Spaces screen is a trap

`OneSpace Space` rows are rewritten from `spaces/*.py` by `after_migrate` on
every migration. So the console lets an operator edit a space and silently
reverts it at the next deploy. Make the screen read-only and say where the
truth is, or drop it — the same argument as `Workspace Role`, which is the
tenant's and is already documented as read-here-only.

### 3e. The audit trails stop being rail entries

Support logins, lifecycle events, claim redemptions, AI usage and the credit
ledger are all "what happened to this workspace" — which is a tab on the
workspace, not a screen on the rail. They stay queryable; they stop being nine
places to look.

---

## 4. What must stay a person's decision

Named so that "automate the console" does not quietly become "automate the
business":

* Purging a workspace, and restoring one from cold.
* Granting or removing an entitlement.
* A plan's price, and every other number in the catalogue.
* Holding a workspace out of the lifecycle ladder.
* Signing in as a customer for support.

Each of these is already a declared action with a confirmation
(`entitlements/actions.py`). None should become a cron.

---

## 5. The staging — built

All six shipped. What each turned out to be:

**Stage 1, Attention.** Thirteen checks over eleven doctypes
(`oneapp_control/attention.py`), first on the rail, plus a daily digest that
sends only on days with rows. Three rules make it worth having: every check is
one indexed query or a cached press read; a check with nothing to say
contributes nothing; and a check that raises becomes a row rather than an
exception.

**Stage 2, the shard short form.** Required fields down from eight to six, four
of which have defaults — so the form is a name and a bench group.
`fill_from_press` walks group → server → cluster → region and picks the
cheapest press site plan. `provisioning/regions.py` writes one Region per
cluster press reports, never deletes, and creates them inactive.

**Stage 3, the rail collapses.** `screen_group` on the screen child table, six
groups — Fleet, Money, Catalogue, Apps, AI, Trail — plus Setup, with Attention
above all of them. The rail draws a heading when the group changes, which
keeps the nav model a flat ordered list rather than a tree the record pane
would have to understand.

**Stage 4, the workspace becomes the record.** Smaller than planned, because
the workspace screen already had eight tabs covering the record, the site,
domains, backups, lifecycle, apps, billing and Frappe Cloud's own job log. The
one trail still rail-only was Support logins, and it is now on the Lifecycle
tab — the question "who has been in this workspace" is asked about one
workspace, on a call.

**Stage 5, read-only what is derived.** `AUTHORED` names the ten screens where
a person creates a record; the other eighteen carry `hide_new`. A New button
over a table only machinery writes offers a row that will be ignored,
overwritten, or — for `OneSpace Space` — erased by the next migration.

**Stage 6, the guard.** Four tests: every screen names one of a closed set of
groups, a group is declared in one contiguous run, the leading screen carries
none, and — the one that bites — a doctype nothing in the app ever inserts
must be authored, or the only way to make one is the desk.

## 6. The original staging

Each stage is shippable on its own and none of them deletes data — a screen
leaving the rail is a line removed from `operator.py`, and the doctype, its
records and its permissions are untouched.

**Stage 1 — Attention.** Build the screen and the queries behind it. This is
the only stage that adds something, and it is the one that makes the other five
safe: nothing can be taken off the rail until there is somewhere for a problem
to surface.

**Stage 2 — the shard short form.** The bench-group action, the two dead
fields, and the Regions seed. This is the stage that removes the most typing,
and it is the one that bit us on the first deployment.

**Stage 3 — the rail collapses.** 32 screens to 6, as tabs. Mechanical: the
screens already exist and a tab strip over them is the record pane's own
machinery.

**Stage 4 — the workspace becomes the record.** Fold the per-tenant audit
trails into tabs on the workspace, where the question is asked.

**Stage 5 — read-only what is derived.** Spaces, workspace roles, and the three
press views stop offering New and Delete.

**Stage 6 — the guard.** A test that reads `operator.py` and fails a screen
whose doctype nothing authors and which is not reachable from Attention or from
a workspace. That is what stops the rail growing back to thirty-two.

---

## 7. The one caveat

A console that only shows problems is a console you stop reading when there are
none — which is correct, and which means **Attention has to be reachable
without opening the console at all.** A daily digest to the operator's inbox
with the same rows, and nothing sent on a quiet day. Otherwise this trades
thirty-two screens nobody reads for one screen nobody opens.
