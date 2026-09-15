"""Running an appraisal cycle, and closing a training event.

An **Appraisal Cycle** is the other state machine in this space — `payroll.py`
is the first. Nothing on it is edited; it is *advanced*: find the people it is
about, make an appraisal each, start it, and mark it done. All four were
`frm.add_custom_button` and therefore `/app` only, which made the Appraisals
screen a list of rows nobody here could create.

A **Training Event** ends in two documents — who passed, and what they thought —
and both had screens before they had a way in. §5 of `docs/ERP-SPACES.md` calls
this the recurring shape: HRMS splits the event from what people said about it,
the event is what a rail entry is named after, and the part anybody re-reads is
left behind.

## What is deliberately not a verb

**Goal's four status buttons** — Archive, Unarchive, Close, Reopen. HRMS draws
them because its form has no other way to set a field on a submitted document;
ours does. `status` is an ordinary Select on the Goals screen, editable on the
record and draggable on the board, so four buttons would be four more words for
something already doable in one. A verb earns its place by doing something the
form cannot.

**Appraisal's View Goals** and the cycle's, which are navigation. A record's
connections already answer "what else is about this" — `spaceview/connections.py`
— and a verb that only changes the address is a tab with extra steps.
"""

import frappe
from frappe import _

from oneapp.onehr.verbs import filled, refuse

RESULTS = "training-results"
FEEDBACK = "training-feedback"


def installed() -> bool:
	return bool(frappe.db.exists("DocType", "Appraisal Cycle"))


def actions() -> dict:
	return {
		"onehr/cycles": [
			{
				"key": "find-appraisees",
				"label": _("Find the people"),
				"icon": "lucide-users",
				"scope": "one",
				"method": "oneapp.onehr.growth.find_people",
			},
			{
				"key": "create-appraisals",
				"label": _("Create the appraisals"),
				"icon": "lucide-chart-line",
				"scope": "one",
				"method": "oneapp.onehr.growth.create_appraisals",
			},
			{
				"key": "move-cycle",
				"label": _("Move it on"),
				"icon": "lucide-git-compare",
				"scope": "one",
				"method": "oneapp.onehr.growth.move_on",
			},
		],
		"onehr/training": [
			{
				"key": "training-result",
				"label": _("Record the results"),
				"icon": "lucide-graduation-cap",
				"scope": "one",
				"method": "oneapp.onehr.growth.result",
			},
			{
				"key": "training-feedback",
				"label": _("Ask for feedback"),
				"icon": "lucide-message-square",
				"scope": "one",
				"method": "oneapp.onehr.growth.feedback",
			},
		],
	}


def _cycle(name: str):
	if not installed():
		frappe.throw(_("This workspace does not run appraisals."))
	doc = frappe.get_doc("Appraisal Cycle", name)
	doc.check_permission("write")
	return doc


def find_people(name: str) -> dict:
	"""Fill the cycle with everybody its filters describe.

	The same shape as a payroll run's Get employees, and the same trap: HRMS's
	`set_employees` writes the child table in memory and leaves the desk to
	save. A verb that forgot the save would look exactly like one that worked.
	"""
	doc = _cycle(name)
	if doc.status == "Completed":
		refuse(doc, _("It is finished."))

	doc.set_employees()
	doc.save()
	return {"appraisees": len(doc.appraisees or [])}


def create_appraisals(name: str) -> dict:
	"""One appraisal per person on it, against the cycle's template.

	Above a handful HRMS enqueues the work and says so, which this does not
	unwind. Nothing here computes a score: an appraisal is made empty and
	filled in by the people whose opinion it is.
	"""
	doc = _cycle(name)
	if doc.status == "Completed":
		refuse(doc, _("It is finished."))
	if not (doc.appraisees or []):
		refuse(doc, _("Nobody is on it yet — find the people first."))

	doc.create_appraisals()
	return {"ok": True}


def move_on(name: str) -> dict:
	"""Whichever step the cycle is on, in the direction it goes.

	One verb rather than three, and it is the same argument the overtime verb
	in `payroll.py` makes: HRMS draws Start, Mark as Completed or Mark as In
	Progress depending on `status`, which is a field the document keeps exactly
	so that only one of them is ever the right one. Reading the field is one
	decision fewer than three buttons, two of which always refuse.

    	Not Started  →  In Progress
    	In Progress  →  Completed
    	Completed    →  In Progress

	The third is a reopening rather than a step on, and it is here for the same
	reason HRMS has it: a cycle marked done a week early is otherwise done.
	"""
	doc = _cycle(name)
	if doc.status == "Not Started":
		doc.status = "In Progress"
		doc.save()
		return {"ok": True, "status": doc.status}
	if doc.status == "In Progress":
		# HRMS's own, because completing a cycle is not a status write: it
		# submits the appraisals under it and refuses where one is unfinished.
		doc.complete_cycle()
		return {"ok": True, "status": "Completed"}
	if doc.status == "Completed":
		doc.status = "In Progress"
		doc.save()
		return {"ok": True, "status": doc.status}
	refuse(doc, _("There is no next step for it."))


def _event(name: str):
	doc = frappe.get_doc("Training Event", name)
	doc.check_permission("read")
	if not (doc.employees or []):
		refuse(doc, _("Nobody is down as attending it."))
	return doc


def result(name: str) -> dict:
	"""How it went, per person — the target screen's own New dialog.

	The event and nothing else. A Training Result's rows are an employee each
	with a grade somebody types, and filling them in *is* the document, so a
	verb that pre-populated them would be a verb with an opinion about the
	answer. HRMS's own form pulls them from the event's attendance list when
	the event is chosen.
	"""
	doc = _event(name)
	return filled(frappe.get_doc({"doctype": "Training Result",
	                              "training_event": doc.name}), RESULTS)


def feedback(name: str) -> dict:
	"""And what somebody thought of it.

	Granted `if_owner` to the employee seat, so this verb is the people
	officer's way in and the screen is everybody else's: you file your own and
	the officer sees them all. One manifest, two lists — §5.
	"""
	doc = _event(name)
	return filled(frappe.get_doc({"doctype": "Training Feedback",
	                              "training_event": doc.name}), FEEDBACK)
