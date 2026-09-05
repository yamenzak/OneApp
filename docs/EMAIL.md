# Email

What OneSpace does with mail and what it deliberately does not. Companion to §8
of `docs/ONEADMIN.md`, which describes the transport; this describes the product.

Written as a plan and kept as one: §4 is the position it was written from and §5
the seven stages it proposed. All seven are built, and an eighth was added
afterwards — so each stage now says what is
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

`frappe/suite` is **AGPL-3.0**, and so is this repository — but it was MIT when
this was written, so the mail that shipped is ours and nothing in it is derived.
The prohibition has lifted; this paragraph is why the code looks the way it
does. The frappe-ui components it draws with are MIT and come from
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
before any of the stages started.

## 5. The stages

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
* **Threads, not messages.** `Communication` has no thread key, so we gave it
  one: `custom_thread`, written on insert by `email/threading.py`, which walks
  `in_reply_to` and inherits the parent's key. Where the headers are there that
  is real message-id threading; where they are not it falls back to the subject
  with its `Re:` and `Fwd:` stripped, which is what mail clients did for twenty
  years before. Both grouping keys are read on the way out, because one thread
  can hold messages from either side of the upgrade.
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

That paragraph used to end by ruling out folders, labels and rules on the
grounds that mail files itself against the record it belongs to. That was right
about *our* filing and wrong about everybody else's: somebody arriving with ten
years of Outlook arrives with their folders, and a reader that cannot show them
is a reader they cannot move to. Stage 8 is what that turned into.

### Stage 9 — Telling somebody when something happens

`Notification` is the framework's own rule → recipients → message on a document
event, with a scheduler for the date-relative ones and a `System Notification`
channel that writes the same `Notification Log` the bell already reads. None of
that is reimplemented. What is ours is `oneapp_core/alerts.py`: the gate, the
scope, and a much smaller shape.

A rule is one sentence — *when a Project is past due by 3 days, tell the
accounts role, and say this* — and the settings panel is that sentence. Frappe's
own form offers eight events, four channels, a filters JSON, a property to set
afterwards and a Slack webhook; this offers five events, two channels, and
recipients that are a role or a field on the document.

**The condition is compiled, never typed**, and that is the whole reason the
module is shaped this way. `Notification.condition` is `frappe.safe_eval`'d with
the document in scope, so a text box would be a text box that runs code. A
field, an operator and a value go in; `_condition` builds the expression and
`_decompile` reads it back so the form can reopen on it. The string stays the
only copy, because two places holding one fact is two places to disagree.

Ours are marked with `Notification.custom_onespace`. `is_standard` was the
obvious flag and is the wrong one: Frappe ships two non-standard Notifications
of its own on every site, and the platform's error alerts in a customer's
settings page is a bug the first customer would report.

### Stage 8 — The rest of a mail client

Stage 6 was a reader. This is the difference between a reader and something
somebody moves to, and it was built in five batches after the question "what is
left for a fully functional email client?" turned out to have a ten-item answer.

**A list that does not stop at fifty.** Fifty conversations a page, a Load more
under them, and a search that reads the body rather than the subject — a mail
search that cannot find a phone number somebody sent you is not a search. Body
search is two queries because it has to be: `_matching()` finds names by content
without an address scope and hands them to the scoped query as an `in`, so the
unscoped half can only ever answer with ids. New mail arriving lands through the
same socket the lists use, so a reader left open is a reader that is current.

**Acting on a conversation.** Delete, archive, mark unread, star. Star is a user
default like the read receipts, and for the same reason: it is a question only
the person asking ever asks, and an address two people share must not have one
person's stars on it. Delete and archive both go out over IMAP where there is a
server — `MOVE` if the server has RFC 6851 and `COPY` plus `STORE \Deleted` if
it does not — so a conversation binned here is binned in Outlook.

**Writing.** A composer with rich text (the same `Editor` a Text Editor field
gets, because mail is prose and a textarea sends one long line), Cc and Bcc
behind a toggle, attachments out as well as in, forward carrying the original's
files, and replies quoting what they answer. Recipients are people rather than a
comma-separated string: `people.suggest()` searches `Contact` and everybody the
workspace has corresponded with, which is an address book that needed no
building and syncs with nothing.

