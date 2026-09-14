"""Who the reader is here, and the one rule about reading a row that is about them.

Two small things that three other modules in OneHR need and none of them owns.

**Who "me" is.** The Employee whose `user_id` is the session's user, and nothing
else. Not a match on email, which is one line shorter and hands somebody their
namesake's record on any workspace where two people share a personal address, and
not a match on name. A reader with no such row is nobody here — which is a
workspace that has not linked its logins, and the fix is a field on a record.

**The rule.** OneHR's Employee seat is granted `if_owner` on everything a person
*files*: you raise your own leave application and cannot read the one at the next
desk. That idiom is right and it covers exactly half of what a self-service page
is about, because the other half is not filed by its subject at all:

    if_owner              what you filed          leave applications, claims
    this module           what was filed about you  attendance, allocations, pay

An Attendance row is written by a scheduled job. A Leave Allocation is written by
the people officer. A payslip is written by payroll. Their owner is never their
subject, so `if_owner` returns nothing for precisely the rows a person most wants
to see about themselves — and the alternative, granting the doctype outright, is
how an Employee seat comes to read the whole company's attendance.

So: **your own row needs no grant; anybody else's needs the doctype.** One
sentence, one function, and it is a narrowing rather than a second permission
path — the same shape as the favourites filter in `spaceview/filters.py`, which
can only ever mean the session's own user because the value is not the caller's
to supply. `may_read` cannot be pointed at a colleague and answer yes; if it is
pointed at one, it asks the ordinary grant and that is the whole answer.

This does not make anything readable that Frappe would refuse — it decides
whether OneHR's own endpoints will read on your behalf, and every one of them
then filters on the employee this returned rather than on one a caller sent.
"""

import frappe


def installed() -> bool:
	return bool(frappe.db.exists("DocType", "Employee"))


def employee_of(user: str | None = None) -> str:
	"""The Employee this user *is*, or an empty string.

	`ignore_permissions` is what `frappe.get_all` does anyway, and it is right
	here for the same reason the favourites filter is: the only filter is the
	session's own user, so there is no row this can return that is not the
	caller's own. A seat that cannot read Employee at all still has to be able
	to find out that it is nobody.
	"""
	if not installed():
		return ""
	found = frappe.get_all(
		"Employee",
		filters={"user_id": user or frappe.session.user},
		pluck="name",
		limit=1,
	)
	return found[0] if found else ""


def may_read(doctype: str, employee: str) -> bool:
	"""Whether OneHR will read this doctype's rows about this person, for this reader.

	Their own: yes, without the grant — that is the rule this module exists for.
	Anybody else's: the ordinary question, asked of Frappe, which is what the
	people officer's wider grant answers and the Employee seat's does not.

	The doctype has to be on the site either way. A workspace without HRMS gets
	`False` and the block that asked draws its empty line.
	"""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return False
	if employee and employee == employee_of():
		return True
	return bool(frappe.has_permission(doctype, "read"))
