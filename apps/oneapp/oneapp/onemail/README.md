# OneMail

The workspace's mail: the addresses it owns, the mailboxes people already had,
the screen they read both in, and the thread of correspondence that ends up
attached to a quotation because that is where somebody will look for it.

Who opens it: everybody. Mail is the one surface in this product that a person
who does not care about any of the rest still uses every day — and it is the
one that talks to people *outside* the workspace, which is why more of this
module is about refusing to do something than about doing it.

`docs/EMAIL.md` is the platform argument — Cloudflare, one domain, why Frappe
Mail is not the answer, the stages. `docs/DOCUMENT-MAIL.md` is the argument for
mail that belongs to a *record*. This file is the module: its nouns, the
decisions inside it that cost something, and what is not built.

---

## 1. The model

**There is no mail store.** That is the decision the whole module rests on and
it was made by the framework, not by us: Frappe writes a `Communication` when
its IMAP sync pulls a message, when somebody sends one, and when a reply comes
back. So mail in this product was already a document with a timeline, a
permission model, an attachment table and a link to a record — and building a
second store would have been building all of that again, worse, beside it.

What the module is, then, is the questions the framework does not answer.

| | |
|---|---|
| **Email Account** | An address. Frappe's, unchanged. |
| **User Email** | A person's access to one — a child table on `User`, so an address has many people and a person has many addresses. A shared mailbox, a decade old, that nobody here had to design. |
| **Communication** | A message. Frappe's, plus four custom fields: the thread key, the folder, how a link was made, and whether it was read. |
| **Communication Link** | What the message is about. Frappe's child table; the provenance column is ours. |
| **Correspondence** | A letter *as a record* — the outward half, for a workspace that files formal correspondence against a project. |
| **Mail Rule** | One condition, one destination. |

Two of those four custom fields are worth their own paragraph.

**`custom_thread`.** `Communication` has no thread key. Mail arrives as
messages and is read as conversations, so we gave it one, written on insert by
walking `in_reply_to` up the chain. Where the headers are there it is real
message-id threading; where they were stripped it falls back to the subject
with `Re:` and `Fwd:` taken off. Both are read on the way out, because one
thread can hold messages from either side of that upgrade.

**`seen`, per person.** Frappe's `Communication.seen` is per *document*, which
is the wrong shape for a shared address: two people on `sales@` each need their
own idea of what they have read. `Document Follow` is not it either. So unread
is a read receipt of our own — and deliberately not a doctype, because a table
with a row per person per message would exist to answer a question only that
person ever asks.

---

## 2. The layers

Server, in import order. A module may use the ones above it and never below.

    addresses    who may send as what, who may read what, what it signs with
    verify       sending as a domain the customer owns — and not until DNS says so
    connect      the mailbox somebody already had, over IMAP
    folders      the folders they had already sorted it into
    threading    which conversation a message belongs to
    linking      which records it is about, by rule
    filing       which record it is about, when no rule can tell (a model ranks)
    inbound      what the Cloudflare Worker posts here
    outbound     rate limiting, which is the only part of sending that is ours
    suppression  bounces and complaints, and not sending there again
    rules        filing rules and the out-of-office
    people       a sender as a person rather than an address string
    faces        a picture for one, fetched once, served from here afterwards
    signatures   whose signature goes on, which is not Frappe's answer
    templates    a message written once and sent often
    intelligence what mail asks a model for
    mailbox/     reading and writing — its own package, its own layering

`mailbox/` is a package because reading mail is most of the screen:
`scope` → `flags` → `query` → `reading` → `filing` → `selections` → `sending`
→ `drafts` → `composing`. Its own `__init__` carries that map.

Browser, at `frontend/src/modules/onemail/`: one page (`Mail.vue`), the
composer, the thread, the sidebar, a recipient field, and `reader/` — the
sandboxed iframe a message body is rendered in.

---

## 3. The decisions that cost something

### The permission filter is on the query, never on the render

`_filters` returns both halves of its filter together — the folder *and* the
set of addresses this person holds — because a caller that took one half would
be asking for every `Communication` on the site. That is a strange-looking API
and it is deliberate: the shape makes the dangerous call impossible to write by
accident, which a comment saying "remember to also filter by address" does not.

The same rule appears in `spaceview/mail.py` as one word: `get_list`, not
`get_all`. A link is not a grant. Filing a message against a project must not
publish it to everybody who can open the project, so the record's
correspondence is scoped to what the *reader* may already see and the record is
a filter on top.

### A message body is rendered in a sandbox, and remote assets are blocked

An email is HTML a stranger wrote. It is rendered in a `sandbox=""` iframe with
DOMPurify in front of it, and images are not fetched until somebody asks —
because a tracking pixel that loads on open tells a sender when a person read
their message and from where, and a mail client that does that by default is
doing it on the customer's behalf without asking.

