# Platform decisions

The choices this platform is built on, and why. Companion to
[`ARCHITECTURE.md`](ARCHITECTURE.md), which covers infrastructure; this covers
the product and commercial shape.

---

## 1. One account, many workspaces

**An account owns any number of workspaces, each billed separately.**

The same person signing up for their company and later for something at home is
the normal case, not an edge case — and forcing a second email for it is the kind
of friction people remember. Each workspace carries its own plan, its own
subscription and its own credit ledger, so one can sit on Enterprise while
another sits on Starter.

This changes the isolation rule. It cannot be "the workspace belonging to this
user", because there may be several. It is instead:

> Every customer endpoint takes a workspace name and **verifies ownership before
> doing anything else**. There is no path that trusts the name.

Slightly weaker than having no parameter at all, so it is enforced in one place —
`require_workspace()` — rather than at each call site, and asserted by tests that
read the source: an endpoint that touches a workspace without going through it
fails the build.

---

## 2. Overage

Different resources fail differently, so they are handled differently. The rule
throughout: **never produce a surprise charge, and never destroy data.**

| Resource | At the limit | Why |
| --- | --- | --- |
| **Storage** | Warn at 80%, block new uploads at 100%. Existing files stay. | A hard block is recoverable in seconds by deleting something. Silently charging for overage is not, and deleting data to enforce a quota is indefensible. |
| **Database** | Warn at 80%, block writes that grow it at 100%. | Same reasoning, and this is the one that actually threatens the server. |
| **Users** | Hard cap. Inviting past the limit prompts an upgrade. | Seats are the clearest upgrade signal there is; blurring it with overage helps nobody. |
| **AI credits** | Stop. Buy a pack or wait for the next grant. | Already how the ledger works. Credits are prepaid by design. |

**Storage is not paid for with credits.** Mixing the two currencies means a
tenant uploading a large file silently drains the AI budget they were saving —
a bill nobody can predict from their own behaviour. Extra storage is a separate
add-on, purchased explicitly, and it does not expire.

---

## 3. Plans

Two personal, two commercial. Names chosen to be unambiguous rather than clever:
someone comparing tiers should not have to work out which is bigger.

| Plan | Audience | Position |
| --- | --- | --- |
| **Starter** | Personal | Entry. The $22 tier. |
| **Pro** | Personal | For individuals who have outgrown Starter. |
| **Business** | Commercial | The default for a company. |
| **Enterprise** | Commercial | Large teams, more of everything. |

Plans differ **only in quotas** — storage, seats, credit grant, job concurrency.
Every feature is available on every plan, which is why no feature flags exist
anywhere in the codebase.

### The Plan doctype is the source of truth; Stripe holds the money

Saving a plan creates its Stripe Product and Prices. Nobody pastes a `price_...`
id between two systems, because dual entry is how a page ends up advertising one
number while the card is charged another — and nothing in either system notices.

Stripe Prices are immutable in amount and currency, so **changing what a plan
costs mints a new Price and archives the old one**. That is not a workaround. It
is what makes grandfathering real: everyone already subscribed keeps billing on
the Price they bought, and `Plan Price` keeps every id we have ever minted, so a
webhook can still say which plan an old price was.

Stripe being unreachable never blocks a plan being saved. A control plane whose
price sheet cannot be edited during a Stripe outage is worse than one whose
catalogue is briefly behind; the failure lands in `Plan.sync_error` and the next
save retries.

### Quotas are captured when a subscription is sold

Enforcement reads the terms copied onto the **Subscription**, not the Plan
document. Reading the plan live made every price-sheet edit retroactive: tidying
a tier re-quotaed everyone already on it, and someone who bought 50GB could wake
up with 20GB without having agreed to anything.

So `is_active = 0` retires a plan from the catalogue and takes nothing away from
anyone on it — not the price, not the limits. Editing a live plan changes what
new customers get. Moving an existing customer onto newer terms is a deliberate
act (`quotas.adopt_current_terms`), because the automatic version is the bug this
prevents.

`oneapp_control.billing.quotas` is the only module that decides between the
captured terms and the plan. Everything else asks it.

