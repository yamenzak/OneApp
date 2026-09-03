"""Retention: the part of an invoice the customer keeps until the job is proved.

A subcontractor bills for work done and the main contractor withholds five or
ten per cent of it until the defects period ends — a year, usually. It is money
earned and not yet collectible, and it is the single largest thing wrong with a
construction company's books when nobody models it: the receivables ledger says
a hundred thousand is due, the person chasing it finds ninety, and the ten that
is missing is not late, it is held.

ERPNext has no retention. What it has is the pieces to build one honestly:

* The **deduction** is a Sales Taxes and Charges row with a negative rate. It
  comes off the invoice's total, so what lands in Debtors is what the customer
  actually owes now.
* The **held amount** goes to its own asset account. It is still owed — it is
  not a discount and not a bad debt — so it sits as a receivable that nobody is
  chasing yet, and the ageing report stops lying.
* The **release**, a year later, is a Journal Entry: debit Debtors, credit
  Retention Receivable. From that moment it ages and is collected like anything
  else. Nothing here does that, because releasing retention is a decision and
  not a calculation.

**VAT is charged on the whole supply**, before the deduction. Retention is when
the customer pays, not what the customer buys, so the tax is due on the full
value — which is why the VAT row is computed on the net total and the retention
row is separate. The system this replaces worked its VAT out on the amount
*after* retention, which under-declares output tax; it never actually withheld
anything, so no invoice it issued is wrong, and the arithmetic will not be
carried forward.

Dormant unless somebody asks for it: an invoice with no `custom_retention_percentage`
field, or a zero in it, is left exactly as it is. The field is what turns this
on, and an import plan that creates it — see `plans/rua.py` — is what turns it
on for a workspace that needs it.
"""

import frappe
from frappe import _
from frappe.utils import flt

FIELD = "custom_retention_percentage"

# The account the withheld money waits in. A plain asset and deliberately not
# `Receivable`: ERPNext requires a party on every entry against a receivable
# account, and a taxes-and-charges row has none. The party is on the invoice
# that made it, which is where somebody looks.
ACCOUNT = "Retention Receivable"
ROOT = "Asset"

DESCRIPTION = "Retention withheld"


def apply(doc, method=None):
	"""Put this invoice's retention on it, or take a stale row off.

	Runs on every save, so it is written as "make the row match the field"
	rather than "add a row": an invoice edited from ten per cent to five would
	otherwise carry both.
	"""
	if not doc.meta.has_field(FIELD):
		return

	held = flt(doc.get(FIELD))
	name = _name(doc.company)

	# Whatever this put there last time, gone — matched on the account rather
	# than the description, because a person may edit a description and the
	# next save would then leave the old row behind and add another.
	doc.set("taxes", [row for row in (doc.get("taxes") or [])
	                  if row.account_head != name])

	if not held:
		return

	if held < 0 or held >= 100:
		frappe.throw(_("Retention is a percentage of the invoice, between 0 and 100."))

	doc.append("taxes", {
		"charge_type": "On Net Total",
		"account_head": _account(doc.company),
		"description": f"{DESCRIPTION} ({held:g}%)",
		# Negative, which is the whole mechanism: a charge that takes away.
		"rate": -held,
		# Off the total and out of the tax base both — the row below it is not
		# a tax on this and there is nothing to compound.
		"included_in_print_rate": 0,
	})

	# A document hook runs *after* the controller's own `validate`, so the
	# invoice has already been totalled by the time this row exists. Without
	# this the row sits there with an amount of zero and a grand total that
	# still says the customer owes the retention — which is a wrong invoice
	# that looks right, and is exactly what the first run against a real
	# ERPNext produced.
	if hasattr(doc, "calculate_taxes_and_totals"):
		doc.calculate_taxes_and_totals()


def _name(company: str) -> str:
	"""What the account is called on this company's books."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	return f"{ACCOUNT} - {abbr}"


def _account(company: str) -> str:
	"""The account, made once per company.

	Made rather than asked for: a workspace that has turned retention on has
	already said what it wants, and stopping to demand an account they have not
	heard of is a worse first invoice than one that reconciles.
	"""
	name = _name(company)
	if frappe.db.exists("Account", name):
		return name

	parent = _parent(company)
	if not parent:
		frappe.throw(_("This company's chart of accounts has nowhere to put retention."))

	frappe.get_doc({
		"doctype": "Account",
		"account_name": ACCOUNT,
		"parent_account": parent,
		"company": company,
		"root_type": ROOT,
		"is_group": 0,
		"account_currency": frappe.get_cached_value("Company", company, "default_currency"),
	}).insert(ignore_permissions=True)
	return name


def _parent(company: str) -> str | None:
	"""Wherever this company keeps the money it is owed.

	Read off the company's own receivable account rather than matched by name:
	charts of accounts differ by country and "Accounts Receivable" is called
	four things across the ones ERPNext ships, but every company has a default
	receivable account and its parent is the right neighbourhood on all of them.
	"""
	receivable = frappe.get_cached_value("Company", company, "default_receivable_account")
	if receivable:
		return frappe.db.get_value("Account", receivable, "parent_account")

	found = frappe.get_all(
		"Account", filters={"company": company, "is_group": 1, "root_type": ROOT},
		pluck="name", order_by="lft asc", limit=1,
	)
	return found[0] if found else None
