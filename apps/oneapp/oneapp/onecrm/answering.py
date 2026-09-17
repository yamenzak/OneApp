"""How long a record waited for an answer, measured in working time.

`docs/ONECRM.md` stage 6. The question a sales desk and a support desk and a
council's planning office all ask is the same one: *did anybody get back to
them, and were we in time*. Nothing in ERPNext answers it. Frappe CRM's
`CRM Service Level Agreement` does, and it is the best-built thing in that app.

This is that idea at a third of the surface. Three decisions.

**A target is a row, not a condition.** Theirs stores a Python expression per
agreement and evaluates it to decide which records are covered. A row an
operator can edit must never be a row an operator can run code from — the same
argument `spaceview/actions.py` makes about why an action is a declaration —
so this narrows by one field and one value. "Web leads", "government deals",
"anything on this doctype": covered. Anything that would need an interpreter:
refused, and the answer is a second target.

**The clock runs in working time.** A lead that arrives at six on Friday
evening is not late at nine on Saturday morning, and a measure that says it is
gets switched off within the week. So the deadline is walked forward through
the working week, skipping the holiday list — which is the hard part and the
whole reason this is a doctype rather than a `+ 4 hours`.

**Anything can be the answer.** A sent email, a logged call — stage 5's, and
this is where that doctype pays for itself twice — or somebody writing the date
in by hand. What stops the clock is the *first* of them, and it is never
unstamped afterwards: an answer given is not un-given by a later edit.

And the state is written rather than derived. `Waiting`, `Answered`, `Late` is
a column a list sorts by and a board groups by, and a value computed per row at
render time is neither. `late_now` is what moves a record from waiting to late
without anybody saving it — see `hooks.scheduler_events`.
"""

import frappe
from frappe import _
from frappe.utils import (add_to_date, get_datetime, get_time, getdate,
                          now_datetime, time_diff_in_seconds)

TARGET = "One Response Target"
WEEK = "One Working Day"

#: The fields a measured doctype carries, added by the space manifest.
DUE = "custom_respond_by"
ANSWERED = "custom_answered_on"
STATE = "custom_answering"
WHICH = "custom_response_target"

#: What the three words mean, and they are in the order a record passes through
#: them. `Late` is not a fourth state for "answered late": a record that was
#: answered says so, and *when* against `custom_respond_by` is the measurement.
WAITING = "Waiting"
ANSWERED_STATE = "Answered"
LATE = "Late"

#: The days, in the order Python counts them, so `weekday()` is the index.
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
        "Sunday")

#: How far the walk will go looking for working time before it gives up.
#:
#: A target whose week is every day off would otherwise loop forever. Two years
#: is past any honest holiday list and short enough to fail rather than hang.
FURTHEST = 730


# --------------------------------------------------------------------------- #
# Which target covers a record
# --------------------------------------------------------------------------- #

def target_for(doc) -> dict | None:
	"""The narrowest enabled target that fits this record, or none.

	Ordered by `position` and then by name, so two targets that both fit
	resolve the same way every time rather than by insertion order. A target
	with a `when_field` the doctype has not got is skipped rather than
	throwing: a row typed wrong should cost the record nothing.
	"""
	if not frappe.db.table_exists(TARGET):
		return None

	rows = frappe.get_all(
		TARGET,
		filters={"enabled": 1, "applies_to": doc.doctype},
		fields=["name", "when_field", "when_value", "hours", "holiday_list"],
		order_by="position asc, name asc",
	)
	meta = frappe.get_meta(doc.doctype)
	for row in rows:
		field = (row.get("when_field") or "").strip()
		if not field:
			return dict(row)
		if not meta.has_field(field):
			continue
		if str(doc.get(field) or "") == str(row.get("when_value") or ""):
			return dict(row)
	return None


def apply(doc, method=None) -> None:
	"""Put a deadline on a record, and say where it stands.

	On validate, so a record that has just been given the field value a target
	narrows by picks the target up on that save rather than on the next one.

	The deadline is written **once**. A lead re-saved on Thursday does not get
	until Monday to be answered — that would be a measure that resets itself
	every time somebody looks at it, which is the failure mode every SLA
	implementation has had at least once.
	"""
	meta = frappe.get_meta(doc.doctype)
	if not meta.has_field(DUE):
		return

	if not doc.get(DUE):
		target = target_for(doc)
		if not target:
			return
		doc.set(WHICH, target["name"])
		doc.set(DUE, deadline(_began(doc), target))

	doc.set(STATE, _standing(doc))


