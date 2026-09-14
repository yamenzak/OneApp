"""Checking yourself in and out. The only thing in OneHR that writes.

Every other module here reads, and the README says so as a rule rather than an
accident: auto-attendance is HRMS's job and it runs on a schedule, so a page that
marked somebody present because it happened to be open would be a second writer
on the same rows with no lock between them. That rule still holds. This is not
an exception to it — it is the one act it was never about.

`docs/HORILLA.md` §3.4: the competitor carries a check-in control in the navbar
on every page, and it is the single cheapest thing in that document. Checking in
is the one HR act that happens twice a day for every employee, and making it a
destination — rail, Time, Check-ins, New — puts four decisions in front of a
thing that should be one. The README's refusal was about checking *somebody else*
in from *their* record: that needs a device policy, a geofence and a duplicate
rule, and it is still not built. Filing your own is a different act with none of
those questions in it.

**What makes it safe is that it takes no employee.** There is no argument to
point at a colleague. The row is written for `own.employee_of()` and for nobody
else, which is the same property `me.home` has and for the same reason.

**Which way it points is read, not asked.** The browser does not send IN or OUT,
because a browser that has been open since this morning would send whichever the
button said when it loaded. `presence.of` already ranks the four doctypes that
answer "where is this person now", so the direction is the opposite of wherever
they are — and a person the reasoning says is on leave or on a holiday is not
offered a direction at all, because a badge-in on approved leave is exactly the
disagreement `presence` exists to rank and writing one would manufacture it.

**Everything else is HRMS's.** The row goes in as an ordinary document, so its
own validation runs — shift resolution, the duplicate window, whatever a
workspace has added. We do not reimplement any of it and we do not skip it: no
`ignore_permissions`, because the seat's `create` grant is the permission and
`own.py` is not a way around one.
"""

import frappe
from frappe import _

from . import own, presence

#: The two directions a log can point, in HRMS's own words.
IN = "IN"
OUT = "OUT"

#: Where somebody has to be for a direction to make sense. On leave or on a
#: holiday there is no honest answer, so the control is not offered and the
#: endpoint refuses — see the module docstring.
DIRECTIONS = {
	"in": OUT,
	"late": OUT,
	"out": IN,
	"absent": IN,
	"unknown": IN,
}


def installed() -> bool:
	return bool(frappe.db.exists("DocType", "Employee Checkin"))


@frappe.whitelist(methods=["GET"])
def next_direction() -> dict:
	"""Which way the control points, and whether it points anywhere.

	Read on its own as well as inside `me.home`, because the button has to be
	right again after somebody presses it and re-fetching the whole page to move
	one word is a page that flickers once a day for everybody.
	"""
	name = own.employee_of()
	if not name or not installed():
		return {"direction": "", "state": "", "why": "no-employee"}

	state = presence.of(name)
	which = _direction(state)
	return {
		"direction": which,
		"state": state.get("state") or "",
		"since": state.get("since") or "",
		"late": bool(state.get("late")),
		"why": "" if which else state.get("state") or "",
	}


def _direction(state: dict) -> str:
	"""The opposite of wherever they are, or nothing.

	`late` is a fact about an `in` rather than a state of its own — `presence`
	is explicit about that — so it is read off the flag rather than looked up,
	which is why this is a function and not a dict lookup at the call site.
	"""
	which = state.get("state") or "unknown"
	if which == "in" and state.get("late"):
		which = "late"
	return DIRECTIONS.get(which, "")


@frappe.whitelist(methods=["POST"])
def file() -> dict:
	"""One check-in, for the person asking, pointing the only way it can.

	Returns the presence *after* the write, so the page that called this has the
	whole of its own answer and does not draw a button that disagrees with the
	line above it for as long as a second request takes.
	"""
	if not installed():
		frappe.throw(_("This workspace does not record check-ins."))

	name = own.employee_of()
	if not name:
		# The same sentence the page says, because this is the same state: a
		# login nobody linked to a record. Not a permission error — nothing was
		# refused, there is simply nobody to file for.
		frappe.throw(_("Your login is not linked to an employee record."))

	before = presence.of(name)
	which = _direction(before)
	if not which:
		frappe.throw(
			_("You are marked {0} today, so there is nothing to check in or out of.")
			.format((before.get("label") or "").lower() or _("away"))
		)

	frappe.get_doc({
		"doctype": "Employee Checkin",
		"employee": name,
		"log_type": which,
		"time": frappe.utils.now_datetime(),
	}).insert()

	return {"direction": which, "presence": presence.of(name)}
