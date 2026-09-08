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
	# `frappe.defaults`, not `frappe.db.get_default`. The latter reads the
	# *global* defaults, which every session on the site loads in full — one
	# person's read receipts would be paid for by everybody. Under the user it
	# is loaded with that user's own defaults and nobody else's.
	raw = frappe.defaults.get_user_default(SEEN_KEY, frappe.session.user) or ""
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