### Plan changes do not go through Stripe's billing portal

The portal is better than us at cards, invoices and cancellation, and keeps all
three. It cannot be given plan switching, for one reason: **it does not know our
quotas.** It would sell a downgrade to a workspace already holding more than the
smaller plan allows, and the customer would find out afterwards, over quota, with
no way back except paying again.

So the switch is ours — `billing.checkout.change_plan` — and it runs the same fit
check the plans page renders, from the same function. Proration is immediate and
symmetric in both directions: Stripe bills or credits the difference, and the new
limits apply now. A change that charges today and applies next month is a split
nobody can reason about from a receipt.

Stripe can still be repriced without us — a coupon, a dashboard edit — so
`customer.subscription.updated` follows the price actually being charged back to
a plan and applies it. Before that, an upgrade made in Stripe billed at the new
price and left the workspace on the old storage, seats, credit grant and site
plan.

---

## 4. Regions

**Customers pick where their workspace runs; the price does not change.**

A `Shard` already models one server. `Region` groups shards under a name a
customer recognises (`Nuremberg`), and signup offers the regions that currently
have capacity. Adding Frankfurt or Ashburn later is a Region row and a Shard row
— no code.

This also settles buying versus upgrading a server: **both work, and buying is
preferred once a server is full.** Upgrading is a Frappe Cloud operation that
does not involve us. Buying is a new Shard, which the allocator starts using the
moment it accepts tenants. Nothing needs redesigning either way, which is the
point of having modelled shards from the start.

---

## 5. Storage jurisdiction and bucket rotation

**Customers choose Global or EU jurisdiction. Buckets are rotated at a cap.**

Cloudflare R2 can pin a bucket to an EU jurisdiction, which is what an EU
customer asking "where is my data" actually needs answering.

Objects are never spread across one enormous bucket. A `Storage Bucket` record
tracks each bucket's jurisdiction, tenant count and bytes; when one reaches its
cap it is marked Full and a fresh bucket is created through the Cloudflare API.
Tenants are assigned a bucket at provisioning and keep it.

The reason is blast radius. One bucket holding every tenant's files is a single
credential, a single misconfiguration and a single accidental lifecycle rule away
from losing everything at once. Bounded buckets mean the worst case is bounded
too.

**Consequence:** the R2 bucket is per-tenant, so it belongs in *site* config,
not bench config. Bench config keeps only the account-wide credentials.

---

## 6. What plan-based queue priority can and cannot do

Worth being straight about, because the obvious approach does not work.

Frappe's background workers pull from shared RQ queues per bench. There is no
supported way to make a worker prefer one site's jobs over another's, and
patching the queue is not something to carry across framework upgrades.

**What is achievable, and is what we do:**

- **Cap what a small plan can consume.** `Plan.background_workers` limits how
  many jobs a workspace may have in flight, so a Starter tenant cannot occupy
  every worker. This protects the fleet without needing preemption.
- **Route our own long work by plan.** Jobs we enqueue carry a queue derived from
  the plan, so an Enterprise import is not stuck behind a Starter one.
- **Rate limit per tenant.** Already true of email and AI.

**What is not achievable:** preempting framework-internal jobs. A tenant's
scheduled ERPNext work runs at the same priority as everyone's.

**The real lever on RAM is MariaDB, not the queue.** Each site is a database with
~1,200 tables, and the InnoDB buffer pool is shared. Fitting more sites per
server is a matter of buffer pool sizing and connection limits — bench-level
tuning — not scheduling. Section 1 of ARCHITECTURE covers the capacity numbers.

---

## 7. No desk

**The desk is not part of the product, for customers or for us.**

Everything an operator needs is in the admin SPA. This is a deliberate cost: any
new operational capability has to be built rather than getting a free doctype
form. The reason is that the desk exposes the whole schema — every tenant's
billing, every credential — behind a UI that was never designed to be a boundary,
and "it is only for admins" stops being true the first time it isn't.

### Checked, not remembered

