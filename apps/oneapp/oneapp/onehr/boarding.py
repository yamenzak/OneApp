"""Arriving and leaving — the two HRMS documents that make a Project.

Employee Onboarding and Employee Separation are checklists. HRMS implements the
checklist by creating an ERPNext **Project** on submit and one **Task** per
activity under it, which is a good reuse and has two consequences that neither
app owns, because each is only visible when both are installed.

**A checklist is not a job.** Those Projects land in the same table the delivery
projects live in, so a space over `Project` lists somebody's induction beside a
client's building. Fixed by typing them: every boarding Project is stamped with
`BOARDING`, and the project screens in OneProject and RUA exclude that type.
A type rather than a name prefix, because the prefix HRMS builds is translated
and would stop matching the day somebody switches language.

The same is true one level down, and only became visible once OneProject moved
onto ERPNext's Task: "Return the laptop" is not a piece of delivery work, and a
board of the quarter's tasks with twelve induction steps in it is the same
complaint as the paragraph above. So the Tasks are typed too, with a `Task
Type` of the same name, and the same screens exclude it.

**Onboarding cannot begin before the person joins.** The controller creates the
Project with `expected_start_date = date_of_joining`, then dates every task from
`boarding_begins_on` — and ERPNext's Task refuses a start before its project's.
So the one thing onboarding is for, the fortnight of preparation before somebody
walks in, is refused by the two apps together with an error naming a task.
Widened here, before the tasks are made.

Both are done by overriding one method rather than by copying `on_submit`:
`create_task_and_notify_user` runs immediately after the Project is inserted and
immediately before the first Task, which is the only moment either fix can be
applied. See `override_doctype_class` in `hooks.py`.
"""

import frappe
from frappe.utils import getdate

from hrms.hr.doctype.employee_onboarding.employee_onboarding import EmployeeOnboarding
from hrms.hr.doctype.employee_separation.employee_separation import EmployeeSeparation

#: What a boarding Project is typed as, and what the project screens exclude.
#: Not translated: it is an id that two manifests and this module compare.
BOARDING = "Employee boarding"


class Onboarding(EmployeeOnboarding):
	def create_task_and_notify_user(self):
		_own_project(self)
		super().create_task_and_notify_user()
		type_tasks(self.get("project"))


class Exit(EmployeeSeparation):
	def create_task_and_notify_user(self):
		_own_project(self)
		super().create_task_and_notify_user()
		type_tasks(self.get("project"))


def _own_project(doc) -> None:
	"""Type the Project this document just made, and let it start on time."""
	if not doc.get("project"):
		return

	values = {"project_type": _boarding_type()}

	begins = doc.get("boarding_begins_on")
	started = frappe.db.get_value("Project", doc.project, "expected_start_date")
	if begins and (not started or getdate(started) > getdate(begins)):
		values["expected_start_date"] = getdate(begins)

	frappe.db.set_value("Project", doc.project, values, update_modified=False)


def type_tasks(project: str | None) -> int:
	"""Stamp this checklist's steps, so a work board is work.

	After `super()` rather than before, because the Tasks do not exist until
	HRMS has made them — which is also why this cannot ride along with
	`_own_project`. A `db_set` rather than a save: the type is a label on rows
	the controller has just written, and re-running ERPNext's Task controller
	twelve times would re-roll the project's percent complete for a change that
	moved no date.

	Only tasks that have no type, so a workspace that categorises its induction
	steps itself keeps what it chose.
	"""
	if not project:
		return 0
	found = frappe.get_all("Task", filters={"project": project,
	                                        "type": ["is", "not set"]}, pluck="name")
	for one in found:
		frappe.db.set_value("Task", one, "type", _boarding_task_type(),
		                    update_modified=False)
	return len(found)


def _boarding_task_type() -> str:
	"""The Task Type, made once, for the same reason the Project Type is."""
	if not frappe.db.exists("Task Type", BOARDING):
		frappe.get_doc({
			"doctype": "Task Type",
			"name": BOARDING,
			"description": frappe._(
				"A step in an onboarding or an exit checklist. Not delivery work."
			),
		}).insert(ignore_permissions=True)
	return BOARDING


