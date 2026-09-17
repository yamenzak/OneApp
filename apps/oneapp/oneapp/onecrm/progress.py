"""Where a record has been, and how long it sat in each place.

`docs/ONECRM.md` stage 2. A pipeline review is not held to ask what is in
Negotiation; it is held to ask what has been in Negotiation for forty days, and
neither ERPNext nor OneCRM could answer that at all. Frappe CRM's
`CRM Status Change Log` is a child table on both their lead and their deal, and
so is this.

The walk is here rather than on the deal because it is the same walk twice: a
deal moves through `custom_stage` and a lead through ERPNext's own
`qualification_status`, and the only difference is which field is read. Two
copies of this would be two copies to keep in step.

Driven off the child table rather than off the Datetime: the last open row *is*
where the record was, so the log cannot drift from the field even if somebody
writes one of them by hand. The field is the copy, because a child table cannot
be sorted on and "longest stuck first" is a sort. A Datetime rather than a day
count, which would be wrong by one every midnight.
"""

import frappe
from frappe.utils import now_datetime, time_diff_in_hours

#: How many arrivals one record keeps.
#:
#: A deal that has moved two hundred times is a deal somebody is dragging
#: around a board, and the oldest rows are the least interesting: what a review
#: asks is where it is *now* and how long it has been there. Past this the
#: earliest row is dropped, which keeps the record openable.
MOST = 100


def log_the_move(doc, field: str, log: str, since: str) -> None:
	"""Close the row for where it was, and open one for where it is.

	A record with nothing in `field` logs nothing, and one saved without moving
	touches neither — this runs on every save of every such record on the site.
	"""
	where = doc.get(field)
	if not where:
		return
	# The columns are the space manifest's, added when a workspace gains the
	# space rather than when the app is installed — so between `bench migrate`
	# and the first sync they are not there, and appending to a table the
	# doctype has not got is an `AttributeError` on every save of every lead on
	# the site. Nothing logged is the right answer in that window; the next
	# move after the sync opens the first row.
	if not doc.meta.has_field(log):
		return

	rows = doc.get(log) or []
	open_row = rows[-1] if rows and not rows[-1].left_on else None
	if open_row and open_row.stage == where:
		return

	now = now_datetime()
	if open_row:
		open_row.left_on = now
		open_row.days = round(
			time_diff_in_hours(now, open_row.entered_on) / 24.0, 2)

	doc.append(log, {
		"stage": where, "entered_on": now, "moved_by": frappe.session.user,
	})
	if len(doc.get(log)) > MOST:
		doc.set(log, doc.get(log)[-MOST:])
	doc.set(since, now)
