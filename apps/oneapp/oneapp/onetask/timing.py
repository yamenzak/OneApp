"""A stretch of somebody's time, started and stopped.

`docs/WORK.md` stage 6. Three decisions, and the first is the one everything
else follows from.

**A running entry is a row with no end on it.** Not a flag, not a cache, not a
key in Redis: the thing that is running *is* the timesheet row, so a browser
that closed, a session that expired and a server that restarted all leave the
same truth on disk. Which also means there is nothing to reconcile — the
question "what am I timing" is one query with one filter.

**One at a time, per person.** Two running clocks is an afternoon that has to
be unpicked by hand, and nobody ever means it: starting a second one stops the
first, and says which.

**The task keeps the total.** `spent_minutes` is rolled up here the way a
project's counts are rolled up in `one_task.py` — a list of forty tasks showing
how long each took should be one query, not forty sums over a child table.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds

#: How long a clock may run before it is obviously somebody's forgotten tab.
#:
#: Not enforced — a night shift is real and a fixture that refuses one is worse
#: than a number somebody has to correct — but reported, so a person opening
#: their week sees it flagged rather than discovering a fourteen-hour Tuesday
#: on an invoice.
LONG = 12 * 60


@frappe.whitelist(methods=["GET"])
def running() -> dict:
	"""What this person is timing, if anything."""
	found = frappe.get_all(
		"One Time Entry",
		filters={"person": frappe.session.user, "ends_at": ["is", "not set"]},
		fields=["name", "task", "project", "starts_at", "note"],
		order_by="starts_at desc",
		limit_page_length=1,
	)
	if not found:
		return {}
	entry = dict(found[0])
	entry["subject"] = frappe.db.get_value("One Task", entry["task"], "subject") or ""
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
	if not task or not frappe.db.exists("One Task", task):
		frappe.throw(_("There is no task at {0}.").format(task or "—"))
	frappe.has_permission("One Task", "read", doc=task, throw=True)

	stopped = stop()
	entry = frappe.get_doc({
		"doctype": "One Time Entry",
		"task": task,
		"person": frappe.session.user,
		"starts_at": now_datetime(),
		"note": note or "",
	}).insert()
	return {"entry": entry.name, "task": task, "stopped": stopped.get("entry", "")}


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

	entry = frappe.get_doc("One Time Entry", held["name"])
	entry.ends_at = now_datetime()
	if note:
		entry.note = note
	entry.save()
	return {"entry": entry.name, "task": entry.task, "minutes": entry.minutes}


def _so_far(started) -> int:
	"""How long a running entry has been running, in whole minutes."""
	if not started:
		return 0
	return max(0, int(time_diff_in_seconds(now_datetime(), get_datetime(started)) // 60))


def spent(minutes_of: str) -> int:
	"""How long a task has taken, from its entries.

	One sum rather than a walk: a task with two hundred stretches on it is a
	long job, not a reason to fetch two hundred rows.
	"""
	if not minutes_of:
		return 0
	found = frappe.get_all(
		"One Time Entry",
		filters={"task": minutes_of},
		fields=[{"SUM": "minutes", "as": "total"}],
	)
	return int((found[0].get("total") if found else 0) or 0)


def recount(task: str) -> None:
	"""Write that total onto the task."""
	if not task:
		return
	frappe.db.set_value("One Task", task, "spent_minutes", spent(task),
	                    update_modified=False)


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
	return {"onetask/tasks": verbs, "onetask/my-tasks": verbs}


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
