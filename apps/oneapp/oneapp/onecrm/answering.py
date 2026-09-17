"""How long a record waited, measured in working time — and whether it settled.

`docs/ONECRM.md` stage 6. The question a sales desk and a support desk and a
council's planning office all ask is the same one: *did anybody get back to
them, were we in time, and did it get dealt with*. Nothing in ERPNext answers
it. Frappe CRM's `CRM Service Level Agreement` does, and it is the best-built
thing in that app.

This is all of it except one part, and that part is a security decision rather
than a feature.

**What is not taken.** Theirs stores a Python condition on the row and
evaluates it to decide which records are covered. A row an operator can edit
must never be a row an operator can run code from — the same argument
`spaceview/actions.py` makes about why an action is a declaration. So the
narrowing is a **rule list**: fieldname, operator, value, the three-part shape
every filter in this product has, evaluated by comparison and never by an
interpreter. It covers what a condition covered without being a door.

**Five things that are here.**

*Priorities.* A level is a row with its own two clocks, matched on whatever
field the doctype keeps a priority in — a workspace's own word, because a fixed
list of three is what every other product gets wrong here. A record whose
priority is blank falls to the default row rather than quietly not being
measured.

*Two clocks.* A response target and a resolution target, because "did anybody
reply" and "did it get dealt with" are two questions and a desk is judged on
both. Resolution is decided by the record itself, through the same rule shape:
a deal whose stage is Won or Lost, a job whose status is Closed.

*Working time.* Walked forward through the working week a day and a window at a
time, skipping the holiday list — a lead that arrives at six on Friday evening
is not late at nine on Saturday morning, and a measure that says it is gets
switched off within the week.

*Rolling responses*, which is the best idea in their implementation and the one
this module was incomplete without. An agreement is not about the first reply;
it is about every reply. Somebody writing back after being answered starts the
clock again, and the record counts the rounds.

*And the durations*, in working hours, so "how long do we take to answer" has
an answer that is not somebody subtracting two columns by eye.

**What stops a clock.** A sent email, a call out, or somebody writing the date
in by hand. Mail *received* and calls *in* are the thing being waited on — and
under rolling they are what starts the next round. The first answer of each
round is the measurement, and it is never unstamped: an answer given is not
un-given by a later edit.
"""

import frappe
from frappe import _
from frappe.utils import (add_to_date, cint, flt, get_datetime, get_time,
                          getdate, now_datetime, time_diff_in_seconds)

TARGET = "One Response Target"
LEVEL = "One Response Level"
RULE = "One Response Rule"
WEEK = "One Working Day"

#: The fields a measured doctype carries, added by the space manifest.
DUE = "custom_respond_by"
ANSWERED = "custom_answered_on"
STATE = "custom_answering"
SETTLE_BY = "custom_settle_by"
SETTLED = "custom_settled_on"
SETTLING = "custom_settling"
WHICH = "custom_response_target"
AT_LEVEL = "custom_response_level"
TOOK = "custom_answered_in"
SETTLED_IN = "custom_settled_in"
ROUNDS = "custom_rounds"
ROUND_FROM = "custom_round_began"

#: The first-response clock, in the order a record passes through it.
WAITING = "Waiting"
ANSWERED_STATE = "Answered"
LATE = "Late"

#: And the resolution clock. `Open` rather than a second `Waiting`, because the
#: two columns sit beside each other and two identical words would make a
#: person read twice to see which was which.
OPEN = "Open"
SETTLED_STATE = "Settled"
OVERDUE = "Overdue"

#: The days, in the order Python counts them, so `weekday()` is the index.
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
        "Sunday")

#: How far the walk will go looking for working time before it gives up.
#:
#: A target whose week is every day off would otherwise loop forever. Two years
#: is past any honest holiday list and short enough to fail rather than hang.
FURTHEST = 730


# --------------------------------------------------------------------------- #
# Rules — what a condition expression is, without the interpreter
# --------------------------------------------------------------------------- #

def matches(doc, rules) -> bool:
	"""Whether every rule holds against this record.

	AND and not OR, deliberately: a target that fires when *any* of three
	things is true is a target nobody can predict from reading it, and two
	targets ordered by `position` say the same thing readably.

	A rule naming a field the doctype has not got is **false** rather than
	skipped — which is the opposite of the choice `target_for` used to make and
	the right way round here. A rule is somebody narrowing; a narrowing that
	silently stops narrowing is how a target meant for web leads starts
	covering everything.
	"""
	for rule in rules or []:
		if not _holds(doc, rule):
			return False
	return True


