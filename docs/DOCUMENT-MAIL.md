# Mail against a document

`docs/EMAIL.md` is the mailbox: addresses, folders, threads, the reader. This is
the other half — the mail that belongs to a *record*, and what an AI lane can
honestly do about it that Frappe's own linking cannot.

Written as a study and kept as one. §1–3 are what was in the code and in the
framework when it was written, checked rather than remembered. §4 is where the
ceiling is. §5–7 are the proposal, ordered by value rather than by novelty, and
§5 is deliberately first because most of the win is not AI.

**A1–A4 are built.** §5 says what each one turned into; §1 is left as it was,
because a study whose starting position has been edited to match its outcome is
no longer a record of anything.

---

## 1. Where we actually are

Mail in this product is already a `Communication`, and the reader around it is
finished. What is missing is one thing, and it is the thing this document is
about: **nothing links a message to a document.**

Four findings, each verifiable:

* **Inbound files against a doctype and never a document.**
  `inbound.handle_address` calls `_communication(payload,
  reference_doctype=account.append_to or None)` — `reference_name` is not a
  parameter it passes. So an address with `append_to = "Purchase Invoice"`
  records that the message is about *a* purchase invoice, and not which one.

* **The four built-in handlers set neither.** `handle_supplier_invoice`,
  `handle_support`, `handle_lead` and `handle_generic` each write a bare
  Communication and return `{"queue": "supplier_invoice"}` or similar. Nothing
  reads `queue`. It is a label on a return value.

* **Replies inherit a link that was never set.** `mailbox/sending.py` copies
  `parent.reference_doctype` and `parent.reference_name` onto a reply, which is
  exactly right and currently copies two nulls.

* **A record has no correspondence.** `spaceview/surround.timeline()` returns
  comments, versions and likes. There is no reader for a record's mail, no
  composer on a record, and no tab for either. A person looking at
  `PO-2025-0088` cannot see the four emails about it, and a person reading those
  four emails cannot get to it.

And one finding that matters more than it looks: **the AI lane is complete and
entirely unused.** `hooks.py` has `ai_features = []`, with a comment saying so.
The gateway, the credit hold and settle, the per-workspace model choice, the
capability-filtered picker, the operator registry and the reconciliation are all
built and shipped. Nothing calls any of it. Whatever we do here will be the first
feature through that lane, which is an argument for choosing it carefully and
against choosing four at once.

## 2. What the framework gives us, precisely

Frappe's document-mail linking is larger than `reference_doctype` and it is worth
being exact about, because three of the four mechanisms we are not using.

**The single link.** `Communication.reference_doctype` / `reference_name`. One
document per message. This is what the desk timeline reads and what `append_to`
fills in.

**The many links.** `Communication.timeline_links`, a child table of
`Communication Link` rows, each a `link_doctype`/`link_name` pair. This is how
one message shows on the contact, the deal and the invoice at once. Frappe fills
it from two places: every `Contact` matching an address on the message, and then
every `Dynamic Link` those contacts carry —
`add_contact_links_to_communication`. **We write nothing to it.** Neither
`timeline_links`, `Communication Link`, `email_append_to` nor
`enable_automatic_linking` appears anywhere in this repository.

**Plus-addressing.** `parse_email_for_timeline_links` reads
`someone+doctype=docname@example.com` (RFC 5233 sub-addressing), resolves it, and
sets both the timeline link and — if there is not one — the primary reference.
Gated on an `Email Account` with `enable_automatic_linking`. Exact when it fires,
and it fires only when we generated the address in the first place.

**Reply resolution.** `InboundMail.reference_document()`, three strategies in
order:

1. `in_reply_to` matches an `Email Queue` row we sent, and that row carries its
   own reference — exact, and the reason a reply to a system notification lands
   on the right document.
2. `get_reference_name_from_subject()` — the name after the last `#` in
   `Re: Your invoice (#PINV-2025-0041)`.
3. `match_record_by_subject_and_sender()` — the doctype's declared
   `subject_field` and `sender_field` matched against the message, bounded by
   record age, with a documented special case for a system user replying from
   Outlook with the threading lost.

