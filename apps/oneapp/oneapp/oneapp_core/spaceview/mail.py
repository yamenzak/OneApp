"""A record's correspondence: the mail about it, and writing more.

The record surface had a timeline of comments and versions and no mail at all,
which meant a person on `PO-2025-0088` could not see the four emails about it
and a person reading those four could not get to it. `email/linking.py` is what
makes the link; this is where a reader sees it.

**A link is not a grant, and this is the file that has to mean it.** A
`Communication` is shared with the holders of the address it arrived on. If this
returned every message linked to the record, then filing a message against a
project would publish it to everybody who can open the project — which is a
disclosure, not a feature. So the query is scoped to what the *reader* may
already see, exactly as the Mail screen scopes it, and the record is a filter on
top rather than a key that unlocks anything.

Sending is the other half and the more important one. A message sent from a
record is linked with no inference at all: we know what it is about because the
person was looking at it. That is what makes a corpus of correctly-linked mail
exist, which is what everything cleverer later has to be measured against.
"""

import frappe
from frappe import _

from .guard import _reachable
from .resolve import _resolve

PAGE = 50


@frappe.whitelist(methods=["GET"])
def correspondence(space_code: str, screen: str, name: str, limit: int = PAGE) -> dict:
	"""The mail about this record that this reader may see."""
	_reachable(space_code, screen, name)

	doctype = screen_doctype(space_code, screen)
	names = _linked(doctype, name)
	if not names:
		return {"messages": [], "can_send": bool(_addresses()), "more": False}

	limit = min(int(limit or PAGE), PAGE)

	# `get_list` and not `get_all`. That one word is this module's docstring:
	# `get_all` ignores permissions, so it would hand every message linked to
	# this record to anybody who can open the record — which is exactly the
	# disclosure a link must not cause. `get_list` applies the reader's own
	# access, including the `DocShare` rows inbound writes per address holder.
	rows = frappe.get_list(
		"Communication",
		filters={"name": ["in", names]},
		fields=[
			"name", "subject", "sender", "sender_full_name", "recipients", "cc",
			"communication_date", "sent_or_received", "has_attachment",
			"content",
		],
		order_by="communication_date desc",
		limit_page_length=limit + 1,
	)

	more = len(rows) > limit
	rows = rows[:limit]

	# The same resolver the Mail screen uses, so a sender is the same person
	# with the same face in both places — and in one query for the page rather
	# than one per message.
	from oneapp.oneapp_core.email import people

	profiles = people.profiles([
		(row.get("sender") or "", row.get("sender_full_name") or "") for row in rows
	])
	provenance = _by(names, doctype, name)
	for row in rows:
		row["person"] = profiles.get((row.get("sender") or "").lower()) or {}
		row["by"] = provenance.get(row["name"], "")

	return {"messages": rows, "can_send": bool(_addresses()), "more": more}


@frappe.whitelist(methods=["POST"])
def write(space_code: str, screen: str, name: str, to: str, subject: str,
          content: str, sender: str = "", cc: str = "", bcc: str = "",
          attachments: str | list = "") -> dict:
	"""Send a message that is about this record.

	The link needs no working out — the person was looking at the record when
	they wrote it — so this is the one path where correspondence is filed
	exactly right by construction.
	"""
	doctype = _reachable(space_code, screen, name)

	from oneapp.oneapp_core.email import linking
	from oneapp.oneapp_core.email.mailbox import send

	sent = send(
		to=to, subject=subject, content=content, sender=sender,
		cc=cc, bcc=bcc, attachments=attachments,
	)
	if not sent.get("name"):
		return sent

	doc = frappe.get_doc("Communication", sent["name"])
	if linking.add(doc, doctype, name, linking.BY_MANUAL):
		doc.save(ignore_permissions=True)

	return {**sent, "about": {"doctype": doctype, "name": name}}


@frappe.whitelist(methods=["POST"])
def attach(space_code: str, screen: str, name: str, message: str) -> dict:
	"""File a message that already exists against this record.

	The way out of every case the automatic filing did not get: a person who can
	see the message and can reach the record says the two belong together. It
	needs both permissions and takes neither from the other.
	"""
	doctype = _reachable(space_code, screen, name)

	doc = frappe.get_doc("Communication", message)
	doc.check_permission("read")

	from oneapp.oneapp_core.email import linking

	if not linking.add(doc, doctype, name, linking.BY_MANUAL):
		return {"ok": True, "already": True}

	doc.save(ignore_permissions=True)
	return {"ok": True, "linked": message}


@frappe.whitelist(methods=["POST"])
def detach(space_code: str, screen: str, name: str, message: str) -> dict:
	"""Unfile a message from this record.

	Every link has to be undoable, and the ones a machine made most of all —
	nobody lets software touch their accounts payable because it is usually
	right, they let it because they can see what it did and take it back.
	"""
	doctype = _reachable(space_code, screen, name)

	doc = frappe.get_doc("Communication", message)
	doc.check_permission("read")

	rows = [
		row for row in (doc.get("timeline_links") or [])
		if not (row.link_doctype == doctype and row.link_name == name)
	]
	if len(rows) == len(doc.get("timeline_links") or []):
		return {"ok": True, "already": True}

	doc.set("timeline_links", rows)
	# The primary reference is the first link, so removing the one it points at
	# has to move it rather than leave it pointing at a link that is gone.
	if doc.reference_doctype == doctype and doc.reference_name == name:
		doc.reference_doctype = rows[0].link_doctype if rows else None
		doc.reference_name = rows[0].link_name if rows else None

	doc.save(ignore_permissions=True)
	return {"ok": True, "unlinked": message}


def screen_doctype(space_code: str, screen: str) -> str:
	return _resolve(space_code, screen).get("doctype") or ""


def _linked(doctype: str, name: str) -> list[str]:
	"""Every message naming this record, by either of the two places a link lives.

	The child table is the storage and the reference pair is the primary one,
	and a message written before this existed has only the pair — so both are
	read and the union is the answer.
	"""
	if not doctype:
		return []

	# A child table has no permission of its own — the parent's apply, and the
	# parent is checked by the query that returns content. This half only ever
	# produces ids.
	rows = set(frappe.get_all(
		"Communication Link",
		filters={"link_doctype": doctype, "link_name": name,
		         "parenttype": "Communication"},
		pluck="parent",
	))
	# The pair, for messages written before the child table was the storage.
	# `get_list`, so this half is the reader's own access from the start rather
	# than relying on the later query to take back what this one gave.
	rows |= {
		row["name"] for row in frappe.get_list(
			"Communication",
			filters={"reference_doctype": doctype, "reference_name": name},
			fields=["name"],
			limit_page_length=0,
		)
	}
	return sorted(rows)


def _by(messages: list[str], doctype: str, name: str) -> dict[str, str]:
	"""How each of these messages came to be about this record.

	One query for the page. A message linked before the provenance field
	existed, or through the reference pair alone, has no row here and is
	reported as an empty string — which the reader draws as nothing rather than
	as a guess about where it came from.
	"""
	from oneapp.oneapp_core.email.linking import LINK_BY

	return {
		row["parent"]: row.get(LINK_BY) or ""
		for row in frappe.get_all(
			"Communication Link",
			filters={"parent": ["in", messages], "link_doctype": doctype,
			         "link_name": name, "parenttype": "Communication"},
			fields=["parent", LINK_BY],
		)
	}


def _addresses() -> list[str]:
	"""Whether this person has anywhere to send from at all."""
	from oneapp.oneapp_core.email.mailbox import _held

	try:
		return _held()
	except Exception:
		return []
