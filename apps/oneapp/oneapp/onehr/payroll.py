"""Running a payroll cycle, which was the last thing here that needed the desk.

A Payroll Entry is not a document somebody fills in and submits. It is a
**machine**, and every state of it is advanced by a button HRMS declares in
JavaScript:

    Get Employees          draft, before there is anybody on it
    Create Salary Slips    submitting the entry is what makes them
    Submit Salary Slip     and that writes the accrual journal entry
    Make Bank Entry        once they are submitted
    Release Withheld       for whoever was held back
    Create/Submit Overtime where overtime rides on the same run

`frm.add_custom_button` is a door this product does not have and should not —
`docs/UNIFICATION.md` rail 34 refuses a tenant-shipped script — so all seven
were reachable only from `/app`. A workspace could see its payroll runs here and
could not run one, which is the sharpest form the "no desk" rule can be broken
in: a screen that lists the thing and cannot do the thing.

## What is here and what is not

**Nothing computes a payslip.** Every verb below calls HRMS's own method on
HRMS's own document, after checking the same permission the desk checks. What is
written here is the part the desk wrote in JavaScript: which method, when it
makes sense, and what the reader should see afterwards.

**One of the seven is already in the product.** "Create Salary Slips" on a draft
is literally `frm.save("Submit")` — submitting the Payroll Entry is what creates
them — and the record header has offered Submit since `docflow` shipped. So the
verb here is the *retry*, which is the only other place the desk draws that
button: a run whose slips failed halfway.

**Offered always, refused precisely.** `hiring.py` states the rule and this
follows it: a button that vanishes at some statuses is a button nobody learns is
there. Every verb is on every row, and a verb in the wrong state answers with
the sentence that says which state it wanted. The alternative — hiding them —
also costs an engine change, because an action is resolved per *screen* and
these would have to be resolved per *record*.
"""

import frappe
from frappe import _

#: The doctype all seven act on.
ENTRY = "Payroll Entry"

#: Where a bank entry is opened once it exists. A journal entry is the only way
#: to get from a payslip to the money leaving the account, which the manifest
#: has said since this space shipped — and `journal` is the screen that finally
#: makes the sentence true.
JOURNAL = "journal"


def installed() -> bool:
	return bool(frappe.db.exists("DocType", ENTRY))


def actions() -> dict:
	"""The payroll cycle, as verbs on the Payroll runs screen."""
	return {
		"onehr/payroll": [
			{
				"key": "get-employees",
				"label": _("Get employees"),
				"icon": "lucide-users",
				"scope": "one",
				"method": "oneapp.onehr.payroll.get_employees",
			},
			{
				"key": "create-slips",
				"label": _("Create the payslips"),
				"icon": "lucide-receipt",
				"scope": "one",
				"method": "oneapp.onehr.payroll.create_slips",
			},
			{
				"key": "submit-slips",
				"label": _("Submit the payslips"),
				"icon": "lucide-receipt",
				"scope": "one",
				# The one verb with a confirmation on it, and the desk has one
				# too: submitting the slips is what writes the accrual journal
				# entry, so it is the step that reaches the ledger.
				"confirm": _("This submits every payslip on this run and writes "
				             "the accrual journal entry."),
				"method": "oneapp.onehr.payroll.submit_slips",
			},
			{
				"key": "bank-entry",
				"label": _("Make the bank entry"),
				"icon": "lucide-wallet",
				"scope": "one",
				"method": "oneapp.onehr.payroll.bank_entry",
			},
			{
				"key": "release-withheld",
				"label": _("Release withheld pay"),
				"icon": "lucide-wallet",
				"scope": "one",
				"method": "oneapp.onehr.payroll.release_withheld",
			},
			{
				"key": "overtime-slips",
				"label": _("Overtime slips"),
				"icon": "lucide-clock",
				"scope": "one",
				"method": "oneapp.onehr.payroll.overtime",
			},
		],
	}


def _entry(name: str):
	"""One payroll run, or a refusal.

	`get_doc` and then `check_permission`, which is what every one of HRMS's own
	methods does on the way in — so this is the same gate asked one step
	earlier, where the message can name the run rather than the doctype.
	"""
	if not installed():
		frappe.throw(_("This workspace does not run payroll."))
	doc = frappe.get_doc(ENTRY, name)
	doc.check_permission("write")
	return doc


def _refuse(doc, wanted: str) -> None:
	"""Say which state the verb wanted, and which one this run is in.

	The whole of the "offered always" rule rests on this reading well. A
	refusal that said "not allowed" would make a menu of six verbs a menu of
	six guesses.
	"""
	frappe.throw(
		_("{0} is {1}. {2}").format(doc.name, _(doc.status or _("Draft")), wanted)
	)