So the framework's linking is **exact, syntactic, or contact-graph**. It resolves
a reply we can trace, a name somebody left in a subject line, an address we
minted, or a person we already know. It never reads the message.

## 3. What we added on top

Two custom fields on `Communication`, both in `install.create_custom_fields`:
`custom_thread` (the conversation key, walked from `in_reply_to`, falling back to
the stripped subject) and `custom_imap_folder` (where the message was filed on a
real IMAP server, which the framework drops).

`custom_thread` matters here more than it did in the mailbox. It is a stable key
across a whole conversation, which means **a link established once for a thread
can be inherited by every later message in it** without re-deciding. That is the
cheapest correct linking mechanism available to us and we are not using it.

## 4. Where the ceiling is

Three failures, chosen because each is a real case in the space we are building
for and none of them is solved by anything in §2.

**First contact about an existing thing.** "Please find attached invoice 4471
against your PO-2025-0088." No `in_reply_to`, no `#(...)` token, and the sender
is `accounts.new@supplier.ae` rather than the contact we hold. Frappe files this
nowhere at all, and it is the single most common inbound shape for `ap@` — which
is the address `docs/EMAIL.md` calls the highest-value one we have.

**One message, several documents.** A supplier statement listing eleven
invoices; a consultant's letter answering three RFIs. `reference_name` is
single-valued and `timeline_links` could hold all eleven, but nothing puts them
there, and the contact graph would link the message to that supplier's other four
hundred invoices rather than to the eleven it names.

**The contact graph over-links.** `add_contact_links_to_communication` attaches
a message to everything its sender is linked to. That is the right default for a
CRM, where a contact has a handful of deals. It is the wrong default for
accounts payable, where it produces a timeline entry on every invoice a supplier
has ever issued.

The common shape: the answer is **in the prose**, and every mechanism the
framework has stops at the envelope.

## 5. The half that is not AI, and came first

Four changes, none of which spends a credit, and all of which are prerequisites
rather than alternatives — a model cannot link a message to a record on a product
with nowhere to show the link, and cannot be evaluated on a site with no linked
mail to compare against. All four are built; what each says is what is in the
code.

**A1 — a thread inherits its link.** `linking.from_thread`. A message joining a
`custom_thread` that already has a reference takes it: one query, exact, and it
covers every reply in a conversation that was placed once. It reads the thread
key rather than `in_reply_to`, so it still finds the answer where a reply arrived
with its headers stripped and was threaded on the subject instead. This is where
the two nulls copied by `mailbox/sending.py` started being two values.

**A2 — `timeline_links` is the storage.** `linking.add`. Many links per message,
with `reference_doctype`/`reference_name` kept as the primary — the first link —
so the desk, the framework's own timeline and `append_to` all keep working. Each
row carries **how it was made** in `custom_linked_by`: `thread`, `text` or
`manual` today, and a fourth for a model when there is one. A link nobody can
explain is a link nobody will trust, and the ones made without a person are
exactly the ones that have to be distinguishable to be reviewable.

**A3 — the record's correspondence.** `spaceview/mail.py` and `RecordMail.vue`,
a tab beside Activity rather than inside it: a comment is something a colleague
said in here and a message is something somebody said from outside, and merging
them loses the distinction that matters most about correspondence. **Sending
from a record files the message against it** with no inference at all, through
the composer that already existed — one `about` prop, not a second composer.

**A4 — deterministic extraction, which Frappe does not do.** `linking.from_text`.
The site knows every naming series it issues, so the prefixes are a small exact
vocabulary: `PINV-`, `LTR-`, `MR-`. Every candidate is then checked against the
database, because a prefix match is a guess and `db.exists` is not — and the
scope is `sync.granted_doctypes()`, so a stranger writing a plausible id cannot
file their message against the platform's own bookkeeping. The quoted history of
a reply is cut off before scanning: those ids were found when those messages
arrived, and reading them again links a one-line reply to everything the
conversation ever mentioned.