The claim decays quietly. A doctype gains a field, the field is only editable in
`/app`, and nobody notices until an operator is told to "just open the desk" — at
which point running this needs someone who knows Frappe, which is the thing the
decision was protecting against.

So `tests/test_no_desk.py` enumerates every doctype the control plane defines and
fails the build on any that OneAdmin cannot reach, either by name or through an
endpoint the SPA calls. Exemptions are listed with a reason: child tables edited
through their parent, and records written by the system and read somewhere else.
It also fails on any link into `/app` from either SPA — one would be enough to
teach that the real interface is elsewhere.

The audit found five surfaces that had none: account requests, the standby pool,
Stripe webhook events (including replaying a failed one), app entitlements per
workspace, and a workspace's subscription and credit ledger. Regions, storage
buckets, plans and the app registry could be read and not written.

### The customer's half

The same rule points the other way for a workspace. A tenant site is a real
Frappe site, so the name and logo on its sign-in page, who may sign in and how,
and what a date looks like all already exist — behind a desk its owner never
sees. Those are the customer's, and they are in OneSpace under Workspace
settings.

`oneapp_core/workspace.py` is one object serving as both the spec the SPA renders
and the allowlist the write path checks, so a setting is writable exactly when it
is visible and there is no code path for anything else. The owner is deliberately
not a System Manager, so every write is `ignore_permissions` behind a single role
check.

What stays ours is the platform: the scheduler, backups, file size limits (that
is a billed quota), guest uploads, telemetry, the mail footer and tracebacks. A
workspace that can stop its own scheduler stops its own email, backups and syncs,
and cannot see why — and we get the ticket.

`docs/WORKSPACE-SETTINGS.md` records every field considered, on both sides, with
the reason. `tests/test_workspace_settings.py` fails the build if anything on the
platform's side appears in the spec.

### What the operator does *not* get to change

Reachable is not the same as editable. A shard's press identity — server, bench
group, version, domain and mode — is what the tenants on it were created against,
so `update_shard` refuses it: editing those would leave the shard describing a
machine those sites are not on. Replacing a shard is registering a new one and
draining the old, which is what the intake switch is for.

---

### Seeded apps are not a catalogue

The registry ships one row, `books`, and nobody has decided to build a books
app. It exists so the entitlement pipeline has something running through it end
to end — registry row, sync payload, role created with `desk_access` off,
DocPerms written from the manifest, launcher rendering, reconciliation on
removal. With an empty catalogue every one of those is dead code on a fresh
control plane, and a break in any of them would go unnoticed until the first
real app.

It is **Restricted**. It was seeded General, which put an app whose interface
says "Not built yet" into every workspace's launcher and granted write on eight
ERPNext doctypes over the REST API — a promise of software that does not exist,
made to someone paying for it. An operator grants it to a workspace to exercise
the pipeline; nobody else sees it.

`tests/test_no_desk.py` fails the build on a seeded app that is not Restricted,
and `seed_apps` defaults to Restricted, so reaching every customer is something
a seed has to opt into rather than arrive at by forgetting to say.

Note that the company and chart-of-accounts setup does **not** depend on this
row: it keys on ERPNext being installed, which is the bench composition in
ARCHITECTURE §1.

---

## 8. Roles and permissions

**We ignore the roles ERPNext, HRMS and Payments ship with.** We use those apps
for the business logic they already implement, not for their idea of who an
"Accounts Manager" is. A customer never sees ERPNext, so a role named for
ERPNext's org chart describes nothing they recognise.

OneSpace defines its own roles instead. Two kinds:

| Kind | Created by | Editable by customer |
| --- | --- | --- |
| **Recommended** | us, per app, from the manifest | no — sync would fight them |
| **Custom** | the customer, through our API | yes, within the allowlist |

### The manifest is the single source of truth

Each `OneSpace Space` declares the doctypes it exposes. That one list drives three
things, which is what makes the model hold together:

1. the DocPerms we generate for our own roles,
2. what an entitlement grants and revokes,
3. the allowlist a customer's custom role may draw from.

A doctype absent from every manifest is reachable by nobody, without anyone
having to remember to exclude it.

### Why not reuse ERPNext's roles with `desk_access` turned off

