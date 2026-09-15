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


class Exit(EmployeeSeparation):
	def create_task_and_notify_user(self):
		_own_project(self)
		super().create_task_and_notify_user()


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


def _boarding_type() -> str:
	"""The Project Type, made once on the first onboarding this site submits.

	Made here rather than seeded with the space: a space is a manifest and this
	is a row, and a workspace that enabled OnePeople a year ago would have to be
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
