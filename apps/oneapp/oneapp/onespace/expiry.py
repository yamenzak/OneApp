"""The daily walk over documents that expire.

Two things happen every morning. Every document's status is brought up to date,
because a status derived on save goes stale the moment the day changes — a
licence that was Valid last night is Expiring this morning and nobody saved it.
And whoever should know is told, once.

Once is the whole design. A register that emails every morning until somebody
acts is a register people filter into a folder, and then the one that mattered
is in the folder too. So a warning is sent when a document crosses into
Expiring or Expired, `reminded_on` records that it went, and nothing is sent
again until the document changes state.

Who is told: whoever it is assigned to, whoever follows it, and its owner.
Frappe's own assignment and following, so this adds no third idea of "people
who care about this record".
"""

import frappe
from frappe.utils import getdate, nowdate

from oneapp.onespace.doctype.compliance_document.compliance_document import (
	EXPIRED,
	EXPIRING,
	standing,
)

# What one pass will look at. A register is hundreds of rows, not millions, and
# a cap means a site with a runaway import does not spend its morning here.
LIMIT = 5000


def sweep():
	"""From `scheduler_events`, daily."""
	today = nowdate()
	told = 0

	for row in frappe.get_all(
		"Compliance Document",
		fields=["name", "title", "expiry_date", "remind_days", "status",
		        "reminded_on", "owner", "about_doctype", "about"],
		limit_page_length=LIMIT,
	):
		now = standing(row.expiry_date, row.remind_days, today)
		moved = now != row.status

		if moved:
			frappe.db.set_value("Compliance Document", row.name, "status", now,
			                    update_modified=False)

		# Told on the way in, and not again while it sits there. A document
		# that was warned about as Expiring is warned about again when it
		# actually expires, because those are two different pieces of news.
		if now in (EXPIRING, EXPIRED) and moved:
			told += _warn(row, now, today)

	frappe.db.commit()
	return told


def _warn(row, now: str, today: str) -> int:
	"""One notification per person who should know, through the framework's own.

	`notifications.notify` is the framework's producer with the registry in
	front of it: each person's settings applied, the actor skipped, dedupe done
	— and the kind checked, so "Expiring" is a switch somebody can turn off
	rather than a notification that arrives whatever they set.
	"""
	from oneapp.onespace import notifications

	people = set(notifications._followers("Compliance Document", row.name))
	people.update(frappe.parse_json(
		frappe.db.get_value("Compliance Document", row.name, "_assign") or "[]") or [])
	if row.owner:
		people.add(row.owner)
	people.discard("Administrator")
	people.discard("Guest")
	if not people:
		return 0

	days = (getdate(row.expiry_date) - getdate(today)).days
	said = (
		f"{row.title} expired {abs(days)} days ago"
		if now == EXPIRED
		else f"{row.title} expires in {days} days"
	)

	notifications.notify(notifications.EXPIRY_TYPE, people, {
		"document_type": "Compliance Document",
		"document_name": row.name,
		"subject": said,
		"email_content": said,
		"from_user": "Administrator",
	})
	frappe.db.set_value("Compliance Document", row.name, "reminded_on", today,
	                    update_modified=False)
	return len(people)
