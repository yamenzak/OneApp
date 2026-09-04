# Email

What OneSpace does with mail, what it deliberately does not, and the order the
rest gets built in. Companion to §8 of `docs/ONEADMIN.md`, which describes the
transport; this describes the product.

---

## 1. The decision everything else follows from

**We are not building a mailbox.** Cloudflare gives us two things and not the
third:

* **Receive** — a catch-all lands on an Email Worker, which can read the whole
  MIME message, decide, and hand it on. 25 MiB inbound.
* **Send** — Email Sending over SMTP, REST or a Workers binding. 5 MiB, or
  25 MiB to a verified destination.
* **Storage — no.** Email Routing forwards; it does not keep mail, and there is
  no IMAP, no folders, no server-side search. The [limits page][cf-limits] is
  explicit: 200 routing rules per domain, 200 verified destinations per
  *account*, and nothing that resembles a mailbox.

So an address on our domain is not somewhere mail *sits*. It is somewhere mail
*arrives*, and what receives it is the tenant's own site: the Worker POSTs the
parsed message and a `Communication` is written. Everything below is that one
idea applied to more addresses.

This reverses a line in `docs/ONEADMIN.md` — "per-user mailboxes are out of
scope, that is a mailbox product, not a feature" — and the reversal is narrower
than it looks. We are still not running a mail server. We are giving a person an
address that files into the record they already work in.

The 200-limits do **not** bind us, and it is worth being clear why: they count
*forwarding rules* and *verified destinations*. A catch-all to a Worker is one
rule for the whole domain, and we forward to nobody. A thousand people on a
hundred tenants cost one rule and zero destinations.

[cf-limits]: https://developers.cloudflare.com/email-routing/limits/

## 2. What the framework already gives us

Frappe's email surface is larger than it looks and most of this plan is wiring,
not building.

| | What it is | What we use it for |
|---|---|---|
| `Email Account` | A sending and/or receiving identity, with `signature`, `footer`, `default_outgoing`, `append_to`, `create_contact` | Every address in the product, whoever owns it |
| `User Email` | Child table on `User` pointing at an `Email Account` | **Shared mailboxes.** A User has many accounts; an account has many Users |
| `Email Queue` | Batching, retries, unsubscribe, attachment assembly | Everything outbound. Already ours via `enforce_send_rate` |
| `Email Template` | Subject and body with Jinja | Notification bodies, once anybody asks |
| `Notification` | Rule → template → recipient, on document events | The one thing a workspace manager will want early |
| `Communication` | A message filed against a document | What inbound already writes |
| `Email Domain` | SMTP/IMAP defaults shared by accounts on one domain | Bring-your-own-domain, later |
| `Email Rule` | Sender/recipient → what to append it to | Routing inbound without code |

Two of those are exactly the features asked for, already built:

* **Shared access is `User Email`.** Somebody in sales gets a row pointing at
  the `sales@` account and it appears beside their own. There is no new doctype
  to design; the desk has worked this way for a decade.
* **A signature per address is `Email Account.signature`**, with `add_signature`
  deciding whether it is appended.

What the framework does **not** fit is our inbound. `enable_incoming` means
"poll this over IMAP", and we have no IMAP — we have a Worker pushing. So an
internal address is an `Email Account` with `enable_outgoing` on and
`enable_incoming` **off**, and the incoming half stays ours. Trying to make the
poller accept a push is the wrong shape and would fight the framework at every
upgrade.

## 3. What Frappe Mail is, and why we are not using it

`frappe/suite` is **AGPL-3.0**. This repository is MIT. Read it for patterns;
paste nothing. The frappe-ui components it draws with are MIT and come from
frappe-ui directly — that part is fair game, and it is the only part that is.

More to the point: Frappe Mail *is* the mailbox product we said we were not
building. It runs **Stalwart** as the mail server, speaks **JMAP** to it, and
models `JMAP Account`, `Mailbox` (with IMAP-style `may_read_items` /
`may_add_items` ACLs), `Sieve Script`, `Quota`, `Vacation Response`, `Spam Check
Log`. Adopting it means operating a mail server per tenant or a shared one with
per-tenant accounts, plus the deliverability, abuse and storage that come with
it. That is a company, not a feature.

Three of its ideas are worth taking as ideas:

* **`Identity`** — a *send-as* address that carries its own signature,
  `reply_to` and `bcc`, separate from the account that receives. One mailbox,
  several identities. Frappe's `Email Account` conflates the two; where somebody
  needs to send as `accounts@` from their own inbox, this is the shape.
* **`User Account`** — the many-to-many that makes a shared mailbox. The
  framework's `User Email` is the same idea and we already have it.
* **The UI** — a folder rail, a thread pane, and a compose dock that floats over
  the list rather than replacing it. Worth copying as a *layout*; write our own.

## 4. Where we are today

* **Outbound** is Cloudflare Email Service over SMTP
  (`smtps://smtp.mx.cloudflare.net:465`, user `api_token`), one sending identity
  per tenant at `t-<tenant>@mail.4dl.app`, created and reconciled by
  `ensure_email_account()`. Replies come back via `Reply-To`.
* **Inbound** is catch-all → Worker → HMAC POST → `Communication`, with handlers
  for `ap@`, `support@` and `leads@` and a generic fallback that files rather
  than bounces.
* **The routing map** is Cloudflare KV, keyed by tenant slug, written at
  provisioning. KV rather than a call home so a control-plane outage cannot
  bounce customer mail.