def _holds(doc, rule) -> bool:
	"""One rule, evaluated by comparison. Never by `eval`."""
	field = str((rule.get("fieldname") or "")).strip()
	if not field:
		return False
	operator = str(rule.get("operator") or "is").strip().lower()
	held = doc.get(field)
	wanted = rule.get("value")

	if operator == "is set":
		return held not in (None, "", 0)
	if operator == "is not set":
		return held in (None, "", 0)
	if operator == "contains":
		return str(wanted or "").lower() in str(held or "").lower()

	numbers = _as_numbers(held, wanted)
	if operator == "is":
		return numbers[0] == numbers[1] if numbers else _same(held, wanted)
	if operator == "is not":
		return numbers[0] != numbers[1] if numbers else not _same(held, wanted)
	if not numbers:
		# An ordering against something that is not a number is still worth
		# answering — a date, a series — and text order is what Frappe's own
		# query would apply to those columns.
		numbers = (str(held or ""), str(wanted or ""))
	if operator == ">":
		return numbers[0] > numbers[1]
	if operator == "<":
		return numbers[0] < numbers[1]
	if operator == ">=":
		return numbers[0] >= numbers[1]
	if operator == "<=":
		return numbers[0] <= numbers[1]
	return False


def _as_numbers(held, wanted):
	"""Both sides as floats, or nothing if either is not a number."""
	try:
		return float(held), float(wanted)
	except (TypeError, ValueError):
		return None


def _same(held, wanted) -> bool:
	"""Text equality, which is what a Data, a Select and a Link all are."""
	return str(held if held is not None else "") == str(
		wanted if wanted is not None else "")


# --------------------------------------------------------------------------- #
# Which target covers a record, and at what level
# --------------------------------------------------------------------------- #

def target_for(doc) -> dict | None:
	"""The narrowest enabled target that fits this record, or none.

	Ordered by `position` and then by name, so two targets that both fit
	resolve the same way every time rather than by insertion order.
	"""
	if not frappe.db.table_exists(TARGET):
		return None

	rows = frappe.get_all(
		TARGET,
		filters={"enabled": 1, "applies_to": doc.doctype},
		fields=["name", "priority_field", "holiday_list", "rolling"],
		order_by="position asc, name asc",
	)
	for row in rows:
		if matches(doc, _rules(row["name"], "applies_when")):
			return dict(row)
	return None


def level_for(doc, target: dict) -> dict | None:
	"""Which promise applies to this record.

	Read off the field the target names, falling back to the row marked
	default. A priority nobody made a row for is *not* a record that goes
	unmeasured: the default catches it, and a desk that wanted otherwise
	deletes the default row.
	"""
	rows = frappe.get_all(
		LEVEL,
		filters={"parent": target["name"], "parenttype": TARGET},
		fields=["level", "is_default", "respond_within", "resolve_within"],
		order_by="position asc, idx asc",
	)
	if not rows:
		return None

	field = (target.get("priority_field") or "").strip()
	said = str(doc.get(field) or "").strip() if field else ""
	if said:
		found = next((one for one in rows
		              if str(one.get("level") or "").strip() == said), None)
		if found:
			return dict(found)
	found = next((one for one in rows if one.get("is_default")), None)
	return dict(found or rows[0])


def _rules(target: str, fieldname: str) -> list[dict]:
	"""One of a target's two rule lists."""
	return frappe.get_all(
		RULE,
		filters={"parent": target, "parenttype": TARGET,
		         "parentfield": fieldname},
		fields=["fieldname", "operator", "value"],
		order_by="idx asc",
	)


# --------------------------------------------------------------------------- #
# Putting the clocks on a record
# --------------------------------------------------------------------------- #