Two of the three composer promises are kept on the server rather than in the
browser. A draft is held under the person's own user defaults and restored when
the composer reopens, so closing it by accident is not a decision. And Undo is
`Email Queue.send_after` set fifteen seconds out — the message really is held,
the queue's picker really does refuse it, and `unsend()` refuses to promise
anything once any row has left `Not Sent`. A countdown in the browser that a
closed tab defeats would have been a lie about the one thing the button exists
to promise.

**A phone.** The list and the conversation are one column that swaps, not two
columns squeezed. The rail became the shell's own sidebar, which is where a
phone already looks for navigation.

**Threading, out of office, and rules.** `Communication.custom_thread`, written
on insert by walking `in_reply_to` — real message-id threading where the headers
are there, the stripped subject where they are not. Out of office is
`Email Account`'s own `auto_reply` with a date we clear on a daily job, so
"until Monday" ends on Monday without anybody remembering. And a rule is four
words — look at this field, for this text, file it there — because somebody
sorting their own mail is not asking for a query builder. `Mail Rule` is ours;
Frappe's `Email Rule` is an allow/block list on an address and answers a
different question.

What is still not here, both deliberate: **push notifications**, which wait on
the EU-jurisdiction question, and **`Notification` plus `Email Template`**,
which is the row still open in §6.

### Stage 10 — Frappe Mail's client, taken where it is better than ours

`frappe/mail` is AGPL-3.0 and so are we, so the question stopped being whether
we could copy it and became which parts are worth copying. Four were, and the
criterion each time was the same: take what has no framework under it, and
reseam the layer that fetches.

**The reader is theirs, vendored.** Ours rendered a stranger's HTML with `v-html`
into our own document, and held remote images back with a regex over the raw
markup. Measured against six ordinary shapes — a `srcset`, a CSS background, a
`<style>` block — that regex held two and leaked four while the banner above it
said the images were blocked. Theirs is DOMPurify, then a DOM pass that stashes
each remote `src` on `data-blocked-src`, then a `srcdoc` iframe that grows to
its own height. See `components/mail/reader/VENDORED.md`; the measurement that
made us take it is `assets.test.js`, which is ours.

**An attachment says how big it is.** It was an anchor with a paperclip: no
size, though the server always sent one, and no way to look without downloading
first. It is a control now — kind icon, name, size — and clicking opens the
Drive's own previewer, because a mail attachment *is* a Drive file: the same
`File` row, the same object, the same permission check on the way to the bytes.
The one part of their shape not taken is the hover-to-download swap, which is
unreachable on a touch screen.

**A conversation opens where the new mail is.** Every message used to be drawn
open, oldest first, which on a thread of fifteen is a wall. Now a message
already read is one row — who, the first line, when — a run of four or more
read messages folds behind "N earlier messages", and a line marks where the
unread begins. Ours differs from theirs in one place, in `components/mail/
thread.js`: their fold collects every read message in the thread, so it can
swallow one *below* the new-mail mark and the count then describes messages in
two places; ours folds one contiguous run and it is the run above the line.
Whether a message counts as read is the server's answer, computed before the
browser marks the thread read a moment later.

**A selection, and the way back from one.** Reading a morning's post is the same
three actions forty times. Rows tick, shift takes a run, and the bar over the
list archives, bins, unreads or stars all of them in one request —
`mailbox/selections.py`, which is a loop on the server rather than forty round
trips from the browser. It keeps a note of where every conversation was, and
that note is what Undo reads. The keys are Gmail's, because Frappe Mail's are
Gmail's and so are Outlook's: `j` `k` to move, `e` to archive, `#` to bin, `u`,
`s`, `c`, `r`, `/`, and `?` for the list of them. Two rules keep them safe, in
`lib/shortcuts.js`: never while somebody is typing, and never over a dialog.