That was the first plan and it is worse. `user_type` is derived on every `User`
save (`frappe/core/doctype/user/user.py`): any role with `desk_access = 1` makes
the holder a System User, and `frappe/www/desk.py` only refuses `/app` to Website
Users. So desk access is decided by role flags, and flipping them on upstream
roles means re-flipping after every ERPNext upgrade — a silent reopening of the
desk if it is ever missed. Our own roles are `desk_access = 0` at creation, and
there is nothing to keep flipping.

### The cost, stated plainly

DocPerms attach to role names, so our roles begin with no permissions and we
generate them. Scoped to what our apps actually expose that is tens of doctypes,
not the ~1,200 in a stock site — but it is real work, and two parts of it cannot
be done by reading code:

- **The transitive set is not the visible set.** Submitting a Sales Invoice
  writes GL Entry, Payment Ledger Entry, Stock Ledger Entry and updates Item.
  Much of that runs `ignore_permissions=True` inside ERPNext, but not all, and a
  miss surfaces as a permission error thrown deep in a hook naming a doctype the
  customer has never heard of. This set has to be discovered by running the real
  flows against a real site, not enumerated by guessing.
- **Some ERPNext logic branches on literal role names** rather than on
  permissions. Those paths do not fail — they quietly take the other branch for
  our roles.

### Rules for customer-created roles

Enforced in the API that creates them, not in a doctype form:

- **Allowlist, never denylist.** `User`, `Role`, `DocType`, `Server Script` and
  `System Settings` are out because they are in no manifest, not because someone
  remembered to exclude them.
- **`desk_access` forced to 0 on write**, not defaulted. One saved role with it
  set would turn every holder into a System User and reopen `/app`.
- **Managed roles are not customer-editable**, or entitlement sync and their
  edits overwrite each other.

### Consequence we accept

Every tenant user is a Website User, so Query Report and the report builder are
gone — they require desk. Reporting is something we build in the SPA. This
already followed from §7; it is restated here because it is real work, not a
footnote.

### The workspace owner is not a System Manager

They own the workspace, not the site. `site_config` holds
`oneapp_control_secret`; a System Manager could read it and sign requests as
their own tenant, forging usage reports and credit commits. Ops the customer
needs — inviting users, managing seats, creating roles — are whitelisted methods
we expose and run elevated, surfaced in the SPA. Capability comes from our API,
never from a Frappe admin role.


---

## 9. Staging and production

**One bench group per server, and one control plane per group. Frappe Cloud does
not allow more.**

The intent was two groups on one machine — staging and production — so the
development tooling could rewrite the staging control site without touching the
production one. Frappe Cloud will not do it. Creating a site on a dedicated
server requires naming the server, and naming the server makes press re-derive
the bench from `(server, version, apps)` and ignore the `group` argument
entirely. Two groups with the same version and the same apps are therefore
indistinguishable: both new control sites landed on a third, older group.

`version_upgrade(name, destination_group)` looks like the way to move one
afterwards and is not — it is built for cross-version moves and raises
`IndexError` between two Nightly groups. Omitting `server` fails with "No bench
is available to deploy this site".

So separation costs a second server, and until there is one:

| | Where | Automation |
| --- | --- | --- |
| **Now** | one group, one control site, staging | patched and deployed automatically |
| **At go-live** | a second server for production | Frappe Cloud dashboard only |

Tenants are separated by `Tenant.environment` regardless, which is what keeps the
tooling off a bench once a customer lands on it.

### Splitting later is supported, and costs a backup-and-restore window

Running on one bench now is not a corner we are painting ourselves into. The
supported move is **by server**, which is also the split worth paying for:

1. `add_server_to_release_group(name, server)` puts the new machine in the group.
   It needs at least one successful deploy there first.
2. `change_server(name, server)` creates a **Site Migration** and moves the site.

Be clear about the cost, because "migration" sounds livelier than it is. Site
Migration runs: deactivate on source → back up → restore on destination →
restore on destination proxy → remove from source proxy → archive source →
reactivate. **The site is offline for all of it**, so the downtime is a backup
plus a restore — minutes for a small site, longer as it grows. Move workspaces
while they are small.

