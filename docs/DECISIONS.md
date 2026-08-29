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

---

## 8. Roles and permissions

**We ignore the roles ERPNext, HRMS and Payments ship with.** We use those apps
for the business logic they already implement, not for their idea of who an
"Accounts Manager" is. A customer never sees ERPNext, so a role named for
ERPNext's org chart describes nothing they recognise.

OneApp defines its own roles instead. Two kinds:

| Kind | Created by | Editable by customer |
| --- | --- | --- |
| **Recommended** | us, per app, from the manifest | no — sync would fight them |
| **Custom** | the customer, through our API | yes, within the allowlist |

### The manifest is the single source of truth

Each `OneApp App` declares the doctypes it exposes. That one list drives three
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