def apply(doc, method=None) -> None:
	"""Put the deadlines on a record, and say where both of them stand.

	On validate, so a record that has just been given the field value a target
	narrows by picks the target up on that save rather than on the next one.

	Each deadline is written **once per round**. A lead re-saved on Thursday
	does not get until Monday to be answered — that would be a measure that
	resets itself every time somebody looks at it, which is the failure mode
	every SLA implementation has had at least once. What *does* start a new
	round is the other side writing back, and that goes through `reopened`.
	"""
	meta = frappe.get_meta(doc.doctype)
	if not meta.has_field(DUE):
		return

	target = None
	if not doc.get(DUE):
		target = target_for(doc)
		if not target:
			return
		level = level_for(doc, target)
		if not level:
			return
		began = _began(doc)
		doc.set(WHICH, target["name"])
		doc.set(AT_LEVEL, level.get("level") or "")
		doc.set(DUE, deadline(began, target, flt(level.get("respond_within"))))
		if flt(level.get("resolve_within")) > 0 and not doc.get(SETTLE_BY):
			doc.set(SETTLE_BY,
			        deadline(began, target, flt(level["resolve_within"])))
		if not doc.get(ROUNDS):
			doc.set(ROUNDS, 1)
		# When *this* round started. The record's creation on the first one and
		# the moment somebody wrote back on every one after it — stored rather
		# than derived, because the alternative is reading it back out of a
		# deadline by inverting the walk that made it, and an inverse that
		# rounds differently is a duration that disagrees with its own column.
		if not doc.get(ROUND_FROM):
			doc.set(ROUND_FROM, began)

	_settle_if_the_record_says_so(doc, target)
	doc.set(STATE, _standing(doc))
	doc.set(SETTLING, _settling(doc))


def _settle_if_the_record_says_so(doc, target: dict | None) -> None:
	"""Stop the resolution clock when the record has reached its own end.

	The rules are the target's, evaluated against the document being saved —
	so a deal stops the clock at the moment somebody drags it into Won, on the
	same save, rather than an hour later when a sweep notices.
	"""
	if doc.get(SETTLED) or not doc.get(SETTLE_BY):
		return
	name = doc.get(WHICH) or (target or {}).get("name")
	if not name:
		return
	rules = _rules(name, "resolved_when")
	if not rules or not matches(doc, rules):
		return
	at = now_datetime()
	doc.set(SETTLED, at)
	# From the record's own beginning and not from this round's: a response is
	# measured per round because each one is a promise, and a resolution is
	# measured once because there is one of it.
	doc.set(SETTLED_IN, _worked(doc, _began(doc), at))


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


def _settling(doc) -> str:
	"""And the other clock. Empty where the target promised nothing about it."""
	if not doc.get(SETTLE_BY):
		return ""
	if doc.get(SETTLED):
		return SETTLED_STATE
	return OVERDUE if get_datetime(doc.get(SETTLE_BY)) < now_datetime() else OPEN


def _worked(doc, start, end) -> float:
	"""How long between two moments, counting only working time.

	The inverse of `deadline`, and it has to exist for the same reason that
	does: a first response that took "three days" over a weekend took one
	working day, and a desk measured in wall clock is a desk that looks worse
	in December than in June.
	"""
	name = doc.get(WHICH)
	if not name:
		return 0.0
	target = frappe.db.get_value(TARGET, name, ["name", "holiday_list"],
	                             as_dict=True)
	return worked_hours(start, end, dict(target)) if target else 0.0


# --------------------------------------------------------------------------- #
# The working week
# --------------------------------------------------------------------------- #

def deadline(start, target: dict, hours: float):
	"""When something is due, counting only working time.

	Walked a day at a time rather than computed, because the arithmetic that
	looks closed-form stops being so the moment a holiday list is involved —
	and a day at a time over a four-hour target is at most a handful of
	iterations.

	An empty week means every day, all day, which is the honest reading of a
	desk that has not said otherwise and is what a support line running at
	night actually wants.
	"""
	left = flt(hours) * 3600.0
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


def worked_hours(start, end, target: dict) -> float:
	"""How much working time lies between two moments.

	Same walk as `deadline` and the same week, which is the point: a duration
	measured by a different rule from the deadline it is compared against is a
	report that disagrees with the column beside it.
	"""
	at = get_datetime(start)
	end = get_datetime(end)
	if not at or not end or end <= at:
		return 0.0

	week = _week(target["name"])
	holidays = _holidays(target.get("holiday_list"))
	seconds = 0.0

	for _day in range(FURTHEST):
		day = getdate(at)
		window = _window(week, day, holidays)
		if window:
			opens, shuts = window
			opens = _on(day, opens)
			shuts = (_on(add_to_date(day, days=1), get_time("00:00:00"))
			         if shuts is None else _on(day, shuts))
			opened = max(at, opens)
			closed = min(end, shuts)
			if closed > opened:
				seconds += time_diff_in_seconds(closed, opened)
		at = _on(add_to_date(day, days=1), get_time("00:00:00"))
		if at >= end:
			break
	return round(seconds / 3600.0, 2)


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
# What stops a clock, and what starts the next one
# --------------------------------------------------------------------------- #