def _boarding_type() -> str:
	"""The Project Type, made once on the first onboarding this site submits.

	Made here rather than seeded with the space: a space is a manifest and this
	is a row, and a workspace that enabled OneHR a year ago would have to be
	migrated to get one. The first checklist makes it and every one after finds
	it.
	"""
	if not frappe.db.exists("Project Type", BOARDING):
		frappe.get_doc({
			"doctype": "Project Type",
			"project_type": BOARDING,
			"description": frappe._(
				"Onboarding and exit checklists. Not a job somebody is paid for."
			),
		}).insert(ignore_permissions=True)
	return BOARDING


# --------------------------------------------------------------------------- #
# The three verbs at either end of the checklist
#
# The two doctypes above are checklists, and a checklist has exactly two things
# you do to it that are not ticking a box: turn it into the person, and say it
# is done. HRMS draws both with `frm.add_custom_button`, so an onboarding could
# be created here and never produce an Employee — which is the one thing an
# onboarding is *for*.
#
# The third is the exit questionnaire, which belongs here for the same reason
# the separation does: it is the other end of the same arc, and it is the only
# verb in this space that sends mail.
#
# What is deliberately not here is **View Employee**, **View Project** and
# **View Task** — three of the five buttons on these forms. Those are
# navigation, and a record's connections already answer "what else is about
# this": `spaceview/connections.py` derives them from the schema rather than
# from a declaration, so a verb that only changed the address would be a tab
# with extra steps.
# --------------------------------------------------------------------------- #

from frappe import _  # noqa: E402

from oneapp.onehr.verbs import filled, refuse  # noqa: E402

#: The screens these answer with. Names in OneHR's manifest.
PEOPLE = "people"


def actions() -> dict:
	return {
		"onehr/onboarding": [
			{
				"key": "make-employee",
				"label": _("Make them an employee"),
				"icon": "lucide-user-round",
				"scope": "one",
				"method": "oneapp.onehr.boarding.make_employee",
			},
			{
				"key": "onboarding-done",
				"label": _("Mark it done"),
				"icon": "lucide-layout-grid",
				"scope": "one",
				"method": "oneapp.onehr.boarding.completed",
			},
		],
		"onehr/exit-interviews": [
			{
				"key": "send-questionnaire",
				"label": _("Send the questionnaire"),
				"icon": "lucide-mail",
				"scope": "many",
				"method": "oneapp.onehr.boarding.questionnaire",
			},
		],
	}


def make_employee(name: str) -> dict:
	"""The person this onboarding was for, as a record to check and save.

	HRMS's own mapping and HRMS's own refusal: `make_employee` calls
	`validate_employee_creation` first, which is what stops an onboarding in
	progress producing somebody who is already working here.

	A dialog rather than an insert, and this is the case the rule was written
	for — an Employee has required fields nobody can derive, a date of birth
	among them, so a verb that inserted would either fail validation or skip
	it. Skipping it is how a workspace ends up with an Employee nobody can run
	payroll for.
	"""
	from hrms.hr.doctype.employee_onboarding.employee_onboarding import (
		make_employee as mapped,
	)

	doc = frappe.get_doc("Employee Onboarding", name)
	doc.check_permission("write")
	if doc.docstatus != 1:
		refuse(doc, _("An onboarding produces somebody once it is submitted."))

	return filled(mapped(doc.name), PEOPLE)


def completed(name: str) -> dict:
	"""Every task on it closed, and the project with them.

	HRMS's `mark_onboarding_as_completed`, which closes the Project and each
	Task rather than only the checklist — the three are one thing here, and a
	checklist marked done over open tasks is a project that stays in somebody's
	list forever.
	"""
	doc = frappe.get_doc("Employee Onboarding", name)
	doc.check_permission("write")
	if doc.boarding_status == "Completed":
		refuse(doc, _("It is already done."))

	doc.mark_onboarding_as_completed()
	return {"ok": True}


def questionnaire(name: str) -> dict:
	"""Ask the leaver what they thought, before they go.

	`many`, because exits come in waves and the whole point of a questionnaire
	is that nobody writes it per person. HRMS skips anybody it has already been
	sent to, so running it twice over the same list is safe by construction —
	and it refuses outright where the workspace has not said which web form to
	send, which is a setting on **Rules**.
	"""
	from hrms.hr.doctype.exit_interview.exit_interview import send_exit_questionnaire

	doc = frappe.get_doc("Exit Interview", name)
	doc.check_permission("write")
	if doc.questionnaire_email_sent:
		refuse(doc, _("It has already gone out."))

	send_exit_questionnaire([{"name": doc.name}])
	return {"ok": True}
