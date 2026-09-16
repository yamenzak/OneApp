"""Posting time to the ledger, where a workspace keeps one.

`docs/WORK.md` §3 and stage 6. The rule this file exists to hold: **OneTask
does not bill.** A `One Time Entry` is the record of an hour and nothing else;
turning hours into money is ERPNext's Timesheet and the invoice that reads it,
and a workspace that does not carry ERPNext still keeps perfectly good time.

So this is a **bridge and not a feature**. It runs only where the app is
installed, it writes ERPNext's own doctype through ERPNext's own controller,
and it marks each row it posted so an hour cannot reach an invoice twice. If
somebody deletes the Timesheet at the other end, the mark is what tells us —
`posted_on` with no Timesheet behind it is a row to post again, not a row to
bill twice.

What it deliberately does not do is *price*. A rate belongs to the customer,
the activity and the person, and ERPNext already has all three in a place
somebody maintains; inventing a fourth here would be the number that disagrees
on the invoice.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime


def installed() -> bool:
	"""Whether there is a ledger to post to at all."""
	return "erpnext" in (frappe.get_installed_apps() or [])


#: How many stretches one call may post.
#:
#: A month of one person's time is about a hundred and fifty rows, so this is
#: three months in one press and a ceiling somebody can feel rather than a
#: limit they hit weekly.
MOST = 500


@frappe.whitelist(methods=["POST"])
def post(names: str | list = "") -> dict:
	"""Post billable time to ERPNext Timesheets, one per person per project.

	Grouped, because that is what a Timesheet *is* over there: a document with
	a person on it and a table of stretches. One per row would be a hundred
	documents for a month and an invoice nobody can read.

	Already-posted rows are skipped rather than refused: the ordinary way to
	use this is to press it again at the end of the week, and a call that threw
	because one row of forty had been posted would be a call nobody presses.
	"""
	if not installed():
		frappe.throw(_("This workspace does not bill through ERPNext."))

	wanted = names if isinstance(names, list) else frappe.parse_json(names or "[]")
	if not isinstance(wanted, list) or not wanted:
		frappe.throw(_("Nothing was chosen to post."))

	rows = frappe.get_all(
		"One Time Entry",
		filters={
			"name": ["in", wanted[:MOST]],
			"billable": 1,
			"posted_on": ["is", "not set"],
			"ends_at": ["is", "set"],
		},
		fields=["name", "task", "project", "person", "starts_at", "ends_at",
		        "minutes", "note"],
		order_by="person asc, project asc, starts_at asc",
	)
	if not rows:
		return {"posted": 0, "timesheets": []}

	for row in rows:
		frappe.has_permission("One Time Entry", "write", doc=row["name"], throw=True)

	made = []
	for (person, project), stretches in _grouped(rows).items():
		sheet = frappe.get_doc({
			"doctype": "Timesheet",
			"employee": _employee(person),
			"parent_project": _ledger_project(project),
			"time_logs": [_log(one) for one in stretches],
		})
		sheet.insert(ignore_permissions=True)
		made.append(sheet.name)
		for one in stretches:
			frappe.db.set_value("One Time Entry", one["name"], {
				"posted_on": frappe.utils.now_datetime(),
				"timesheet": sheet.name,
			}, update_modified=False)

	return {"posted": len(rows), "timesheets": made}


def _grouped(rows: list[dict]) -> dict:
	"""One bucket per person and project, in the order they came."""
	found: dict = {}
	for row in rows:
		found.setdefault((row["person"], row.get("project") or ""), []).append(row)
	return found


def _log(row: dict) -> dict:
	"""One stretch, as a Timesheet Detail.

	No rate and no amount. ERPNext reads those from the activity type, the
	project and the customer, all of which somebody maintains over there — and
	a number invented here is the one that disagrees on the invoice.
	"""
	return {
		"from_time": get_datetime(row["starts_at"]),
		"to_time": get_datetime(row["ends_at"]),
		"hours": round((row.get("minutes") or 0) / 60.0, 4),
		"description": row.get("note") or "",
		"is_billable": 1,
	}


def _ledger_project(project: str) -> str | None:
	"""ERPNext's Project of the same name, where the workspace keeps one.

	A `One Project` is not an ERPNext `Project` and must not pretend to be: a
	workspace can run OneTask with no ledger at all, and the two are only the
	same thing where somebody deliberately made them so. So the link is by
	name, it is optional, and time against a project ERPNext has never heard of
	still posts — as hours on a Timesheet, which is what was asked for.
	"""
	if not project or not frappe.db.exists("DocType", "Project"):
		return None
	return frappe.db.get_value("Project", {"project_name": project}, "name") or None


def _employee(user: str) -> str | None:
	"""The Employee behind a user, where HR is installed and one exists.

	Optional on purpose: a Timesheet without an employee is still a record of
	hours against a project, and a workspace that bills for contractors has
	people with no Employee row at all. Refusing them would make the bridge
	useless exactly where it is most wanted.
	"""
	if not frappe.db.exists("DocType", "Employee"):
		return None
	return frappe.db.get_value("Employee", {"user_id": user}, "name") or None


def actions() -> dict:
	"""The verb, on the screen a lead bills from.

	Only where there is a ledger: a button that throws "this workspace does not
	bill through ERPNext" is a button that should not have been drawn.
	"""
	if not installed():
		return {}
	return {
		"onetask/time": [
			{
				"key": "post-time",
				"label": _("Post to a timesheet"),
				"icon": "lucide-receipt",
				"scope": "many",
				"method": "oneapp.onetask.billing.post_one",
			},
		],
	}


@frappe.whitelist(methods=["POST"])
def post_one(name: str = "") -> dict:
	"""What the action runner calls, once per chosen row.

	The runner hands each record's name to the method in turn — see
	`spaceview/run.py` — so the grouping above happens over one row at a time
	here. Which is right for the ordinary case and honest about the other: a
	person posting a month from the list gets a Timesheet per row of the
	selection they made, and `post` is there for a caller that has the whole
	list in hand.
	"""
	return post([name] if name else [])