**The composer signs, and the reader says who else was on it.** Two things the
product had and used neither of. The signature people typed into settings was
stored on the address and never inserted — while Frappe's own rule appended the
*default outgoing* account's signature to everything, after the message left the
composer, where nobody could see it happen; on a workspace whose notifications
leave from `hello@`, a reply from `sales@` went out signed by `hello@`. The
framework's rule is held off entirely now (`email/signatures.py`, a `before_save`
hook) and the address's own signature goes in when the composer opens, above the
quoted history, editable like the rest of the message — and it changes when the
From does. And `cc`, fetched on every message and rendered on none, is on the
message header: who else saw this decides whether a reply goes to one person or
to six.

Two bugs fell out of building it, both older than it. A draft is held in a user
default, and Frappe stores those through its own HTML sanitiser — so a draft
containing any quoted attribute (`class="x"`, or a link, or an inline image)
came back with `&quot;` where the quotes were, which is no longer JSON, and
*every* composer opening after that was a 500 for that person until somebody
cleared the value by hand. Drafts are base64 now, and a draft that will not
parse is a draft that is gone rather than an error. The other: the reply
attribution line read "On 2026-09-04 20:48:15.232563, Hala Nasser wrote:",
microseconds and all, in a message going to a customer.

The one thing that had to change underneath: **an inbox no longer holds what has
been put away**. The inbox view was every received message on an address and did
not care what folder it was in, so Archive filed the conversation and left it
exactly where it was in the list — and so did Move to Trash. `PUT_AWAY` in
`mailbox/query.py` is the three quiet folders plus the archive, excluded by
folder *name* because one mailbox's archive is `Archive` and another's is
`[Gmail]/All Mail`. Filing still needs to reach mail wherever it is, so moving a
conversation asks for the `EVERYWHERE` scope instead — which is how Undo came to
work at all.

### Stage 7 — What we owe the platform regardless

None of this is visible and all but one of it is built. `enforce_send_rate` on
`Email Queue` is where three of the four live, cheapest gate first:

* **Suspension.** `_suspended()` reads the synced status, and a suspended,
  cold or archived workspace stops sending before it stops anything else —
  sending is what spends the platform's reputation and the one thing a
  suspended customer must not keep doing.
* **Rate limits per tenant** — per hour, per day and per recipient, counted on
  `Email Queue` inserts because Frappe queues one document per send.
* **Bounces and complaints.** `suppression.py`, wired both ways: a permanent
  SMTP failure is read off the queue row by `on_queue_failure`, and a delivery
  report or an abuse report arrives at the Worker and never becomes
  correspondence. `_drop_suppressed` takes suppressed addresses off a message
  rather than refusing the whole thing — one bad address in forty must not lose
  the other thirty-nine.

**DMARC** is the one still outstanding, and it is DNS rather than code: records
on our own domains, and alignment for anyone sending as theirs.

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

All eight are built. Stage 8 was not in the original seven — it is what the
question "what is left for a fully functional email client?" turned into, asked
once the first seven were done and there was something real to answer it about.
The order the seven were built in was still the argument above,
and one part of that argument turned out to be wrong in a way worth keeping on
the record: stages 2 and 3 were ordered that way because per-person addresses
supposedly needed an allocation registry that shared addresses would need too,
and building it once for the harder case was cheaper. There was no registry to
build — see Stage 2 — so 2 and 3 collapsed into one list, one validator and one
`create()`, and the ordering bought nothing. The rest held: Stage 1 made every
later address a variation on one that already worked, and Stage 6 came last
because a mail *reader* with nothing to read is the most expensive way to
discover the model was wrong.

Three things named here and not built:

* **OAuth for Gmail and Outlook.** Frappe ships `Connected App`; the password
  path works for every provider and this works for two, so it waits for an
  operator to want it.
* **DMARC records**, per Stage 7.
* **`Email Template`.** A rule carries its own subject and message, which is
  what somebody writing one wants; a library of reusable bodies is a second
  screen nobody has asked for yet.

And one that is a different document: mail against a *record* — what links a
message to a document, and where an AI lane earns its cost — is
`docs/DOCUMENT-MAIL.md`. Its deterministic half is built; its model half is not.
