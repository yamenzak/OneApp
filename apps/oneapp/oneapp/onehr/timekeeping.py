"""The five verbs that make a day, a shift and a balance say what they mean.

Small ones, and each closes a screen that could be opened and not used:

**Overtime** — `Fetch Overtime Details` reads the attendance in the slip's
period, works out what is over the standard hours, and fills the rows. Without
it the Overtime screen this space added is a form somebody types by hand,
against attendance the database already has.

**Check-ins** — `Fetch Shift` works out which shift a log belongs to from the
time it was made. HRMS does it on insert; the button is for a log whose shift
changed afterwards, which is most of why anybody opens one.

**Shift types** — `Mark Attendance` is the auto-attendance run, by hand. It is
the scheduled job in `hourly_long`, and pressing it is what a people officer
does when somebody's check-ins arrived late.

**Allocations** — expiring one, and adjusting one. The second is the interesting
one: HRMS asks for four fields in a dialog it builds in JavaScript, and this
space already has a screen over the document that dialog creates, so the verb
opens **Adjustments**' own New dialog instead. Its validation, its required-ness
and its permission — which the hand-built one has none of.

Nothing here computes anything. Every verb is HRMS's own method on HRMS's own
document, after the permission the desk asks for.
"""

import frappe
from frappe import _
from frappe.utils import nowdate

from oneapp.onehr.verbs import filled, refuse

ADJUSTMENTS = "adjustments"


def installed() -> bool:
	return bool(frappe.db.exists("DocType", "Overtime Slip"))


def actions() -> dict:
	return {
		"onehr/overtime": [
			{
				"key": "fetch-overtime",
				"label": _("Fetch the hours"),
				"icon": "lucide-clock",
				"scope": "one",
				"method": "oneapp.onehr.timekeeping.fetch_overtime",
			},
		],
		"onehr/checkins": [
			{
				"key": "fetch-shift",
				"label": _("Work out the shift"),
				"icon": "lucide-clock",
				"scope": "many",
				"method": "oneapp.onehr.timekeeping.fetch_shift",
			},
		],
		"onehr/shift-types": [
			{
				"key": "mark-attendance",
				"label": _("Mark the attendance"),
				"icon": "lucide-clock",
				"scope": "one",
				"confirm": _("This reads every check-in against this shift and "
				             "writes the attendance it implies."),
				"method": "oneapp.onehr.timekeeping.mark_attendance",
			},
		],
		"onehr/allocations": [
			{
				"key": "adjust-allocation",
				"label": _("Adjust it"),
				"icon": "lucide-git-compare",
				"scope": "one",
				"method": "oneapp.onehr.timekeeping.adjust",
			},
			{
				"key": "expire-allocation",
				"label": _("Expire it"),
				"icon": "lucide-calendar",
				"scope": "one",
				"confirm": _("This writes off whatever is left on this "
				             "allocation."),
				"method": "oneapp.onehr.timekeeping.expire",
			},
		],
	}


def fetch_overtime(name: str) -> dict:
	"""Read the attendance in this slip's period and fill the rows.

	Two HRMS methods in the order its own form calls them: the period first,
	where the slip does not carry one — it is derived from the person's payroll
	frequency — and then the details. Saved here, because both write the
	document in memory and leave the desk to press Save.
	"""
	if not installed():
		frappe.throw(_("This workspace does not keep overtime."))
	doc = frappe.get_doc("Overtime Slip", name)
	doc.check_permission("write")
	if doc.docstatus != 0:
		refuse(doc, _("A slip is filled in while it is a draft."))

	if not (doc.start_date and doc.end_date):
		doc.get_frequency_and_dates()
	doc.get_emp_and_overtime_details()
	doc.save()
	return {"rows": len(doc.overtime_details or []),
	        "hours": doc.total_overtime_duration}


def fetch_shift(name: str) -> dict:
	"""Which shift a check-in belongs to, from the time it was made.

	`many`, unlike everything else here, and the reason is the shape of the
	mistake it fixes: a shift assignment written after the fact leaves a
	morning's worth of logs pointing at nothing, and correcting them one at a
	time is the work this exists to save.
	"""
	doc = frappe.get_doc("Employee Checkin", name)
	doc.check_permission("write")
	doc.fetch_shift()
	doc.save()
	return {"shift": doc.shift or ""}


def mark_attendance(name: str) -> dict:
	"""The auto-attendance run for one shift, by hand.

	HRMS's own, including the part that matters: it refuses a shift whose
	configuration cannot produce attendance, and above a thousand logs it
	enqueues the work and answers with the job it made.
	"""
	doc = frappe.get_doc("Shift Type", name)
	doc.check_permission("write")
	if not doc.enable_auto_attendance:
		frappe.throw(_("{0} does not mark attendance automatically, so there "
		               "is nothing to run.").format(doc.name))

	job = doc.process_auto_attendance(is_manually_triggered=True)
	return {"ok": True, "queued": bool(job)}


def _allocation(name: str):
	doc = frappe.get_doc("Leave Allocation", name)
	doc.check_permission("write")
	if doc.docstatus != 1:
		refuse(doc, _("An allocation is adjusted once it is submitted."))
	return doc


def adjust(name: str) -> dict:
	"""Two days out, put right — on the Adjustments screen's own form.

	HRMS builds a four-field dialog in JavaScript and posts it to a method on
	the allocation. This space has a screen over the document that dialog
	creates, so the verb fills in what it knows — who, which type, which
	allocation — and the screen asks the rest. Which means the required-ness
	and the validation are a doctype's rather than a dialog's, and the row is
	one somebody can find again.
	"""
	doc = _allocation(name)
	return filled(frappe.get_doc({
		"doctype": "Leave Adjustment",
		"employee": doc.employee,
		"leave_type": doc.leave_type,
		"leave_allocation": doc.name,
		"from_date": doc.from_date,
		"to_date": doc.to_date,
		"allocated_leaves": doc.total_leaves_allocated,
		"company": doc.company,
		"posting_date": nowdate(),
	}), ADJUSTMENTS)


def expire(name: str) -> dict:
	"""Write off whatever is left on it.

	HRMS's `expire_allocation`, which writes the ledger entry rather than
	editing the allocation — a balance that went down with no row saying why is
	the thing a leave ledger exists to prevent.
	"""
	from hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry import expire_allocation

	doc = _allocation(name)
	expire_allocation(doc)
	return {"ok": True}