def answered(doctype: str, name: str, when=None) -> bool:
	"""Stamp the answer on a record that is waiting for one.

	Written straight to the columns rather than through a save: this runs from
	the insert of something else — a sent message, a logged call — and taking a
	document through its own validate from inside another document's insert is
	how a mail send starts failing for a reason nobody can find.

	Never overwritten within a round. The first answer is the measurement, and
	a second email is not a second chance to have been on time; a *new* round
	is what `reopened` opens.
	"""
	if not doctype or not name:
		return False
	meta = frappe.get_meta(doctype)
	if not meta.has_field(ANSWERED) or not meta.has_field(DUE):
		return False

	row = frappe.db.get_value(
		doctype, name, [DUE, ANSWERED, WHICH, ROUND_FROM, "creation"],
		as_dict=True)
	if not row or not row.get(DUE) or row.get(ANSWERED):
		return False

	at = get_datetime(when or now_datetime())
	written = {ANSWERED: at, STATE: ANSWERED_STATE}
	# How long it took, in working hours — measured from the moment this round
	# started, which is the deadline's own start and not the record's creation
	# once somebody has written back. `_round_began` works it out.
	target = frappe.db.get_value(TARGET, row.get(WHICH),
	                             ["name", "holiday_list"], as_dict=True)
	if target:
		written[TOOK] = worked_hours(_round_began(row), at, dict(target))
	frappe.db.set_value(doctype, name, written, update_modified=False)
	return True


def _round_began(row: dict):
	"""When the clock this answer stops was started.

	`custom_round_began` where there is one — the record's creation on the
	first round, the moment the other side wrote back on every one after it —
	and the creation where a record predates the field.
	"""
	return get_datetime(row.get(ROUND_FROM) or row.get("creation")
	                    or now_datetime())


def reopened(doctype: str, name: str, when=None) -> bool:
	"""The other side wrote back: start the clock again.

	**Rolling responses**, and the best idea in Frappe CRM's agreement. An
	agreement is not about the first reply, it is about every reply — a desk
	that answers within the hour and then goes quiet for a fortnight has met a
	first-response target and failed the customer.

	Only where the target asked for it, only on a record that has already been
	answered, and only where it is not settled: a second question before
	anybody replied is the same round, and a closed one is closed.
	"""
	if not doctype or not name:
		return False
	meta = frappe.get_meta(doctype)
	if not meta.has_field(ANSWERED) or not meta.has_field(DUE):
		return False

	row = frappe.db.get_value(
		doctype, name, [DUE, ANSWERED, SETTLED, WHICH, AT_LEVEL, ROUNDS],
		as_dict=True)
	if not row or not row.get(ANSWERED) or row.get(SETTLED):
		return False

	target = frappe.db.get_value(TARGET, row.get(WHICH),
	                             ["name", "holiday_list", "rolling"],
	                             as_dict=True)
	if not target or not target.get("rolling"):
		return False

	level = _level_named(target["name"], row.get(AT_LEVEL))
	if not level:
		return False

	at = get_datetime(when or now_datetime())
	frappe.db.set_value(doctype, name, {
		DUE: deadline(at, dict(target), flt(level.get("respond_within"))),
		ANSWERED: None,
		STATE: WAITING,
		ROUND_FROM: at,
		ROUNDS: cint(row.get(ROUNDS) or 1) + 1,
	}, update_modified=False)
	return True


def _level_named(target: str, level: str) -> dict | None:
	"""The level a record was measured at, for the round after the first."""
	rows = frappe.get_all(
		LEVEL,
		filters={"parent": target, "parenttype": TARGET},
		fields=["level", "is_default", "respond_within", "resolve_within"],
		order_by="position asc, idx asc",
	)
	if not rows:
		return None
	said = str(level or "").strip()
	found = next((one for one in rows
	              if str(one.get("level") or "").strip() == said), None)
	if found:
		return dict(found)
	return dict(next((one for one in rows if one.get("is_default")), rows[0]))


