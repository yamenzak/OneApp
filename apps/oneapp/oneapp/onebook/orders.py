"""The middle of the chain, and the one verb that moves along it.

`docs/ONEBOOK.md` §5. OneCRM raises a Quotation, OneBook raises a Sales
Invoice, and until this there was nothing between them: a workspace could say
what it had offered and what it had billed, and not what it had *agreed*.

That sounds like a goods question and the measurement says otherwise.
ERPNext's `Project` already computes `total_billed_amount` from its invoices,
`total_costing_amount` from its timesheets, `total_purchase_cost` from its
bills, and a gross margin from the three — and `total_sales_amount` **from a
Sales Order and from nothing else**. So a workspace without orders has a
project that knows what it has billed and what it has cost and not what it was
worth, which is the denominator of every question a services firm asks about a
contract. `per_billed` on the order is the other half: how much of this is
still to bill.

## Their mappers, called rather than copied

`quotation.mapper.make_sales_order` and `sales_order.mapper.make_sales_invoice`
are `get_mapped_doc` definitions — a field map per doctype, a per-row condition
that skips what is already fulfilled, and a `postprocess` that reprices against
today's rate and recalculates the taxes. Rewriting either would be rewriting
"what carries forward from a quote to an order", which is a question with
twenty answers in it and no interesting ones.

## A draft, and never more than a draft

Both verbs insert what the mapper returns and stop. Nothing is submitted:
converting is a clerical act and submitting is a ledger act, and the second is
a decision somebody makes while looking at the document. So the verb ends by
opening the draft it made, which is also the only honest thing to do with a
document that has just copied twenty fields off another one.

**The reader's own permissions decide**, not this module: `insert` is checked
by Frappe on the way in, so a seat that may not raise an invoice cannot reach
one through an order.
"""

import frappe
from frappe import _

#: Where each verb lands, as a screen of the space that offers it.
#:
#: `spaceview/run.py` resolves the name against the space the action was
#: pressed in and refuses one belonging to somebody else, so these are not
#: arbitrary strings — a verb cannot open a screen its own space has not got.
ORDERS = "orders"
INVOICES = "invoices"

#: The two mappers, named here and nowhere else. An action's method is shipped
#: code rather than a request parameter, and this keeps the dotted paths in one
#: file so `oneapp/adapters/erpnext.py` has something to be read against.
FROM_QUOTATION = "erpnext.selling.doctype.quotation.mapper.make_sales_order"
FROM_ORDER = "erpnext.selling.doctype.sales_order.mapper.make_sales_invoice"


def _mapped(path: str, source: str):
	"""Run one of their mappers and keep the draft it returns.

	`get_mapped_doc` hands back an unsaved document, which is the whole point:
	everything it decided is visible on the form before anybody commits to it.
	`ignore_permissions` is deliberately *not* passed — a reader who may not
	create the target should fail here, at the insert, rather than be handed a
	form they cannot save.
	"""
	made = frappe.get_attr(path)(source)
	made.insert()
	return made


def bill(name: str) -> dict:
	"""Invoice what is left of this order.

	Their mapper takes off what has already been billed, row by row, so a
	second press against a part-billed order opens an invoice for the
	remainder rather than for the whole thing again. An order with nothing
	left says so instead.
	"""
	order = frappe.get_doc("Sales Order", name)
	order.check_permission("read")
	if order.docstatus != 1:
		frappe.throw(_("An order is billed once it is submitted."))
	if frappe.utils.flt(order.per_billed) >= 100:
		frappe.throw(_("Every part of this order has been billed."))

	made = _mapped(FROM_ORDER, order.name)
	return {"open": {"screen": INVOICES, "name": made.name}}


def order(name: str) -> dict:
	"""Turn this quotation into the order it was accepted as.

	Offered on OneCRM's quotations screen, because that is where somebody is
	standing when the customer says yes — and it lands in OneBook, because an
	order is a commitment to bill and billing is this space's.
	"""
	quote = frappe.get_doc("Quotation", name)
	quote.check_permission("read")
	if quote.docstatus != 1:
		frappe.throw(_("A quotation becomes an order once it is submitted."))
	if quote.status == "Lost":
		frappe.throw(_("That quotation was lost."))

	made = _mapped(FROM_QUOTATION, quote.name)
	return {"open": {"screen": ORDERS, "name": made.name}}


def actions() -> dict:
	"""The two verbs, on the two screens they belong to.

	Declared in code rather than in a manifest for the reason
	`spaceview/actions.py` opens with: an action names a method, and a list of
	methods a workspace could extend by editing a row is not a thing to have.

	Both are `one`: converting two quotations at once would open one of the two
	orders and silently make the other, which is the shape `run_action`'s own
	`_next` refuses to guess at.
	"""
	return {
		"onebook/orders": [
			{
				"key": "bill",
				"label": _("Invoice what is left"),
				"icon": "lucide-receipt",
				"scope": "one",
				"method": "oneapp.onebook.orders.bill",
			},
		],
	}