### Nothing about a correspondent leaves the site, with one amendment

`people.py` resolves a sender locally. The thing it forbids is what nearly
every other product does: a Gravatar URL *in the page*, so that drawing a list
of fifty conversations tells a third party who fifty of the customer's
correspondents are, on every render, from every reader's browser.

`faces.py` is the amendment, and it is written as one rather than hidden behind
a switch: one request, made by the *server*, the first time a Contact is saved
without a picture, stored as a `File` and served from here forever after. What
leaves is a hash of one address and sometimes one domain name, once per
contact, ever. It is off unless an operator turns it on.

### Threading on headers, not on the subject

Subject threading is wrong in both directions and neither failure is rare: two
people who each write "Invoice" become one conversation, and a reply somebody
renamed becomes a new one. The headers have said it properly since RFC 822.
The subject is the fallback, not the rule.

### One condition per rule

A rule builder that can express `(A or B) and not C` is a builder nobody uses
to express anything. The rules people actually write are "from the architect"
and "with LPO in the subject", and two rules are the answer to two conditions.

### Suppression exists to protect the platform, not out of politeness

Every workspace sends through one Cloudflare identity, so deliverability is a
*shared* resource: one tenant importing a bought list and hitting five hundred
dead addresses moves the spam score for every other tenant on the same domain.
A hard bounce and a complaint are permanent; a soft bounce is not a signal.
Rate limiting in `outbound.py` is there for the same reason and stays ours
whatever the transport becomes.

### Sending as the customer's own domain waits for DNS

Putting `billing@theirs.com` on outgoing mail means asserting to every
receiving server in the world that we may send as them. The only thing that
makes that assertion true is DNS they publish, and the only thing that makes it
safe is refusing to send until they have. SPF, DKIM and DMARC each fail
differently when missing, and the worst of the three failures is the quiet one
— "some of it goes to spam", and nobody can tell you which.

### The folders come across

A person who has used an address for nine years has *sorted* it. Pouring
Applicants, Suppliers and Archive into one flat list takes their filing system
away and calls it a feature. Frappe already syncs folder by folder with a UID
bookmark on each; what it does not do is ask the server what folders exist, so
`discover()` runs the IMAP `LIST` and reads the SPECIAL-USE flags rather than
having somebody type the names in.

### The signature belongs to the address, not the sender

Frappe signs in `before_save` with the sender's `User` signature and failing
that the site's default outgoing account. On a workspace whose notifications
leave from `hello@`, a reply written from `sales@` went out signed by `hello@`
— appended after the message, so nobody could see it happen. Ours goes on in
the composer, where somebody can see it and delete it.

### Linking is exact, then deterministic, then a model — in that order

`linking.py` does not guess. The conversation already has a reference, or an id
this site issues appears in the subject or the body, or nothing. The residue it
leaves — prose naming no id — is what `filing.py` is for, and a model is worth
nothing until the cases that do not need one are handled without it.

When a model is used it is never asked the open question. It is handed a
shortlist that history and retrieval produced, every candidate a record that
exists and that this reader may open, and asked which of *these*. Above its
confidence threshold the link is written with `custom_linked_by="model"` so a
person reading the record's correspondence can see which links a machine made
and take any of them back; below it, a card nobody has answered. See
`docs/DOCUMENT-MAIL.md` §6 for the two places that deviates from the plan and
why.

### An unrecognised recipient is filed, not bounced

`ap@`, `support@` and `leads@` mean something. Anything else is accepted and
filed as an ordinary `Communication`, because bouncing a customer's mail is
worse than filing it somewhere slightly wrong.

---

## 4. What is not built

In the order it blocks.

1. **A module document for the browser half's harder parts.** The reader's
   asset blocking and the composer's draft recovery are each argued in their
   own file's comments and nowhere else; the list above points at them rather
   than restating them, which is the right trade until one of them is wrong.
2. **`mail.extract`** — `docs/DOCUMENT-MAIL.md` §6 B2. The `ap@` case done
   properly: a PDF read into a draft Purchase Invoice with every field showing
   where it came from. The highest-value thing in that document and the one
   with the most to get wrong, which is why it is behind the linking work
   rather than in front of it.
3. **Filing on arrival.** `filing.py` runs when somebody presses a button, and
   §6 of that document explains the three reasons. A queue somebody can
   inspect and stop would change the answer.
4. **Soft-bounce backoff.** A full mailbox is not a dead address, and nothing
   currently slows down for one.
5. **Search beyond the operators.** `from:`, `to:`, `subject:`, `has:` and
   `is:` are ported; there is no full-text index behind them, so body search is
   a `LIKE` and says so in its own comment.