def _began(doc):
	"""When the clock started: the record's own creation, or now.

	`creation` is empty on a document that has not been inserted yet, which is
	the common case here — `apply` runs on validate, and the first validate is
	before the insert.
	"""
	return get_datetime(doc.get("creation")) if doc.get("creation") else now_datetime()


def _standing(doc) -> str:
	"""Waiting, answered or late, from what is on the record."""
	if doc.get(ANSWERED):
		return ANSWERED_STATE
	if not doc.get(DUE):
		return ""
	return LATE if get_datetime(doc.get(DUE)) < now_datetime() else WAITING


# --------------------------------------------------------------------------- #
# The working week
# --------------------------------------------------------------------------- #

def deadline(start, target: dict):
	"""When an answer is due, counting only working time.

	Walked a day at a time rather than computed, because the arithmetic that
	looks closed-form stops being so the moment a holiday list is involved —
	and a day at a time over a four-hour target is at most a handful of
	iterations.

	An empty week means every day, all day, which is the honest reading of a
	desk that has not said otherwise and is what a support line running at
	night actually wants.
	"""
	left = float(target.get("hours") or 0) * 3600.0
	if left <= 0:
		return start

	week = _week(target["name"])
	holidays = _holidays(target.get("holiday_list"))
	at = get_datetime(start)

	for _day in range(FURTHEST):
		day = getdate(at)
		window = _window(week, day, holidays)
		if window:
			opens, shuts = window
			opens = _on(day, opens)
			# `None` is midnight at the far end, and it is not a nicety: a day
			# has no 24:00, so a window written as 09:00–23:59:59 quietly loses
			# a second every day it crosses. A desk with no declared week is
			# open all of it.
			shuts = (_on(add_to_date(day, days=1), get_time("00:00:00"))
			         if shuts is None else _on(day, shuts))
			at = max(at, opens)
			if at < shuts:
				available = time_diff_in_seconds(shuts, at)
				if available >= left:
					return add_to_date(at, seconds=int(left))
				left -= available
		# Tomorrow, at the top of it: the next window decides when work
		# actually resumes.
		at = _on(add_to_date(day, days=1), get_time("00:00:00"))

	# A week with no working time in it at all. Refused loudly rather than
	# answered with a date two years out, which nobody would read as an error.
	frappe.throw(_("{0} has no working time in it, so nothing can be due.")
	             .format(target["name"]))


def _week(target: str) -> dict:
	"""The working windows, by day name. Empty when the target declared none."""
	rows = frappe.get_all(
		WEEK,
		filters={"parent": target, "parenttype": TARGET},
		fields=["day", "works", "from_time", "to_time"],
	)
	return {row["day"]: row for row in rows}


def _holidays(holiday_list: str) -> set:
	"""The days the clock does not run, as dates."""
	if not holiday_list or not frappe.db.exists("Holiday List", holiday_list):
		return set()
	rows = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "parenttype": "Holiday List"},
		fields=["holiday_date"],
	)
	return {getdate(row["holiday_date"]) for row in rows}


def _window(week: dict, day, holidays: set):
	"""This day's working window, or nothing if it is not one."""
	if day in holidays:
		return None
	if not week:
		return get_time("00:00:00"), None
	row = week.get(DAYS[day.weekday()])
	if not row or not row.get("works"):
		return None
	opens = get_time(row.get("from_time") or "00:00:00")
	shuts = get_time(row.get("to_time")) if row.get("to_time") else None
	return (opens, shuts) if shuts is None or shuts > opens else None


def _on(day, at):
	"""A time, on a day, as a datetime."""
	return get_datetime(f"{getdate(day)} {at}")


# --------------------------------------------------------------------------- #
# What stops the clock
# --------------------------------------------------------------------------- #

