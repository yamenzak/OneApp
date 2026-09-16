"""A stretch of somebody's time, started and stopped — on ERPNext's Timesheet.

`docs/WORK.md` §12. There is no second time store and there never wanted to
be one: a `Timesheet Detail` is a person, a task, a from and a to, which is
exactly what a clock produces, and it is the row a Sales Invoice reads. So the
clock writes one directly and the ledger needs no bridge.

Three decisions, and the first is the one everything else follows from.

**A running stretch is a row with no `to_time` on it.** Not a flag, not a
cache, not a key in Redis: the thing that is running *is* the timesheet row,
so a browser that closed, a session that expired and a server that restarted
all leave the same truth on disk. ERPNext is already happy with it — `hours`
is zero, so `set_to_time` leaves the blank alone and `calculate_hours` skips
the row — and the only thing that refuses an unfinished row is submitting the
sheet, which is exactly when somebody should be made to look at it.

**One at a time, per person.** Two running clocks is an afternoon that has to
be unpicked by hand, and nobody ever means it: starting a second one stops the
first, and says which.

**The sheet is a day, and submitting it is the person saying it is right.**
Stretches land on today's draft Timesheet and stay there; ERPNext rolls
`actual_time` and the costing onto the task from *submitted* sheets only,
which is not a gap to work around — it is a timesheet being a thing somebody
signs off. Until then the hours are readable here, where the clock is.
"""

import frappe
from frappe import _
from frappe.utils import (get_datetime, now_datetime, time_diff_in_hours,
                          time_diff_in_seconds, today)

#: Theirs.
SHEET = "Timesheet"
ROW = "Timesheet Detail"
TASK = "Task"

#: How long a clock may run before it is obviously somebody's forgotten tab.
#:
#: Not enforced — a night shift is real and a fixture that refuses one is worse
#: than a number somebody has to correct — but reported, so a person opening
#: their week sees it flagged rather than discovering a fourteen-hour Tuesday
#: on an invoice.
LONG = 12 * 60


@frappe.whitelist(methods=["GET"])
def running() -> dict:
	"""What this person is timing, if anything.

	Two small queries rather than a join: the rows with no end on them are the
	clocks running *anywhere on the site*, which is one per person who has one
	going, and narrowing that handful to this person's sheets is the second.
	A join would be one query and a raw one, for a set this size.

	`parenttype` rather than a `parent` argument, because a `Timesheet Detail`
	is a child table and this is asking about every parent at once — which is
	the one shape `frappe.get_all` will answer for a child doctype.
	"""
	open_rows = frappe.get_all(
		ROW,
		filters={"to_time": ["is", "not set"], "docstatus": 0,
		         "parenttype": SHEET},
		fields=["name", "parent", "task", "project", "from_time", "description"],
		order_by="from_time desc",
	)
	if not open_rows:
		return {}

	mine = set(frappe.get_all(
		SHEET,
		filters={"name": ["in", [one.parent for one in open_rows]],
		         "user": frappe.session.user, "docstatus": 0},
		pluck="name",
	))
	found = next((one for one in open_rows if one.parent in mine), None)
	if not found:
		return {}

	entry = dict(found)
	entry["sheet"] = entry.pop("parent")
	entry["starts_at"] = entry.pop("from_time")
	entry["note"] = entry.pop("description") or ""
	entry["subject"] = frappe.db.get_value(TASK, entry["task"], "subject") or ""
	entry["minutes"] = _so_far(entry["starts_at"])
	return entry


@frappe.whitelist(methods=["POST"])
def start(task: str, note: str = "") -> dict:
	"""Begin timing a task, stopping whatever was running.

	The stop is not a courtesy: a person who starts timing something else has
	stopped doing the first thing, and two clocks would have to be unpicked by
	hand afterwards. What was stopped comes back in the answer so the surface
	can say so rather than leaving it to be noticed on Friday.
	"""
	if not task or not frappe.db.exists(TASK, task):
		frappe.throw(_("There is no task at {0}.").format(task or "—"))
	frappe.has_permission(TASK, "read", doc=task, throw=True)

	stopped = stop()
	project = frappe.db.get_value(TASK, task, "project") or None
	sheet = _sheet()
	sheet.append("time_logs", {
		"task": task,
		"project": project,
		"from_time": now_datetime(),
		"description": note or "",
		# Work on somebody's project is chargeable until a person says it is
		# not, which is the way round that loses the least: an unticked hour
		# is an hour that quietly never reached an invoice, and a ticked one
		# somebody has to untick is a line they are looking at anyway.
		"is_billable": 1 if project and frappe.db.get_value(
			"Project", project, "customer") else 0,
	})
	sheet.save()
	return {"entry": sheet.time_logs[-1].name, "sheet": sheet.name, "task": task,
	        "stopped": stopped.get("entry", "")}