Moving between two groups of the *same version* on one server is the thing that
is not supported. `version_upgrade` is for version progression — it assumes the
destination is a later version, and raises `IndexError` when it is not. Splitting
by server sidesteps this entirely, which is another reason the split is a server
and not a group.

The control plane is the exception that forces the split. The whole point of the
development tooling is that it rewrites code on the staging control site — and a
patch applies to a *bench*, so a production control site sharing that bench
would be rewritten with it. Two groups on the same machine costs a second set of
workers and no second server.

| Group | Carries | Automation |
| --- | --- | --- |
| `oneapp-staging` | staging control site, staging tenants | patched and deployed automatically |
| `oneapp-production` | production control site, customers | Frappe Cloud dashboard only |

For *tenants* the earlier reasoning still holds — staging and production tenants
can share a group, because sites move onto a new bench individually, so staging
can run ahead while production stays put. What follows is the rule that makes
that safe.

A separate group for staging would mean a second image, a second set of workers
and a second Redis on the same budget. Sharing costs nothing extra and the
mechanics already allow it: sites move onto a new bench individually, so staging
can run ahead while production stays where it is. This is the Canary ring from
ARCHITECTURE §1, used for what it was for.

**Everything ships from `main`, to every site, until there is a second bench.**

The distinction above describes where this lands once the budget carries two
bench groups. It does not describe today: one group carries every site, so a
rule that refused to deploy onto a group holding a production workspace refused
every deploy we could actually make. Enforcing it would have meant either never
deploying or lying about which tenants are which, and the second is worse.

So there is one gate, not two:

1. `ONEAPP_DEV_BENCH_GROUP` must name the group. A machine that never sets it
   has the tooling inert rather than merely discouraged — which is the gate that
   was doing the real work anyway.
2. `admin.bench_environment` still answers, and `live.py status` prints it, so
   an operator can see who is on the bench they are about to deploy to. It no
   longer refuses.

`Tenant.environment` and `Shard.environment` stay. Nothing reads them as a veto
today; they are what the split will be built on, and dropping the fields would
mean reconstructing which tenant was which at exactly the wrong moment.

When a second bench group exists: point staging's shard at it, and turn the
second gate back into a refusal.

---

## 10. Adding capacity

**Buy a server on Frappe Cloud, add a bench group to it, register the pair as a
Shard. Nothing else.**

The allocator picks it up on the next signup with no further work: least-loaded
first among shards that are Active, accepting, and under their soft cap. A region
becomes selectable at signup the moment one shard in it has headroom, and stops
being offered when none does — so a region is never offered that cannot take the
tenant.

Registering happens in the admin SPA, with servers and bench groups read live
from Frappe Cloud rather than typed. Both names have to match press exactly, and
a typo produces a shard that looks right and fails at the first provision, after
a real site already exists.

Two shards must never cover one bench group: both would count capacity against
the same machine, so the allocator would overfill it. The form refuses.

Upgrading a server needs nothing at all — raise `capacity_tenants` when the
machine can hold more. Draining one is `accepts_new_tenants = 0`, which stops
intake without touching the tenants already there.

---

## 11. AI is metered, never estimated

The full design is in `docs/AI.md`. The decisions worth stating here are the
three that constrain everything else.

**We do not invent a price.** Every charge starts from a count the provider
returned — tokens by modality, tiles, audio minutes — or from a parameter we
ourselves set on the request. Nothing is derived from the length of a string.
A model whose rate we could not read is not sellable, and a call we could not
meter is not billed. The old code did the opposite: a hardcoded price table, a
default for anything missing, and a reservation estimated at four characters per
token. Both failure modes were the same one — a number we made up appearing on
a customer's bill.

This was worth confirming rather than assuming, because the initial brief had
it the other way round: AI Gateway does not return a cost. There is no cost
header; the figure lives in the gateway's log, arrives after the fact, and
Cloudflare's own documentation calls it an estimate. What is exact and immediate
is the usage the model reports, which is what we charge on.