def answered(doctype: str, name: str, when=None) -> bool:
	"""Stamp the first answer on a record, if it is waiting for one.

	Written straight to the column rather than through a save: this runs from
	the insert of something else — a sent message, a logged call — and taking a
	document through its own validate from inside another document's insert is
	how a mail send starts failing for a reason nobody can find.

	Never overwritten. The *first* answer is the measurement, and a second
	email is not a second chance to have been on time.
	"""
	if not doctype or not name:
		return False
	meta = frappe.get_meta(doctype)
	if not meta.has_field(ANSWERED) or not meta.has_field(DUE):
		return False

	row = frappe.db.get_value(doctype, name, [DUE, ANSWERED], as_dict=True)
	if not row or not row.get(DUE) or row.get(ANSWERED):
		return False

	at = get_datetime(when or now_datetime())
	frappe.db.set_value(doctype, name, {
		ANSWERED: at,
		STATE: ANSWERED_STATE,
	}, update_modified=False)
	return True


def on_communication(doc, method=None) -> None:
	"""A message we sent is an answer to everything it was about.

	Sent only. A message *received* is the thing being waited on, not the
	reply to it — counting it would mean a lead that emails twice has answered
	itself.

	Through `timeline_links`, which `onemail/linking.py` has already written by
	the time this runs: the same rows the record's Mail tab reads, so "what
	this message was about" has one answer on this product.
	"""
	if (doc.get("sent_or_received") or "") != "Sent":
		return
	for link in doc.get("timeline_links") or []:
		try:
			answered(link.get("link_doctype"), link.get("link_name"),
			         doc.get("communication_date"))
		except Exception:
			# A record whose doctype has no such field, a link to something
			# deleted. Never worth failing a send over.
			frappe.clear_last_message()


def on_call(doc, method=None) -> None:
	"""And so is ringing them — stage 5's doctype, earning its keep twice.

	Outgoing only, and for the same reason: an incoming call is somebody
	chasing us, which is the thing being measured rather than the answer to it.
	"""
	if (doc.get("way") or "") != "Outgoing":
		return
	try:
		answered(doc.get("about_doctype"), doc.get("about_name"), doc.get("at"))
	except Exception:
		frappe.clear_last_message()


# --------------------------------------------------------------------------- #
# And the ones that go late while nobody is looking
# --------------------------------------------------------------------------- #

#: How many records one sweep will move. A desk with more than this waiting is
#: a desk with a problem the next run will keep working on.
SWEEP = 500


def late_now() -> int:
	"""Move past-due records from waiting to late.

	The one thing a written state cannot do on its own: nothing saves a record
	at the moment its deadline passes, so without this a lead nobody touched
	stays `Waiting` for ever and the list that is supposed to show the problem
	shows nothing.

	`db.set_value` and not a save, deliberately: this is the clock moving
	rather than anybody changing the record, and a Version row per lead per
	night would bury the timeline the rest of this arc built.
	"""
	moved = 0
	for doctype in _measured():
		try:
			rows = frappe.get_all(
				doctype,
				filters={STATE: WAITING, DUE: ["<", now_datetime()]},
				pluck="name",
				limit_page_length=SWEEP,
			)
		except Exception:
			frappe.clear_last_message()
			continue
		for name in rows:
			frappe.db.set_value(doctype, name, STATE, LATE,
			                    update_modified=False)
			moved += 1
	if moved:
		frappe.db.commit()
	return moved


def _measured() -> list[str]:
	"""The doctypes some enabled target names.

	Read off the targets rather than hard-coded to Lead and Opportunity: the
	whole claim of `applies_to` being a Link to DocType is that a job, a ticket
	or an application is the same row, and a sweep that knew two doctypes would
	have made that claim false.
	"""
	if not frappe.db.table_exists(TARGET):
		return []
	found = frappe.get_all(TARGET, filters={"enabled": 1},
	                       pluck="applies_to", distinct=True)
	return [one for one in dict.fromkeys(found) if one]


def ensure(targets) -> int:
	"""Write a workspace's opening targets, once.

	Idempotent by name and never edited afterwards — `onecrm/stages.py` makes
	the argument: a desk that lengthened its target should not find it back the
	way it shipped after the next migration.
	"""
	written = 0
	for name, applies_to, hours, week in targets:
		if frappe.db.exists(TARGET, name):
			continue
		frappe.get_doc({
			"doctype": TARGET, "target_name": name, "applies_to": applies_to,
			"hours": hours, "enabled": 1,
			"week": [{"day": day, "works": 1, "from_time": opens,
			          "to_time": shuts} for day, opens, shuts in week],
		}).insert(ignore_permissions=True)
		written += 1
	return written