Frappe reaches none of these four. Its subject scan looks only inside `#(...)`,
which is a token we put there and a stranger never will.

## 6. What the AI lane is actually for

Once A1–A4 have run and found nothing, what is left is the case where the answer
is in prose that does not quote an id. That is a real and valuable residue —
"the drawings you sent for the tower", "our meeting about the Reem villas" — and
it is where a model earns its cost.

The shape that matters: **retrieve deterministically, then rank with a model.**
Never "here is an email, which of our records is it about?" — that is a
hallucinated foreign key on a financial document. Instead: build a candidate set
by rules (the sender's domain and its parties, documents carrying any extracted
number, documents recently touched by the same people, top-k by embedding), then
ask the model to choose among candidates it can see, and to say why.

**B1 — `mail.link`.** Choose among candidates, return a choice, a reason and a
confidence. Above a high threshold it links; below it, the message lands in a
"needs a home" queue with the model's suggestion pre-selected and one click to
confirm. The suggestion is the product; the automatic link is the optimisation.

**B2 — `mail.extract`.** The `ap@` case done properly: a PDF attachment read with
Image Understanding into supplier, invoice number, date, currency, total and
lines, producing a **draft** Purchase Invoice with every field showing where it
came from. ERPNext underneath is what makes this worth more than everything else
in this document combined, and the draft-and-review shape is what makes it
safe.

**B3 — `mail.summary`.** A thirty-message thread as a paragraph at the top of the
record. Cheap, uncontroversial, and the one people notice first.

**B4 — `mail.draft`.** A reply drafted from the record's own data. Last
deliberately: it is the demo feature and the least valuable one, and it is the
one most likely to be wrong in a way that goes out over the customer's name.

**Embeddings are the quiet one.** The catalogue already syncs and prices
`Text Embeddings`, and nothing uses it. An embedding per record turns "which of
four thousand projects" into a top-k, which is the retrieval half of B1 and is
useful to search long before it is useful to linking. It is the cheapest
capability we have already paid to plumb.

## 7. What has to be true, and what it costs

Five constraints. The first is the one that could sink the feature and it is not
technical.

**A link must not grant read.** A `Communication` is shared with the holders of
the address it arrived on — `inbound._share` writes a `DocShare` per holder.
Linking it to a document must not make it readable to everyone who can read that
document, or "file this against the project" becomes a way to publish somebody's
mail to the workspace. The record's correspondence tab filters by the reader's
own access to each message, not by their access to the record.

**Deterministic first, always.** Every inbound message through a model is a
per-message credit charge on a workspace that did not press a button. The gate is
A1–A4 finding nothing, and the address having it switched on. `max_credits` per
feature is already enforced by the decorator.

**Every model link is reversible and explains itself.** `by: model` plus the
reason, on the link row. Nobody will let an AI touch their accounts payable
because it is usually right; they will let it because they can see what it did
and undo it in one click.

**Nothing writes to a submitted document.** Extraction produces drafts. An
extractor that amends a submitted Purchase Invoice is a bug with an audit trail
attached to it.

**Message bodies to a third party is a different consent from a summarise
button.** Metering an in-app AI action is something a person chose in the moment;
piping every inbound message through a provider is a standing arrangement about
other people's correspondence. This is the same EU-jurisdiction question that is
holding push notifications, and it should be answered once for both rather than
twice differently.

## 8. Order, and the recommendation

1. **A1, A2, A3** — thread inheritance, many links with provenance, and the
   record's correspondence tab with sending. No credits, and they are what make
   everything after them possible and measurable.
2. **A4** — naming-series extraction. Still no credits, and it is the largest
   single jump in how much mail gets placed.
3. **B2 — `mail.extract`.** First through the AI lane, because `ap@` is where the
   money is and because draft-and-review is the shape that earns trust.
4. **Embeddings, then B1 — `mail.link`.** Retrieval before ranking, suggestion
   before automation.
5. **B3, B4** — summary, then drafting.

The thing to resist is doing 3–5 first because they are the interesting part.
The interesting part does not work without 1 and 2, and cannot be shown to work
without something to compare it against.
