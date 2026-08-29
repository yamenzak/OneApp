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
