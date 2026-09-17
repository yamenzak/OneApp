# Integrations

## Cloudflare — the platform

**Email Routing receives, a Worker posts here, and Email Workers send.**
`docs/EMAIL.md` is the argument: what Cloudflare gives us, what it does not,
and why Frappe Mail is not the answer. `inbound.receive` is the endpoint the
Worker posts to; `outbound.py` is the rate limit in front of sending, which is
the only part of sending that is ours.

A customer's own domain goes through `verify.py` and is not usable until DNS
says so.

## Frappe — deeply

**`Communication` is the message**, plus four custom fields. **`Email Account`
is an address** and **`User Email` is a person's access to one**, which is a
shared mailbox a decade old that nobody here had to design.

**`Communication Link`** is what a message is about, and it is the seam every
space reaches mail through. The provenance column is ours.

**`Contact`** is a correspondent. `faces.py` hangs a `File` off one.

Frappe's IMAP sync is what `connect.py` uses for a mailbox somebody already
had. Its folders come with it.

## Every space, through one rule

**A link is not a grant.** `spaceview/mail.py` says it in one word — `get_list`,
not `get_all`. Filing a message against a project must not publish it to
everybody who can open the project, so a record's correspondence is scoped to
what the *reader* may already see and the record is a filter on top.

That is the same refusal `_filters` makes inside this module and the same one
`onestorage/linked.py` makes about files.

## ERPNext and HRMS

Through `Communication Link` and nothing else. A quotation's thread is on the
quotation because a link row says so; this module does not know what a
quotation is.

`concerns.py` is the one place that names their doctypes, and it names them as
*kinds of party and person* rather than as ERPNext: `Customer`, `Supplier`,
`Prospect`, `Lead` and `Employee`, resolved from `Contact`, `Contact Email` and
`Dynamic Link`, which are Frappe's. Reads only — it writes nothing on any of
them, and a site without HRMS is asked nothing about an Employee.

This is also how the three spaces *receive* what a message proposes, and there
is no mechanism for it beyond the link row: a thread linked to a Customer shows
up on that customer in OneCRM, one linked to an Employee on that person in
OnePeople, because both already read this table. `docs/CLEANUP.md` §7. `Correspondence` is the outward half for a workspace that files
formal letters against a project — and it is ours precisely because ERPNext has
no noun for one.

## OneCloud (`onestorage`)

Attachments are `File` rows, so a mail attachment is in the Drive like anything
else. A fetched face is a `File` too.

## OneWriter (`onedoc`)

A document has to leave, and mail is how. The export being a self-contained
HTML file rather than a link is that requirement: what lands in a stranger's
inbox should be a document.

## The desk (`onespace`)

Mail is a window as well as a page — `docs/DESKTOP.md`. The two differ only in
where the current place is kept.

## OneLegal

`legal.py` carries Cloudflare as a subprocessor and says what a message passes
through. It is one of the clauses that makes the assembled-from-modules design
worth it: changing mail providers changes the subprocessor list and the
document hash, and somebody has to decide whether that is material.

## OneAI

`ai.md`. Three features declared here, and the one interesting integration in
the product's AI story — `filing.py` ranks candidates rather than choosing.