* **Rate limiting** is per tenant per hour on `Email Queue` insert.

So notifications and OTP already leave from our own address. That box is ticked.

## 5. The plan

Seven stages. Each is shippable on its own and none of them needs the next.

### Stage 1 — The workspace's own sending address

A manager sets a From address in Settings. Where they set one, it becomes the
default outgoing account and every notification leaves from it; where they do
not, the platform address stays.

Two paths, and the difference is DNS:

* **Ours.** They pick a local part and it is `<something>@<slug>.4dl.app`. No
  DNS for them to get wrong. Sends immediately.
* **Theirs.** They give `billing@theircompany.com` and we hand them the DKIM,
  SPF and DMARC records to publish. Nothing sends from it until we have verified
  the records — sending as a domain that has not authorised us is how a shared
  IP gets listed.

Verification is a control-plane job, not a tenant one: it is the platform's
reputation being spent.

### Stage 2 — An internal address for every person

`<user>.<slug>@4dl.app`, allocated when a member is added.

The local-part space is **global and the tenants are not**, so allocation
belongs to the control plane and needs its own registry — one `OneSpace Address`
row per address, unique on the local part, pointing at a tenant and a user. A
tenant that could mint `sales@4dl.app` for itself would be minting it for
everyone.

Inbound needs no new mechanism: the Worker already parses the recipient and
already finds the tenant. It gains one more case — a local part that resolves to
a person rather than to a function — and the site files the `Communication`
against that user rather than against a document.

Outbound sends through the same Cloudflare identity with the person's address as
the From.

### Stage 3 — Shared addresses

`sales@`, `accounts@`, `info@`. A manager creates one and grants it to people;
each of them sees it beside their own.

This is `Email Account` plus `User Email` rows and no new model. What we build is
the *granting*: a screen in Settings listing the workspace's addresses and who
may use each, writing `User Email` rows. Removing a grant removes the row.

The one real question is what "access" means for mail that has already arrived.
`Communication` is a document with ordinary permissions, so the honest answer is
a User Permission on the address — a person removed from `sales@` stops seeing
its history too. Anything else means two permission systems disagreeing.

### Stage 4 — Signatures

`Email Account.signature` per address, edited wherever the address is. The
platform address has none; a workspace address has the workspace's; a person's
has theirs.

Worth doing at this point rather than earlier because it is the first thing
somebody notices is missing, and it is one field.

### Stage 5 — Bring your own mailbox

A person connects the mailbox they already have: Gmail or Outlook by OAuth
(Frappe ships the connected-app flow), or plain IMAP/SMTP for anyone else.

Here `enable_incoming` **is** right — there is a real IMAP server to poll — so
this is the one place the framework's own receiving machinery runs unmodified.
It is also the stage that makes the product useful to somebody who will never
give up their address, which is most people.

### Stage 6 — The Mail screen

Only now, and only because by now there is something to look at.

A screen over `Communication`, which means the four view bodies we already have
draw most of it. What is genuinely new is the reading layout — a folder rail,
a thread, a compose dock — and it is bespoke enough to be a
`component:` screen rather than a declared one. Frappe Mail's layout is the
reference for the shape; the code is ours.

### Stage 7 — What we owe the platform regardless

None of this is optional and none of it is visible:

* **Bounces and complaints.** A shared sending identity means one tenant's bad
  list degrades delivery for everyone. We need the feedback loop wired to
  suppression, and a suppression list that outlives the tenant.
* **DMARC** on our own domains, and alignment for anyone sending as theirs.
* **Rate limits per tenant** — partly done, per hour on the queue; needs a daily
  ceiling and a per-recipient one.
* **Suspension.** A suspended workspace must stop sending before it stops
  everything else, and its inbound must be rejected at the Worker rather than
  accepted and dropped.

## 6. What we take from Frappe's mail settings

Into the workspace's Settings, as OneSpace settings rather than desk forms:

| From | What it is |
|---|---|
| `Email Account.signature`, `add_signature` | Per-address signature |
| `Email Account.footer` | A workspace-wide footer, once |
| `Email Account.always_use_account_email_id_as_sender` | Already set on ours |
| `Email Account.track_email_status` | Open tracking, off by default and a decision to make deliberately |
| `Email Account.send_unsubscribe_message` | Required for anything bulk |
| `Email Account.auto_reply`, `enable_auto_reply` | Out of office, cheap and expected |
| `Email Account.create_contact` | Whether inbound creates Contacts |
| `Email Account.append_to`, `Email Rule` | Which doctype an address files into — this is what makes `ap@` work today, and a manager should be able to add their own |
| `Notification` | Rule → template → recipient. The biggest single win, and deferred earlier |
| `Email Template` | Bodies for the above |

Left in the framework: `Email Domain`, `IMAP Folder`, `Auto Email Report`,
`Newsletter` and `Email Group`. The first two are plumbing for Stage 5 and
belong beside the connection rather than in Settings; the rest are a marketing
product we have not been asked for.

## 7. Order, and why

Stage 1 first because it is small, it is what a manager asks for on day one, and
it makes every later address a variation on one that already works. Stage 2
before 3 because the allocation registry that per-person addresses need is the
same one shared addresses need, and building it once for the harder case is
cheaper. Stage 5 could come at any point and probably should come early if the
first customers already live in Gmail. Stage 6 last, always: a mail *reader*
with nothing to read is the most expensive way to discover the model was wrong.
