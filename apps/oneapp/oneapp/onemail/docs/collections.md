# Collections

**There is no mail store**, and that decision was made by the framework rather
than by us. Frappe writes a `Communication` when its IMAP sync pulls a message,
when somebody sends one, and when a reply comes back — so mail was already a
document with a timeline, a permission model, an attachment table and a link to
a record. A second store would have been all of that again, worse, beside it.

What this module is, then, is the questions the framework does not answer.

## Owned

| Doctype | What it is |
| --- | --- |
| `Correspondence` | A letter *as a record* — the outward half, for a workspace that files formal correspondence against a project. `naming_series`, `kind`, `letter_date`, `status`, `is_template`, `subject`/`body` and their Arabic twins, `about_doctype`/`about`. |
| `Mail Rule` | One condition, one destination. `title`, `address`, `enabled`, `priority`, `field`, `operator`, `matches`, `into`, `mark_read`, `star`. |

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `Email Account` | Frappe core | An address. Unchanged. |
| `User Email` | Frappe core | A person's access to one — a child table on `User`, so an address has many people and a person has many addresses. A shared mailbox, a decade old, that nobody here had to design. |
| `Communication` | Frappe core | A message, plus four custom fields. |
| `Communication Link` | Frappe core | What the message is about. The provenance column is ours. |
| `Contact` | Frappe core | A correspondent as a person. |
| `File` | OneCloud | Attachments, and a fetched face. |

## The four custom fields on `Communication`

    custom_thread     which conversation this belongs to
    custom_folder     where it has been filed
    custom_link_by    how the link to a record was made — by rule, by hand,
                      or by a model
    seen              per person, not per document

Two of them are worth their own paragraph.

**`custom_thread`.** `Communication` has no thread key. Mail arrives as
messages and is read as conversations, so we gave it one, written on insert by
walking `in_reply_to` up the chain. Where the headers are there it is real
message-id threading; where they were stripped it falls back to the subject
with `Re:` and `Fwd:` taken off. **Both are read on the way out**, because one
thread can hold messages from either side of that upgrade.

**`seen`, per person.** Frappe's `Communication.seen` is per *document*, which
is the wrong shape for a shared address: two people on `sales@` each need their
own idea of what they have read. `Document Follow` is not it either.

So unread is a read receipt of our own — and **deliberately not a doctype**,
because a table with a row per person per message would exist to answer a
question only that person ever asks.

## `Communication Link.custom_link_by`

Provenance, and it is ours. A message linked to a project by a rule, by a
person and by a model are three different levels of confidence, and a UI that
cannot tell them apart is one that cannot offer to undo the third.
