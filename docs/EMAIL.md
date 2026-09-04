# Email

What OneSpace does with mail and what it deliberately does not. Companion to §8
of `docs/ONEADMIN.md`, which describes the transport; this describes the product.

Written as a plan and kept as one: §4 is the position it was written from and §5
the seven stages it proposed. All seven are built, so each stage now says what is
in the code — including the one place the plan was wrong, which is Stage 2.

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

## 4. Where we were when this was written

Kept as it was, because §5 is written against it and a plan whose starting
position has been edited to match its outcome is no longer a record of anything.

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

So notifications and OTP already left from our own address. That box was ticked
before any of the seven stages started.

## 5. The seven stages

Each was shippable on its own and none of them needed the next. All are built;
what each says is what is in the code, not what was intended.

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

`<local>@<slug>.4dl.app` — the tenant's slug is a **subdomain**, not part of the
local part.

That one choice deletes a whole subsystem, and the first draft of this document
got it wrong, so it is worth saying plainly. On `<user>.<slug>@4dl.app` the
local-part space is global and the tenants are not, so allocation would belong
to the control plane and would need a registry — one row per address, unique
across every workspace on the platform — or a tenant minting `sales@4dl.app`
would be minting it for everybody. Put the slug in the domain and the namespace
is already per tenant: `sales@acme.4dl.app` and `sales@rua.4dl.app` are two
addresses, uniqueness is the site's own `Email Account` uniqueness, and there is
nothing central to allocate, nothing to keep in step, and nothing to migrate
when a workspace is renamed.

So this is not a registry. It is a local part, validated against
`addresses.LOCAL_PART`, refused if it is in `addresses.RESERVED`, and inserted
on the tenant's own site.

Inbound needs no new mechanism either: the Worker already parses the recipient
and already finds the tenant from the subdomain. It gains one more case — a
local part that resolves to a person rather than to a function — and the site
files the `Communication` against that user rather than against a document.

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

A person connects the mailbox they already have. `oneapp_core/email/connect.py`,
and a panel under Settings → Email that is deliberately not gated on being a
manager: a mailbox somebody connects with their own password is theirs, and an
owner has no more business connecting it than a colleague does.

Here `enable_incoming` **is** right — there is a real IMAP server to poll — so
this is the one place the framework's own receiving machinery runs unmodified.
Nothing reimplements `frappe/email/receive.py`; what is ours is the shape of the
question and the refusals:

* **Four fields, not forty.** Address and password, with the servers filled in
  from the address — `KNOWN` covers Gmail, Outlook, Yahoo, iCloud and Zoho, and
  everything else gets `imap.`/`smtp.` in front of the domain and is told it is
  a guess. The two hostnames are hidden until asked for.
* **The app-password problem, said before it happens.** Google and Microsoft
  stopped accepting account passwords years ago, so `AUTHENTICATIONFAILED` is
  by far the commonest outcome and is useless to somebody who typed the right
  password. `_reason()` turns it into the sentence that fixes it.
* **`UNSEEN` and nothing older.** A mailbox with nine years in it would
  otherwise pull all of it into the site on first sync — minutes of work, a
  storage bill, and nine years of somebody's private mail in a workspace their
  colleagues can be granted access to.
* **Disconnecting stops the polling and keeps the mail.** Somebody disconnecting
  Gmail is saying "stop reading my mailbox", not "delete six months of my work".

**The folders come across, and go back.** `folders.py`. `discover()` runs the
IMAP `LIST` and reads the SPECIAL-USE flags, so the server says which folder is
Sent rather than us keeping a table of every language's word for it; every
folder gets an `IMAP Folder` row with its own UID bookmark, and
`Communication.custom_imap_folder` remembers where each message was filed —
which the framework does not, because `InboundMail` is handed the folder and
drops it.

Two subclasses do the carrying, and they are deliberately small: three methods
on `InboundMail` and one on `Email Account`, which is the single place the
framework holds the folder and the message at the same time. One of the three
is why the Sent folder is not empty — Frappe refuses to import a message whose
sender is the account itself, which is right for an inbox and wrong inside a
Sent folder.

`email_sync_option` is `ALL` rather than `UNSEEN`, and that is what makes the
mirror worth having: an Applicants folder somebody read years ago is empty
under `UNSEEN`. It is safe because `initial_sync_count` bounds the first pass
per folder, off that folder's own UIDNEXT.