**The reservation is a ceiling, not a forecast.** Something has to be held
before the answer exists, and the honest way to choose that number is to make it
a limit we enforce rather than a guess at what the answer will cost. A feature
declares the most it may consume; that is priced at catalogue rates and held;
the hold collapses to the measured actual when the provider answers.

**The catalogue is fetched, not typed.** Providers ship models weekly and
re-price them without notice, and the way you find out about a hand-maintained
table is a margin rather than an error. Models, capabilities and prices are
synced nightly from each provider's API and published price page. What stays
ours is the commercial layer: whether to sell a model, what to charge on top,
which one to recommend. The sync never touches those.

The corollary is that prices are not editable in OneAdmin. A field that the next
sync overwrites is a control that silently stops working, so the rates are shown
and the markup is what an operator turns.


---

## 12. An app is configuration before it is code

The full contract is in `docs/SPACES.md`.

Every other part of this platform is registry-driven — entitlements, roles,
DocPerms, AI features all come from a declaration rather than from an edit in
the SPA. Screens were the exception: OneSpace had one route, which rendered
"Not built yet", and `lib/nav.js` already mapped an `app.links` that nothing
produced. Half a contract, sketched and never finished.

So an app declares its screens the way it declares everything else, and OneSpace
renders them from the tenant site's own metadata. A screen names a doctype and
some fieldnames; what each field is called and whether this user may write it
are facts only the tenant has, and copying them into the control plane would
mean a copy that is wrong the first time a field changes.

That makes a new app a registration plus its doctypes, with no OneSpace release
— which matters more than it sounds, because the alternative is that every app
ships a frontend and the generic CRUD that most screens are gets rewritten each
time.

**Reads and writes go through the view, not through a generic document API.**
That is the security property rather than a formality: a screen can only name a
doctype its app's manifest granted, and can only write a field it shows. Frappe's
permissions still decide whether any of it is allowed.

**The escape hatch is a registered component**, for a dashboard or a wizard or
anything a list of records cannot be. Second, not first: every screen written by
hand is a screen maintained by hand.

## 13. A person may narrow a screen, never widen one

Frappe's desk lets someone save a list view: their filters, their sort, their
columns. Customers expect that, and building it means handing the browser three
things that reach the query layer — a filter dict, an `order_by` string and a
field list — for a screen whose whole security property is that it is an
allowlist.

So the rule is one sentence: **a saved or pending view narrows a screen and can
never widen it.**

* **Filters are ANDed with the screen's own.** Neither replaces the other, so a
  saved `status = Closed` on a screen filtered to `status = Open` returns
  nothing rather than quietly returning the screen's rows. Frappe's desk does
  the same, and "no rows, and there is my filter" reads better than a filter
  that appears to be ignored. Narrowing is all an extra condition can do, which
  is what makes this safe as well as honest.
* **The operator is a named part, checked against a table.** A filter is
  `[fieldname, operator, value]`. Which operators a fieldtype may use is
  Frappe's own list — `invalid_condition_map` in its filter UI — inverted from a
  deny list into an allow list, because a deny list gives a fieldtype nobody
  thought about every operator, and that is the wrong way round for something a
  browser sends. `regex`, `ilike` and the nested-set operators are in Frappe's
  query layer and not in its filter menu, so they are not here either.
  `tests/test_field_types.py` reads Frappe's file back and fails when the two
  drift.
* **A value has to be the shape its operator takes.** `between` is exactly two,
  `is` is one of two words, `timespan` is one of Frappe's own relative-date
  strings, `in` is a bounded list, everything else is a scalar. A list arriving
  where a scalar belongs is dropped rather than reinterpreted — which is what
  the old rule ("never an operator inside a value") was really protecting, and
  it still holds now that operators have somewhere honest to live.
* **Columns intersect, and their order is kept.** A saved column list is
  filtered against the screen's own; naming `owner` or `_liked_by` drops it
  rather than adding it. The order that survives is the order someone chose,
  because that is the other half of what a column picker is for.
