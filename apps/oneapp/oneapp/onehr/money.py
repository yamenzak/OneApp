"""What an advance and a final settlement turn into.

Five verbs, one that could not be written, and a line that moved.

An **Employee Advance** is money paid before it is spent, so its whole life is
what happens to the unspent part: it is claimed against, returned, or deducted
from the next payslip. HRMS has a button for each and all three were `/app`
only, which made the Advances screen a list of open balances with nothing to do
about any of them.

A **Full and Final Statement** is what a leaver is owed, and it is `Unpaid`
until a journal entry says otherwise. One button, same story.

## The one that is not a verb

HRMS's fourth button on an advance is **Expense Claim**, and it has no honest
form here. Its helper allocates the whole outstanding onto a claim with no
expenses on it, which an Expense Claim refuses twice over — an advance cannot be
allocated past the claim's sanctioned total, and `expenses` is mandatory. The
desk never meets either because it holds the claim *unsaved* while somebody
types the expenses in, and an unsaved form is the one thing this product does
not have.

Neither answer works: a dialog would drop the advance row, which is the whole
verb, and a draft cannot be inserted at all. So there is no button, and the path
is the one that was always there — raise the claim on **Claims** and pick the
advance on it, which is a child table on the form. One screen, no desk, and the
allocation is decided after the expenses are known rather than before.

## Where the line is, and where it turned out not to be

The line §6 draws is that ERPNext's accounting is not this space's. It is still
the line, and it moved once — the same way Income Tax Slab and Salary
Withholding moved — because the test is not "is it accounting" but **can the
work be finished without leaving**.

Every one of the three verbs on an advance is gated by HRMS on
`paid_amount > 0`, and `paid_amount` is written by a **Payment Entry**. So with
that doctype out, an advance could be raised here and then nothing: not claimed
against, not returned, not deducted. Three verbs that never light up is not a
line, it is a dead end — and the same one made an approved expense claim
unpayable.

So this space **drafts** the payment and does not post it. `Payment Entry` and
`Journal Entry` are granted **read**, each has a read-only screen in Pay, and
every verb here writes a draft and opens it there. What is drafted is always
HRMS's own arithmetic — the outstanding on an advance, the total on a claim, the
payables on a settlement — which is the whole reason a verb exists rather than a
form. Submitting it is still the bookkeeper's: the grant is read, so the screen
has no Save and no Submit, and the engine works that out from the grant rather
than being told.
"""

import frappe
from frappe import _

from oneapp.onehr.verbs import drafted, filled, refuse

#: The screens these verbs answer with. Names in OnePeople's manifest, resolved
#: by `run_action` against the space before the answer is handed back — so a
#: rename that missed this file fails at the verb rather than opening nothing.
EXTRA = "additional-pay"
JOURNAL = "journal"
PAYMENTS = "payments"


def installed() -> bool:
	return bool(frappe.db.exists("DocType", "Employee Advance"))


def actions() -> dict:
	return {
		"onehr/advances": [
			{
				"key": "pay-advance",
				"label": _("Draft the payment"),
				"icon": "lucide-wallet",
				"scope": "one",
				"method": "oneapp.onehr.money.pay_advance",
			},
			{
				"key": "deduct-from-salary",
				"label": _("Deduct it from salary"),
				"icon": "lucide-wallet",
				"scope": "one",
				"method": "oneapp.onehr.money.deduct",
			},
			{
				"key": "return-advance",
				"label": _("Take the money back"),
				"icon": "lucide-git-compare",
				"scope": "one",
				"method": "oneapp.onehr.money.give_back",
			},
		],
		"onehr/claims": [
			{
				"key": "pay-claim",
				"label": _("Draft the payment"),
				"icon": "lucide-wallet",
				"scope": "one",
				"method": "oneapp.onehr.money.pay_claim",
			},
		],
		"onehr/settlements": [
			{
				"key": "settle",
				"label": _("Post the journal entry"),
				"icon": "lucide-file-text",
				"scope": "one",
				"method": "oneapp.onehr.money.settle",
			},
		],
	}


def _advance(name: str):
	if not installed():
		frappe.throw(_("This workspace does not keep advances."))
	doc = frappe.get_doc("Employee Advance", name)
	doc.check_permission("write")
	if doc.docstatus != 1:
		refuse(doc, _("An advance is claimed against once it is submitted."))
	return doc