It goes the other way too. A folder made here is an IMAP `CREATE` and a
`SUBSCRIBE` — unsubscribed folders are hidden by most clients, which would be a
folder somebody made here and cannot find in Outlook — and filing a
conversation is an IMAP `MOVE`. So the organising is not ours alone; it is
theirs, in every client they use.

**A folder on an address we route is ours, and that is not a compromise.**
`sales@acme.4dl.app` has no IMAP server, so a folder there is a row and a value
on the Communication. There is no second client showing that address to
disagree with it — that is the whole point of §1 — so it is not a lesser folder,
it is the only kind that can exist. Refusing to offer one would mean refusing to
organise the mail we own outright while organising the mail we borrow.

Deleting a folder moves its mail back to the inbox first. IMAP `DELETE` removes
the folder *and* everything in it, which is not what "remove this folder" means
to anybody who has used a mail client with a Trash in it.

**Senders are people.** `people.py`. A list that says
`h.nasser@alreem-consultants.ae` and a list that says **Hala Nasser** with her
face beside it are the same data and not the same product. `Contact` and
`Contact Email` already hold the person, so resolving one is a lookup we get for
free; what is ours is doing it in a batch for the whole page rather than per
row, falling back to initials taken off the address's own separators, and never
reaching a third party. No Gravatar: those work by sending a hash of every
correspondent's address to a company the customer has never heard of, once per
message in the list.

OAuth is the better path where an operator has registered a `Connected App`, and
is not built: the password path works for every provider and the OAuth path
works for two.

### Stage 6 — The Mail screen

Only now, and only because by now there is something to look at.
`oneapp_core/email/mailbox.py` and `pages/Mail.vue`.

Thin on purpose. Mail in this product is already a document — inbound writes a
`Communication`, Frappe's IMAP sync writes a `Communication`, replying writes
one — so there is no mail store to build, only a list to filter and an ordering
to get right. Three things the framework does not answer and this does:

* **Which addresses may I see?** `User Email`, and it is the same answer the
  settings screen writes. The filter is on the query and never on the render,
  and both halves of it — the `filters` dict and the `or_filters` list that
  carries the union of several addresses — come back from `_filters()` together,
  because a caller that took one half would be asking for every `Communication`
  on the site.
* **Threads, not messages.** `Communication` has no thread key, so the subject
  with its `Re:` and `Fwd:` stripped is the grouping — what mail clients did for
  twenty years before message-id threading, and right often enough that being
  cleverer would cost more than it returns.
* **Unread, per person.** `Communication.seen` is one flag for the document,
  which is wrong for an address two people share. So a read receipt is a bounded
  list of ids under the person's own user defaults — not a doctype, because it
  is a question only that person ever asks, and bounded because it is loaded on
  every request they make.

The layout is the one every mail client has had for thirty years — a rail of
addresses, a list of conversations, the conversation — and the reason to keep it
is that nobody has to learn it. A conversation is in the URL, so the back button
closes it, a reload keeps it open, and "look at this one" is something you can
send to a colleague. Frappe Mail's layout was the reference for the shape; the
code is ours.

What is deliberately not here: folders somebody makes, labels, rules, drag and
drop. Mail files itself against the record it belongs to, and a parallel filing
system beside that would be two places to look for the same message.

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

All seven are built. The order they were built in was still the argument above,
and one part of that argument turned out to be wrong in a way worth keeping on
the record: stages 2 and 3 were ordered that way because per-person addresses
supposedly needed an allocation registry that shared addresses would need too,
and building it once for the harder case was cheaper. There was no registry to
build — see Stage 2 — so 2 and 3 collapsed into one list, one validator and one
`create()`, and the ordering bought nothing. The rest held: Stage 1 made every
later address a variation on one that already worked, and Stage 6 came last
because a mail *reader* with nothing to read is the most expensive way to
discover the model was wrong.

Two things named here and not built, both deliberately:

* **OAuth for Gmail and Outlook.** Frappe ships `Connected App`; the password
  path works for every provider and this works for two, so it waits for an
  operator to want it.
* **`Notification` and `Email Template`** — rule, template, recipient. Still the
  biggest single win in the table above, and still deferred.