* **`order_by` is rebuilt from parts.** Split into a fieldname and a direction,
  each checked against what the screen offers, and reassembled. The string that
  arrived never reaches the query layer.
* **The same bounds apply before anything is saved**, which is why the controls
  can show their answer immediately: an unsaved change goes through the same
  merge as a saved one rather than being applied in the browser.

A saved view belongs to one screen (`OneSpace Saved View`, keyed on user + app +
view), so it is a preference and never a permission. It also means two screens
over the same doctype keep their own answers.

**A view can be shared, and sharing changes nothing about what it may reach.**
Leaving the row's user empty makes it a layout the whole workspace sees — the
shape Frappe's own `List Filter` uses, where an empty `for_user` means global.
Writing one needs the workspace's admin rights; opening one needs nothing,
because every filter, column and sort in it is re-checked against the screen on
the way out, exactly as a private one is. That "on the way out" is the load-
bearing half: the row is a doctype an operator can write directly, so what it
carries is bounded when it is read rather than only when it was saved.

Nobody edits anybody else's private layout, admin or not. Frappe allows a System
Manager to assign a layout to another user; we have no surface that wants it, so
it is not offered.

**The record dialog shows the screen's whole field list, not the chosen
columns.** Hiding a column is a statement about the list; the record still has
the field, and the server still lets that screen write it.

The shapes of the controls are Frappe's desk too, and deliberately: a customer
who has used one Frappe list should not have to learn a second. A stack of
`[field] [operator] [value]` rows with Add filter and Clear all; a sort that is
a field plus a direction toggle rather than every field listed twice; a column
picker that is the chosen columns in their order, with a grip to drag and
buttons that do the same thing — because a pointer drag reaches neither a
keyboard nor a phone, and order is the whole point of that panel.

One thing worth writing down about the wire: a whitelisted method's **type
annotations are part of the contract**, not documentation. Frappe validates
arguments against them and answers a mismatch with a 417 before the body runs.
When filters became a list of triples and `save_view` still said
`filters: str | dict`, every save from the browser was refused — and every unit
test still passed, because calling the function directly skips the check.
`tests/test_screens.py` now reads the annotations and checks them against the
shapes the SPA actually sends.

### The manifest's fields are a default, not a ceiling

This started as "a screen is an allowlist twice over", and the second `twice`
covered two different things: which *doctype* a screen may reach, and which
*fields* of it. The first is a real boundary — it is the entitlement. The second
was a presentation default doing duty as a permission, and it showed: wanting
the due date on your own list meant a deploy.

So the column picker offers the doctype's own fields, the manifest decides which
are on to begin with, and the bound that remains is Frappe's:

* the doctype must be one the app's manifest granted, checked against the
  DocPerms actually written;
* `get_permlevel_access("read")` decides which fields exist at all here, so a
  screen never becomes a way around field-level permissions;
* `read_only` is not editable and Frappe's bookkeeping is never a column;
* `has_permission` still decides every read and every write.

**Writes moved with it.** The record dialog shows the doctype's whole field list
— hiding a column says nothing about whether the record has the field — and a
control that looks editable and is silently discarded is worse than one that is
not offered. What went is our extra narrowing to the manifest's list; everything
in the list above still holds.

Two consequences worth knowing when writing an app: a field you do not want a
customer to edit needs `read_only` or a permlevel on the doctype, not merely
absence from the manifest; and `fields` is now purely about what the screen opens
with.


## 14. Follow the framework, not the app that inspired it

Frappe CRM is the best worked example of a Frappe SPA there is, and much of this
product's list view is a straight answer to "what does CRM do here". Two of its
answers we took outright: the selection bar floats at the bottom of the screen
rather than pushing the list down, and the saved view lives in the breadcrumb
line rather than in a toolbar — the view you are in *is* where you are.

But CRM's saved views are its own doctype, `CRM View Settings`, built before the
framework had an answer. The framework has one now: `List Filter`, with
`filter_name`, `for_user`, `filters`, `columns` and a sort — and a permission
model (`_can_edit_global_filter`, `_can_update_list_filter`) and sanitisers
(`_sanitize_filters`, `_sanitize_columns`, `_sanitize_sorting`) that we would
otherwise be reinventing line for line.