@frappe.whitelist(methods=["POST"])
def stop(note: str = "") -> dict:
	"""End whatever this person has running, if anything.

	Idempotent on purpose: a second press, a stale tab and a reload all mean
	"make sure nothing is running", and answering an empty dict is the truthful
	way to say it already was not.
	"""
	held = running()
	if not held:
		return {}

	sheet = frappe.get_doc(SHEET, held["sheet"])
	for row in sheet.time_logs:
		if row.name != held["name"]:
			continue
		row.to_time = now_datetime()
		row.hours = time_diff_in_hours(row.to_time, row.from_time)
		if note:
			row.description = note
		break
	sheet.save()
	return {"entry": held["name"], "sheet": sheet.name, "task": held["task"],
	        "minutes": _so_far(held["starts_at"])}


def _sheet():
	"""Today's draft sheet for this person, or a new one.

	Keyed on `start_date` rather than a mark of ours, because ERPNext already
	writes it from the rows — a sheet whose earliest stretch is today *is*
	today's sheet, and a second field saying so is a second field that can
	disagree. A sheet is never saved empty: `time_logs` is a required table, so
	the caller appends its row before this one is written.
	"""
	found = frappe.get_all(
		SHEET,
		filters={"user": frappe.session.user, "docstatus": 0, "start_date": today()},
		pluck="name",
		order_by="creation desc",
		limit_page_length=1,
	)
	if found:
		return frappe.get_doc(SHEET, found[0])

	return frappe.get_doc({
		"doctype": SHEET,
		"user": frappe.session.user,
		# Where the person is one. It is what makes the hours costable and
		# payable, and a workspace whose users are not employees — an agency
		# logging a contractor's time — is left with the sheet it can still
		# submit, because ERPNext only asks for an activity type when there
		# is an employee to price it against.
		"employee": frappe.db.get_value(
			"Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"),
	})


def _so_far(started) -> int:
	"""How long a running entry has been running, in whole minutes."""
	if not started:
		return 0
	return max(0, int(time_diff_in_seconds(now_datetime(), get_datetime(started)) // 60))


def spent(minutes_of: str) -> int:
	"""How long a task has taken so far, in minutes, drafts included.

	Not `Task.actual_time`, which is ERPNext's and counts *submitted* sheets
	only. Both numbers are right and they answer different questions: theirs is
	what has been signed off, and this is what the clock has recorded — which
	is the one a person wants while they are still working.
	"""
	if not minutes_of:
		return 0
	found = frappe.get_all(
		ROW,
		filters={"task": minutes_of, "docstatus": ["<", 2],
		         "parenttype": SHEET},
		fields=[{"SUM": "hours", "as": "total"}],
	)
	return int(round(float((found[0].get("total") if found else 0) or 0) * 60))


def actions() -> dict:
	"""The two verbs, on the screens where somebody is working.

	A record action rather than a control of its own, which is the point of
	`spaceview/actions.py`: a verb declared this way is offered on the open
	record *and* in the selection bar, and it is one line rather than a
	component. Starting is `one` — two tasks at once is the thing the clock
	refuses — and stopping takes whatever is running, so it does not care which
	row is ticked and asks for none.
	"""
	from frappe import _ as translate

	verbs = [
		{
			"key": "start-timing",
			"label": translate("Start timing"),
			"icon": "lucide-clock",
			"scope": "one",
			"method": "oneapp.onetask.timing.start",
		},
		{
			"key": "stop-timing",
			"label": translate("Stop timing"),
			"icon": "lucide-circle-check",
			"scope": "one",
			"method": "oneapp.onetask.timing.stop_for",
		},
	]
	return {"oneproject/tasks": verbs, "oneproject/my-tasks": verbs,
	        "oneproject/inbox": verbs}


@frappe.whitelist(methods=["POST"])
def stop_for(name: str = "") -> dict:
	"""Stop the clock, from a button that is holding a record.

	The runner hands every action the record it was pressed on, and `stop`
	takes a note in that position — so a bare `stop` wired to a button would
	have filed the task's id as the note on every stretch anybody ever timed.
	One function that ignores what it is given, rather than a signature that
	lies about what it means.
	"""
	return stop()