def on_communication(doc, method=None) -> None:
	"""A message we sent is an answer; one we received starts the next round.

	Through `timeline_links`, which `onemail/linking.py` has already written by
	the time this runs: the same rows the record's Mail tab reads, so "what
	this message was about" has one answer on this product.
	"""
	way = (doc.get("sent_or_received") or "")
	if way not in ("Sent", "Received"):
		return
	act = answered if way == "Sent" else reopened
	for link in doc.get("timeline_links") or []:
		try:
			act(link.get("link_doctype"), link.get("link_name"),
			    doc.get("communication_date"))
		except Exception:
			# A record whose doctype has no such field, a link to something
			# deleted. Never worth failing a send over.
			frappe.clear_last_message()


def on_call(doc, method=None) -> None:
	"""And so is ringing them — stage 5's doctype, earning its keep twice.

	Out is an answer; in is somebody chasing us, which under a rolling target
	is exactly what starts the next round.
	"""
	act = answered if (doc.get("way") or "") == "Outgoing" else reopened
	try:
		act(doc.get("about_doctype"), doc.get("about_name"), doc.get("at"))
	except Exception:
		frappe.clear_last_message()


# --------------------------------------------------------------------------- #
# And the ones that go late while nobody is looking
# --------------------------------------------------------------------------- #

#: How many records one sweep will move, per clock. A desk with more than this
#: waiting is a desk with a problem the next run will keep working on.
SWEEP = 500


def late_now() -> int:
	"""Move past-due records from waiting to late, on both clocks.

	The one thing a written state cannot do on its own: nothing saves a record
	at the moment its deadline passes, so without this a lead nobody touched
	stays `Waiting` for ever and the list that is supposed to show the problem
	shows nothing.

	`db.set_value` and not a save, deliberately: this is the clock moving
	rather than anybody changing the record, and a Version row per lead per
	hour would bury the timeline the rest of this arc built.
	"""
	moved = 0
	for doctype in _measured():
		moved += _sweep(doctype, STATE, DUE, WAITING, LATE)
		moved += _sweep(doctype, SETTLING, SETTLE_BY, OPEN, OVERDUE)
	if moved:
		frappe.db.commit()
	return moved


def _sweep(doctype: str, state: str, due: str, was: str, now: str) -> int:
	"""One clock, on one doctype."""
	try:
		rows = frappe.get_all(
			doctype,
			filters={state: was, due: ["<", now_datetime()]},
			pluck="name",
			limit_page_length=SWEEP,
		)
	except Exception:
		# A doctype a target names that has not got the fields — a target typed
		# against the wrong doctype, a space half-installed. One clock missing
		# is not a reason to skip the other.
		frappe.clear_last_message()
		return 0
	for name in rows:
		frappe.db.set_value(doctype, name, state, now, update_modified=False)
	return len(rows)


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
	for at, spec in enumerate(targets):
		if frappe.db.exists(TARGET, spec["name"]):
			continue
		frappe.get_doc({
			"doctype": TARGET,
			"target_name": spec["name"],
			"applies_to": spec["applies_to"],
			# The order they are declared in *is* the order they are tried in.
			# Left at zero they would all tie and fall back to the name, which
			# sorted "Answer a lead" above "Answer a web lead" — so the
			# catch-all matched first and the narrow one never ran.
			"position": at,
			"enabled": 1,
			"rolling": 1 if spec.get("rolling", True) else 0,
			"priority_field": spec.get("priority_field") or "",
			"week": [{"day": day, "works": 1, "from_time": opens,
			          "to_time": shuts} for day, opens, shuts in spec["week"]],
			"levels": [{"level": one[0], "is_default": 1 if one[1] else 0,
			            "respond_within": one[2], "resolve_within": one[3],
			            "position": at}
			           for at, one in enumerate(spec["levels"])],
			"applies_when": [{"fieldname": one[0], "operator": one[1],
			                  "value": one[2]}
			                 for one in spec.get("applies_when") or []],
			"resolved_when": [{"fieldname": one[0], "operator": one[1],
			                   "value": one[2]}
			                  for one in spec.get("resolved_when") or []],
		}).insert(ignore_permissions=True)
		written += 1
	return written
