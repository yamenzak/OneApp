"""What one person has starred, which a shared address cannot store.

Read state used to live here too, and does not any more: it is `\\Seen` on the
mailbox and `Communication.seen` here, kept the same in both directions. The
argument for per-person unread was a shared address — two people on `sales@`
have read different things — and it lost to the simpler fact that every other
client those people use is showing them the mailbox's own flag. A product
whose idea of unread disagrees with Outlook is the surprise; one that agrees
with it is not. See `folders.seen` and `folders.reconcile`.

A star is different and stays per person. There is no IMAP flag it has to
agree with — `\\Flagged` is set as well, but nothing else the customer uses
draws a star from it the way a mail client draws bold from `\\Seen` — and two
people on one address genuinely do flag different things for themselves.
Kept as a user setting rather than a doctype: it is a list of ids nobody
queries across users, and a doctype would be a table with a row per person per
message for a question only that person ever asks.
"""

import frappe


STARRED_KEY = "oneapp_mail_starred"


# Two thousand ids is roughly 36 KB, and it is loaded with the person's other
# user defaults on every request they make. That is the whole reason there is a
# number here: the list is a session cost, not a table, so it has to stay the
# size of something you would happily put in a cookie.
STAR_LIMIT = 2000


def _starred_set() -> set:
	return _starred_of(frappe.session.user)


def _starred_of(person: str) -> set:
	"""What one *named* person has starred.

	Split out from `_starred_set` for the one caller that is not a request: a
	filing rule stars during inbound delivery, where there is no session user
	to read — it stars for whoever holds the address. See `rules.apply_to`.

	`frappe.defaults`, not `frappe.db.get_default`. The latter reads the
	*global* defaults, which every session on the site loads in full — one
	person's stars would be paid for by everybody. Under the user it is loaded
	with that user's own defaults and nobody else's.
	"""
	raw = frappe.defaults.get_user_default(STARRED_KEY, person) or ""
	return set(filter(None, raw.split(",")))