def get_employees(name: str) -> dict:
	"""Fill the run with the people its filters describe.

	HRMS's `fill_employee_details` writes the child table on the document *in
	memory* and leaves the desk to save it — `get_employee_details` in
	`payroll_entry.js` calls `frm.dirty(); frm.save()` right after. So the save
	is ours to do, and forgetting it is a button that appears to work and
	changes nothing.
	"""
	doc = _entry(name)
	if doc.docstatus != 0:
		_refuse(doc, _("Employees are only gathered while it is a draft."))

	doc.fill_employee_details()
	doc.save()
	return {"employees": len(doc.employees or [])}


def create_slips(name: str) -> dict:
	"""Make the payslips, where submitting the run did not.

	Submitting a Payroll Entry is what creates them, and the record header
	already offers Submit — so this is the retry the desk draws in exactly one
	other place: a run that failed partway and has an error on it.
	"""
	doc = _entry(name)
	if doc.docstatus != 1:
		_refuse(doc, _("Submit the run to make its payslips."))
	if doc.salary_slips_created:
		_refuse(doc, _("Its payslips are already made."))

	doc.create_salary_slips()
	return {"ok": True}


def submit_slips(name: str) -> dict:
	"""Submit them, which is also what writes the accrual entry.

	Above thirty people HRMS queues the work and says so, and this does not
	unwind that: the run's own status goes to Queued and the screen shows it.
	"""
	doc = _entry(name)
	if not doc.salary_slips_created:
		_refuse(doc, _("Its payslips have not been made yet."))
	if doc.salary_slips_submitted:
		_refuse(doc, _("Its payslips are already submitted."))

	doc.submit_salary_slips()
	return {"ok": True}


def bank_entry(name: str) -> dict:
	"""The journal entry that pays everybody, and the screen that shows it."""
	return _bank(name, withheld=False)


def release_withheld(name: str) -> dict:
	"""And the second one, for whoever was held back.

	The same HRMS method with its one flag set, which is how the desk does it
	too. `Salary Withholding` is the screen those people are on — it moved off
	the "deliberately not here" list in `docs/ERP-SPACES.md` §6 for the same
	reason this verb exists.
	"""
	return _bank(name, withheld=True)


def _bank(name: str, withheld: bool) -> dict:
	doc = _entry(name)
	if not doc.salary_slips_submitted:
		_refuse(doc, _("Its payslips have to be submitted first."))
	if not doc.payment_account:
		frappe.throw(_("{0} names no payment account, so there is nothing to "
		               "pay it from.").format(doc.name))

	# Whether it has been paid already, which is the one guard here that is not
	# about reading well. `make_bank_entry` is not idempotent — it writes a
	# fresh journal entry every time it is called — so a verb without this is a
	# button that pays everybody twice, and the second press looks exactly like
	# the first. The desk asks the same question before it draws the button;
	# this asks it before it does the work, which is the difference between
	# hiding a mistake and refusing one.
	made = doc.has_bank_entries() or {}
	if withheld and made.get("has_bank_entries_for_withheld_salaries"):
		frappe.throw(_("The withheld pay on {0} has already gone out.")
		             .format(doc.name))
	if not withheld and made.get("has_bank_entries"):
		frappe.throw(_("{0} has already been paid out.").format(doc.name))

	made = doc.make_bank_entry(for_withheld_salaries=withheld)
	if not made:
		# Not an error. `make_bank_entry` answers with nothing when the total
		# is zero or below — a run of statistical components, or withheld pay
		# that has already gone out — and saying so is better than a button
		# that reports success and produced no entry.
		frappe.msgprint(_("There was nothing left to pay out."), alert=True)
		return {"ok": True}

	return {"open": {"screen": JOURNAL, "name": made.name}}


def overtime(name: str) -> dict:
	"""Whichever of the two overtime steps this run is on.

	One verb rather than two, and it is the one place these differ from the
	desk. HRMS draws "Create Overtime Slips" or "Submit Overtime Slips"
	depending on `overtime_step`, which is a field the document keeps precisely
	so that only one of them is ever the right one — so a single button that
	does the step the run is on says the same thing with one less decision.
	"""
	doc = _entry(name)
	step = (doc.get("overtime_step") or "").strip()
	if step == "Create":
		doc.create_overtime_slips()
		return {"ok": True, "did": "create"}
	if step == "Submit":
		doc.submit_overtime_slips()
		return {"ok": True, "did": "submit"}
	_refuse(doc, _("It has no overtime step outstanding."))