**So: where the framework and a Frappe app disagree, follow the framework.** An
app's invention was right for the app on the day it was written; the framework's
is what the next version of Frappe will keep working.

But following a model is not the same as using its table, and here we do not.
`OneSpace Saved View` stays our own doctype, for three reasons that are about
shape rather than taste:

* **It is keyed per screen, not per doctype.** `List Filter` is keyed on
  `reference_doctype` plus a `route_signature` — a signature of a *desk URL*,
  which is a thing this product does not have (§7). Two of our screens can sit
  over one doctype and are two different questions; on their key they would
  collide, or we would be encoding our app and view into a field that means
  something else.
* **It carries things theirs has no field for** — which column the rows are
  grouped under, the favourites flag, the page size. The alternative is adding
  custom fields to a framework doctype, and a framework doctype we have added
  fields to is a merge conflict waiting for the next Frappe upgrade.
* **What is worth following is the model, and we do follow it**: a named
  layout, an empty user meaning everybody, `_can_edit_global_filter` and
  `_can_update_list_filter` as the permission rules, and sanitising what a row
  carries when it is *read* rather than trusting what was written. That is the
  part that took Frappe several versions to get right.

Where we did not follow CRM, and why:

* **Column picking** stays a dialog rather than CRM's popover. Ours carries
  width, both pin edges, keyboard reordering and a search over the doctype's
  whole field list; that does not fit a popover, and reordering by drag alone
  reaches neither a keyboard nor a phone.
* **Quick filters** stay Frappe's standard filter row — `in_standard_filter`
  plus the title field, with the `=` / `≈` toggle — rather than CRM's
  configurable set. It is one less thing to configure and it is the answer the
  doctype already gives.
* **Per-view actions** are a group in the same menu rather than CRM's
  hover-revealed `…` on each row. A control that appears on hover is not there
  on a touch screen, and frappe-ui's Menu gained real submenus since CRM worked
  around not having them.


## 15. A view type is declared before it is built

A screen says how it may be looked at — `view_types: list,board` — and the
first is its default. Today exactly one of them is built. A type a manifest
names and nothing can draw is **dropped on the way out** rather than refused:
the screen renders as a list, and the day a board ships the same manifest gets
one without an edit.

The three places that decide this are deliberately three and not one:

| | |
| --- | --- |
| `spaceview.VIEW_TYPES` / `BUILT_VIEW_TYPES` | what the server will resolve and shape |
| `lib/viewTypes.js` | what the SPA can draw, and which component draws it |
| `OneSpace Space Screen.view_types` | what this screen offers |

The first two are checked against each other by a test, because the failure
otherwise is silent in both directions: a type the server offers and the SPA
cannot draw is a blank page, and one the SPA can draw and the server refuses is
a switcher control that does nothing.

**Rows are shaped for a list, and only for a list.** A board wants buckets, a
calendar a date window, a map a point field — none of which `rows()` knows how
to produce. That is not an oversight, it is the order of work: shaping code
with no view to render it is code nobody can look at, and the shape a board
actually needs is a thing you learn by building the board. The seam is where it
belongs — `rows(space_code, screen, …, view_type)` already takes the type and
already carries per-type settings through `view_settings` — so the day a second
type is built, it is a branch in one function rather than a change to the API.

What *is* already general, and is the reason a second type is a small job
rather than a rewrite:

* **The screen resolves once.** Columns, filters, the sort, permissions and the
  saved layout are all decided before any view type is consulted, so a board
  gets the same allowlist and the same bounds a list does.
* **A layout knows which type it is for.** `OneSpace Saved View` carries
  `view_type` and a `view_settings` blob, and every `*_field` in that blob is
  checked against the screen's own columns on the way out — a board's column
  field is a fieldname that reaches a query, and "it came from the settings
  blob" is not a reason to trust one.
* **The shell owns everything that is not the rows.** The header, the
  breadcrumb, the toolbar, the filters, the footer and the selection bar live
  in `ScreenHost.vue`; a view type supplies a body and nothing else.
