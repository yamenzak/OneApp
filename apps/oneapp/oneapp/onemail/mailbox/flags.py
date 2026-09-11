"""What one person has read and starred, which a shared address cannot store.

Per person, because a shared address is read by several and `Communication.seen`
is one flag for the document. Kept as a user setting rather than a doctype: it
is a list of ids nobody queries across users, and a doctype would be a table
with a row per person per message for a question only that person ever asks.
"""

import frappe


SEEN_KEY = "oneapp_mail_seen"


# Two thousand ids is roughly 36 KB, and it is loaded with the person's other
# user defaults on every request they make. That is the whole reason there is a
# number here: the list is a session cost, not a table, so it has to stay the
# size of something you would happily put in a cookie.
SEEN_LIMIT = 2000


def _seen_set() -> set:
	return _seen_of(frappe.session.user)


def _seen_of(person: str) -> set:
	"""What one *named* person has read.

	Split out for the one caller that is not a request, the same way
	`_starred_of` is: mail arriving already read on the server is read for
	everybody holding the address, and there is no session user during a sync.

	`frappe.defaults`, not `frappe.db.get_default`. The latter reads the
	*global* defaults, which every session on the site loads in full — one
	person's read receipts would be paid for by everybody. Under the user it
	is loaded with that user's own defaults and nobody else's.
	"""
	raw = frappe.defaults.get_user_default(SEEN_KEY, person) or ""
	return set(filter(None, raw.split(",")))


STARRED_KEY = "oneapp_mail_starred"


def _starred_set() -> set:
	return _starred_of(frappe.session.user)


def _starred_of(person: str) -> set:
	"""What one *named* person has starred.

	Split out from `_starred_set` for the one caller that is not a request: a
	filing rule stars during inbound delivery, where there is no session user
	to read — it stars for whoever holds the address. See `rules.apply_to`.
	"""
	raw = frappe.defaults.get_user_default(STARRED_KEY, person) or ""
	return set(filter(None, raw.split(",")))


def carry_seen_from_server(doc, method=None):
	"""A message that arrives already read on the server arrives read here.

	The inbound half of read state, and it runs once — at import, when there
	is no per-person state yet to contradict. That is the whole reason it is
	safe to apply to *everybody* who holds the address: `\\Seen` is one flag on
	the mailbox and cannot say which of three people on `sales@` read
	something, but before the message existed here nobody had an opinion for
	it to overwrite.

	Without it, connecting a mailbox of nine years' mail shows nine years of
	unread, which is the first thing somebody sees and the last thing they
	want.

	The later change is deliberately not reconciled: somebody reading a message
	in Outlook on Tuesday does not mark it read here, because by then the
	per-person lists exist and `\\Seen` still cannot say whose. See
	`folders.seen` for the direction that does work both ways.
	"""
	if (doc.communication_medium or "") != "Email" or not doc.get("seen"):
		return
	if (doc.sent_or_received or "") == "Sent":
		# Sent mail is marked seen by `folders.OneSpaceInboundMail`, and a
		# person's own outbox is not a thing they have "read".
		return

	from oneapp.onemail.inbound import _account_for

	account = _account_for(doc)
	if not account:
		return

	for person in frappe.get_all(
		"User Email", filters={"email_account": account}, pluck="parent", distinct=True
	):
		seen = list(_seen_of(person))
		if doc.name in seen:
			continue
		seen.append(doc.name)
		if len(seen) > SEEN_LIMIT:
			seen = seen[-SEEN_LIMIT:]
		frappe.defaults.set_user_default(SEEN_KEY, ",".join(seen), person)