def _may_pay() -> None:
	"""Whether this reader may draft a payment at all.

	Asked here rather than left to the insert, because `claims` is a screen all
	three seats hold — an employee files their own — and a Frappe permission
	error naming Payment Entry is not a sentence that tells somebody their own
	claim is paid by somebody else.
	"""
	if not frappe.has_permission("Payment Entry", "create"):
		frappe.throw(
			_("Payments are drafted by whoever runs the pay."),
			frappe.PermissionError,
		)


def _payment(doctype: str, name: str) -> dict:
	"""HRMS's own payment for one of its documents, as a draft.

	`get_payment_entry_for_employee` is what the desk calls for an advance, a
	claim, a gratuity and an encashment alike, and it answers with an unsaved
	Payment Entry carrying the references and the outstanding. Rows, so it is a
	draft rather than a dialog — `verbs.drafted` says why.
	"""
	from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

	_may_pay()
	made = get_payment_entry_for_employee(doctype, name)
	return drafted(frappe.get_doc(made) if isinstance(made, dict) else made, PAYMENTS)


def pay_advance(name: str) -> dict:
	"""The money going out, so the advance becomes one that can be spent."""
	doc = _advance(name)
	if (doc.paid_amount or 0) >= (doc.advance_amount or 0):
		refuse(doc, _("It has been paid already."))
	return _payment("Employee Advance", doc.name)


def pay_claim(name: str) -> dict:
	"""And the claim at the other end of it."""
	doc = frappe.get_doc("Expense Claim", name)
	doc.check_permission("read")
	if doc.docstatus != 1:
		refuse(doc, _("A claim is paid once it is submitted."))
	if doc.status == "Paid":
		refuse(doc, _("It has been paid already."))
	if doc.approval_status == "Rejected":
		refuse(doc, _("It was turned down."))
	return _payment("Expense Claim", doc.name)


def deduct(name: str) -> dict:
	"""Take what is left out of the next payslip.

	The one of the three that is a *dialog* rather than a draft, because HRMS's
	`create_return_through_additional_salary` answers with an Additional Salary
	and every field on it is a scalar. So this opens **Additional pay**'s own
	New dialog, which is where the payroll date is chosen — and choosing it is
	the decision, so it is the one thing the verb does not make for anybody.
	"""
	from hrms.hr.doctype.employee_advance.employee_advance import (
		create_return_through_additional_salary,
	)

	doc = _advance(name)
	if not doc.repay_unclaimed_amount_from_salary:
		refuse(doc, _("It is not marked as repayable from salary."))

	return filled(create_return_through_additional_salary(doc), EXTRA)


def give_back(name: str) -> dict:
	"""The unspent part, returned — as a draft journal entry.

	Two account lines, so it cannot be a dialog. The amounts are HRMS's own
	arithmetic over this advance, which is the reason the verb exists at all.
	"""
	from hrms.hr.doctype.employee_advance.employee_advance import make_return_entry

	doc = _advance(name)
	left = (doc.paid_amount or 0) - (doc.claimed_amount or 0) - (doc.return_amount or 0)
	if left <= 0:
		refuse(doc, _("There is nothing left on it to return."))

	made = make_return_entry(
		employee=doc.employee,
		company=doc.company,
		employee_advance_name=doc.name,
		return_amount=left,
		advance_account=doc.advance_account,
		currency=doc.currency,
		mode_of_payment=doc.mode_of_payment,
	)
	# `make_return_entry` is whitelisted for the desk and answers with a dict
	# rather than a document, because that is what `frappe.model.sync` wants.
	return drafted(frappe.get_doc(made) if isinstance(made, dict) else made, JOURNAL)


def settle(name: str) -> dict:
	"""What the leaver is owed, posted.

	`create_journal_entry` is a method on the statement, so the payables, the
	receivables and the asset recovery are added up by the document that holds
	them. A draft, like the other two: this space writes what it can compute
	and leaves the posting to whoever keeps the books.
	"""
	doc = frappe.get_doc("Full and Final Statement", name)
	doc.check_permission("write")
	if doc.docstatus != 1:
		refuse(doc, _("A settlement is posted once it is submitted."))
	if doc.status != "Unpaid":
		refuse(doc, _("It is not waiting to be paid."))

	return drafted(doc.create_journal_entry(), JOURNAL)
