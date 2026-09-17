# Permissions

**OneMail has no roles**, and it is the module with the most permission
machinery in it — because it is the one surface that talks to people *outside*
the workspace. More of this module is about refusing to do something than about
doing it.

## An address is held, and holding it is the permission

`User Email` is a person's access to an `Email Account`. An address has many
people and a person has many addresses, so `sales@` is a shared mailbox and
each person on it has their own idea of what they have read.

`addresses.py` is the whole of who may do what: `grant`, `revoke`,
`set_default`, `claim`, and `set_connect_policy` for whether people may attach
mailboxes of their own at all.

## The filter is on the query, never on the render

`_filters` returns **both halves of its filter together** — the folder *and*
the set of addresses this person holds — because a caller that took one half
would be asking for every `Communication` on the site.

That is a strange-looking API and it is deliberate: **the shape makes the
dangerous call impossible to write by accident**, which a comment saying
"remember to also filter by address" does not.

## A link is not a grant

`spaceview/mail.py`, in one word: `get_list`, not `get_all`.

Filing a message against a project must not publish it to everybody who can
open the project. A record's correspondence is scoped to **what the reader may
already see**, and the record is a filter on top of that — never the other way
round.

## A message body is a stranger's HTML

Rendered in a `sandbox=""` iframe with DOMPurify in front of it, and **remote
assets are not fetched until somebody asks**.

A tracking pixel that loads on open tells a sender when a person read their
message and from where, and a mail client that does that by default is doing it
on the customer's behalf without asking.

## Nothing about a correspondent leaves, with one amendment

`people.py` resolves a sender locally. What it forbids is what nearly every
other product does: a Gravatar URL *in the page*, so that drawing a list of
fifty conversations tells a third party who fifty of the customer's
correspondents are, on every render, from every reader's browser.

`faces.py` is the amendment, **written as one rather than hidden behind a
switch**: one request, made by the *server*, the first time a Contact is saved
without a picture, stored as a `File` and served from here forever after. What
leaves is a hash of one address and sometimes one domain name, once per
contact, ever. It is off unless an operator turns it on.

## Sending

**As a domain, not until DNS says so** — `verify.py`.

**Rate limited** — `outbound.py`, the only part of sending that is ours.

**Suppressed after a bounce or a complaint** — `suppression.py`, and nothing
sends there again until somebody clears it.
