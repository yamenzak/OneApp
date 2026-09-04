"""Turning a folder and a search term into a query over `Communication`."""

import frappe
import re
from oneapp.oneapp_core.email.folders import FOLDER_FIELD, QUIET
from oneapp.oneapp_core.email.threading import THREAD_FIELD
from .scope import SENT, SPLIT, _held, _like


def _filters(folder: str) -> tuple[dict, list | None]:
	"""The pair of filters that scopes a query to what this person may read.

	Returned together, and that is the whole point of the shape. `recipients` on
	Communication is a comma-joined string, so the union of two addresses is a
	LIKE each and therefore an `or_filters` — and a caller that took the `filters`
	half and forgot the other would ask for "every received email", which the
	database would cheerfully answer with the whole site's mail. One function,
	one return value, impossible to use half of.
	"""
	held = _held()
	if not held:
		# Not an empty filter — an impossible one. A person who holds no
		# address sees no mail, and a missing filter here would show them
		# every Communication on the site.
		return {"name": ("=", "")}, None

	base = {"communication_type": "Communication", "communication_medium": "Email"}

	if folder == "sent":
		# Everything this person has sent, from any of their addresses. No
		# longer in the rail — Sent belongs to an address, not to the
		# workspace — but kept, because it is one honest query and a link
		# somebody saved should not stop working.
		return {**base, "sent_or_received": "Sent", "sender": ("in", held)}, None

	address, _, name = folder.partition(SPLIT) if folder else ("", "", "")

	if name:
		# One folder of one mailbox. Scoped by the address *as well as* the
		# folder name, because folder names are not unique across mailboxes —
		# two people on this site can both have an `Applicants`, and a filter on
		# the name alone would hand one of them the other's.
		if address not in held:
			frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)

		if name == SENT:
			# One address's outbox, whether the message was written here or
			# came out of that mailbox's own Sent folder. The sender is what
			# they have in common; the folder is not.
			return {**base, "sent_or_received": "Sent", "sender": address}, None

		# Scoped by the *address*, not by the Email Account behind it.
		#
		# `email_account` is only set on mail that came through an account —
		# Frappe's IMAP sync sets it, and the Worker that delivers our own
		# routed mail does not, because there is no account to name. Scoping on
		# it therefore did the wrong thing in the one case the whole product is
		# built around: a message on `sales@acme.4dl.app` could be filed into a
		# folder and then was in no folder anybody could open. Address it is,
		# which is what identifies a mailbox anyway.
		return (
			{**base, FOLDER_FIELD: name},
			[
				["recipients", "like", f"%{_like(address)}%"],
				# A folder can hold both halves of a correspondence. `sender`
				# catches the sent ones, which is what an Archive is full of.
				["sender", "=", address],
			],
		)

	base["sent_or_received"] = "Received"
	if folder and folder != "all":
		if folder not in held:
			frappe.throw(_("That is not one of your addresses."), frappe.PermissionError)
		base["recipients"] = ("like", f"%{_like(folder)}%")
		return base, None

	if len(held) == 1:
		base["recipients"] = ("like", f"%{_like(held[0])}%")
		return base, None

	return base, [["recipients", "like", f"%{_like(one)}%"] for one in held]


# How many messages a search may consider. The subject-or-body query answers
# names only and the real query then applies this person's own filter to them,
# so this is a cost bound and not a permission one — but it is a bound: a search
# for "the" on a busy site should not build a list of every message ever.
SEARCH_CEILING = 2000


def _matching(text: str) -> list[str]:
	"""The names of messages whose subject *or* body matches.

	Two OR groups cannot go in one `get_all`: the address scope is already an
	`or_filters`, and a second one would replace it rather than be added to it —
	which is the kind of mistake that turns a search into "everybody's mail".
	So the search runs first and answers names, and the real query filters those
	names by who is allowed to see them. Nothing leaks, because nothing but ids
	comes out of here and the gate is downstream.
	"""
	like = f"%{_like(text)}%"
	found = frappe.get_all(
		"Communication",
		filters={"communication_type": "Communication", "communication_medium": "Email"},
		or_filters=[["subject", "like", like], ["content", "like", like]],
		pluck="name",
		order_by="communication_date desc",
		limit_page_length=SEARCH_CEILING,
	)
	# Never empty: an `in` on an empty list matches nothing in some engines and
	# everything in others, and this one stands in front of the whole site.
	return found or [""]


def _in_thread(key: str) -> list[str]:
	"""Names of messages that could belong to one conversation.

	Names only and unscoped, for the same reason `_matching` is: two OR groups
	cannot go in one `get_all`, and the address scope already owns the one this
	query would need. The gate is the caller's, which applies it to these names
	— so nothing but ids comes out of here.
	"""
	like = f"%{_like(key)}%"
	found = frappe.get_all(
		"Communication",
		filters={"communication_type": "Communication", "communication_medium": "Email"},
		or_filters=[[THREAD_FIELD, "=", key], ["subject", "like", like]],
		pluck="name",
		limit_page_length=SEARCH_CEILING,
	)
	return found or [""]


def _preview(html: str) -> str:
	"""The first line, with the markup taken out.

	Deliberately crude — a regex, not a parser. This is one line under a subject
	in a list; a message whose preview is slightly wrong costs nothing, and a
	dependency that turns every list into an HTML parse costs the list.
	"""
	text = re.sub(r"<[^>]+>", " ", html or "")
	text = re.sub(r"\s+", " ", text).strip()
	return text[:160]
