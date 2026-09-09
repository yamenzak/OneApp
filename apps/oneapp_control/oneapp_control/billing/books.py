"""Mirror billing into ERPNext.

The control plane runs ERPNext so our own revenue is bookkept in the same system
we sell, rather than in a bespoke table that has to be reconciled by hand at
year end. Tenants are Customers; payments become Sales Invoices — and then
Payment Entries, which is the half that was missing.

An invoice on its own says what somebody owes. Every one of ours is already
paid at the moment it is raised, so a book of nothing but invoices shows every
customer permanently outstanding, and there is no account for a Stripe payout
to land against. So each invoice is settled straight away into a clearing
account standing for the Stripe balance, less the fee Stripe kept — which
leaves that account holding exactly what the next payout will be worth, and
makes reconciling it a match rather than an investigation.

The fee is not on the invoice and not on the charge: it is on the charge's
balance transaction, which is also why a payout is the net of a batch rather
than the sum of its charges.

Everything here is best-effort and must never break a webhook: if bookkeeping
fails, the customer has still paid and their credits must still land. Failures
are logged for an operator, not raised.
"""

import functools

import frappe
from frappe.utils import flt, getdate

from oneapp_control.billing import stripe_client

DEFAULT_ITEM = "OneSpace Subscription"
CREDIT_ITEM = "OneSpace Credits"
STORAGE_ITEM = "OneSpace Storage"


def _safe(fn):
	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except Exception:
			frappe.log_error(
				title=f"ERPNext bookkeeping failed in {fn.__name__}",
				message=frappe.get_traceback(),
			)
			return None

	return wrapper


def ensure_customer(tenant: str) -> str | None:
	"""Create the ERPNext Customer for a tenant on first payment."""
	existing = frappe.db.get_value("Tenant", tenant, "customer")
	if existing and frappe.db.exists("Customer", existing):
		return existing

	tenant_doc = frappe.get_doc("Tenant", tenant)
	name = frappe.db.get_value("Customer", {"customer_name": tenant_doc.tenant_name})

	if not name:
		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": tenant_doc.tenant_name,
				"customer_type": "Company",
				"customer_group": _default("Customer Group", "customer_group"),
				"territory": _default("Territory", "territory"),
			}
		).insert(ignore_permissions=True)
		name = customer.name

	tenant_doc.db_set("customer", name)
	return name


def _default(doctype: str, key: str):
	value = frappe.db.get_single_value("Selling Settings", key)
	if value:
		return value
	return frappe.db.get_value(doctype, {"is_group": 0}, "name")


def ensure_item(item_code: str, description: str) -> str:
	if frappe.db.exists("Item", item_code):
		return item_code

	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"description": description,
			"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"is_sales_item": 1,
		}
	).insert(ignore_permissions=True)

	return item_code


@_safe
def record_invoice(subscription, stripe_invoice: dict):
	"""Create a Sales Invoice mirroring a paid Stripe invoice."""
	invoice_id = stripe_invoice.get("id")

	# Stripe can deliver invoice.paid more than once. The invoice is not made
	# twice — but the settlement is tried again, because the common way to end
	# up with an unpaid invoice here is the invoice landing and the Payment
	# Entry failing, and `_safe` makes that failure quiet.
	already = invoice_id and frappe.db.get_value(
		"Sales Invoice", {"po_no": invoice_id, "docstatus": ("<", 2)}, "name"
	)
	if already:
		settle(already, stripe_invoice)
		return None

	customer = ensure_customer(subscription.tenant)
	if not customer:
		return None

	amount = flt(stripe_invoice.get("amount_paid") or 0) / 100
	if amount <= 0:
		return None

	item = ensure_item(DEFAULT_ITEM, "OneSpace platform subscription")

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"company": _company(),
			"po_no": invoice_id,
			"currency": (stripe_invoice.get("currency") or "usd").upper(),
			"posting_date": getdate(),
			"items": [
				{
					"item_code": item,
					"qty": 1,
					"rate": amount,
					"description": f"{subscription.plan} — {subscription.interval}",
				}
			],
			"remarks": f"Stripe invoice {invoice_id} for tenant {subscription.tenant}",
		}
	)
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	settle(invoice.name, stripe_invoice)
	return invoice.name


@_safe
def record_storage_pack(tenant: str, gb: int, checkout: dict):
	return _record_one_off(
		tenant, checkout, STORAGE_ITEM, "OneSpace additional storage", f"{int(gb)} GB storage"
	)


@_safe
def record_credit_pack(tenant: str, credits: float, checkout: dict):
	return _record_one_off(
		tenant, checkout, CREDIT_ITEM, "OneSpace credit pack", f"{int(credits)} credits"
	)


def _record_one_off(tenant: str, checkout: dict, item_code: str, item_description: str,
                    line_description: str):
	"""Sales Invoice for a one-off purchase.

	Keyed on the Stripe session id, because Stripe can deliver the same
	checkout.session.completed more than once and a duplicate invoice is worse
	than none.
	"""
	session_id = checkout.get("id")

	already = session_id and frappe.db.get_value(
		"Sales Invoice", {"po_no": session_id, "docstatus": ("<", 2)}, "name"
	)
	if already:
		settle(already, checkout)
		return None

	customer = ensure_customer(tenant)
	if not customer:
		return None

	amount = flt(checkout.get("amount_total") or 0) / 100
	if amount <= 0:
		return None

	item = ensure_item(item_code, item_description)

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"company": _company(),
			"po_no": session_id,
			"currency": (checkout.get("currency") or "usd").upper(),
			"posting_date": getdate(),
			"items": [
				{
					"item_code": item,
					"qty": 1,
					"rate": amount,
					"description": line_description,
				}
			],
			"remarks": f"{item_description} for tenant {tenant}",
		}
	)
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	settle(invoice.name, checkout)
	return invoice.name


# --------------------------------------------------------------------------- #
# The cash
#
# Everything below turns a submitted Sales Invoice into a settled one. It is
# separate from raising the invoice on purpose: the invoice is the record of
# what was sold and must land whatever happens, while the cash half needs two
# accounts an operator names and a round trip to Stripe to learn the fee. When
# the second fails, the first is still right.
# --------------------------------------------------------------------------- #

def _settings():
	return frappe.get_single("OneSpace Control Settings") or frappe._dict()


def _company() -> str | None:
	"""Whose books these are.

	Named in settings because a control site may carry more than one company —
	the one we sell through is not necessarily the one that came first.
	"""
	named = _settings().get("books_company")
	if named:
		return named

	default = frappe.db.get_default("company")
	if default:
		return default

	if not frappe.db.exists("DocType", "Company"):
		# A control site before ERPNext is installed. Bring-up reaches here —
		# the readiness list is answered on a site that has the control app and
		# not yet the books — and an exception would take the screen asking the
		# question with it.
		return None

	return frappe.db.get_value("Company", {}, "name")


def _id(value) -> str:
	"""Stripe sends a related object as an id, or expanded. Either is an id."""
	if isinstance(value, dict):
		return str(value.get("id") or "")
	return str(value or "")


def _charge_of(paid: dict) -> str:
	"""The charge behind a payment, whatever the event called it.

	An invoice names its charge; a checkout session names a payment intent,
	which names the charge. Stripe has also renamed `charge` to `latest_charge`
	across API versions, and an account pinned to an older one still sends the
	first — so both are read rather than the current one guessed at.
	"""
	for key in ("charge", "latest_charge"):
		found = _id(paid.get(key))
		if found:
			return found

	intent = _id(paid.get("payment_intent"))
	if not intent:
		return ""

	return _id((stripe_client.get_payment_intent(intent) or {}).get("latest_charge"))


def _fee(paid: dict, currency: str) -> float:
	"""What Stripe kept, in the invoice's currency — or zero if we cannot say.

	Zero does not mean there was no fee. It means book the gross: the clearing
	account then drifts from the payout by the fees, which is a visible number
	an operator can chase, where a guessed fee is a wrong one nobody can see.
	"""
	try:
		charge = _charge_of(paid)
		if not charge:
			return 0.0

		transaction = (stripe_client.get_charge(charge) or {}).get("balance_transaction")
	except Exception:
		# Two extra round trips to Stripe, at the moment a webhook is being
		# answered. Stripe being unreachable must cost the fee line and not the
		# settlement — an unpaid invoice is the failure that hides.
		frappe.log_error(
			title="Could not read the Stripe fee", message=frappe.get_traceback()
		)
		return 0.0

	if not isinstance(transaction, dict):
		return 0.0

	# The fee is denominated in the *settlement* currency, which is the Stripe
	# account's and not necessarily the charge's. Converting it would be
	# inventing an exchange rate.
	if (transaction.get("currency") or "").upper() != (currency or "").upper():
		return 0.0

	return flt(transaction.get("fee") or 0) / 100


@_safe
def settle(invoice_name: str, paid: dict) -> str | None:
	"""Pay off a Sales Invoice from the Stripe clearing account.

	Safe to call twice, because Stripe delivers the same event twice: an
	invoice with nothing outstanding has already been settled.
	"""
	settings = _settings()
	clearing = settings.get("stripe_clearing_account")
	if not clearing:
		# Nothing is posted until an operator names the account — the console's
		# readiness list says as much. A guessed cash account is a wrong entry
		# in a submitted ledger, which is far more work to undo than to make.
		return None

	invoice = frappe.db.get_value(
		"Sales Invoice",
		invoice_name,
		["customer", "company", "currency", "outstanding_amount", "docstatus"],
		as_dict=True,
	)
	if not invoice or int(invoice.get("docstatus") or 0) != 1:
		return None

	gross = flt(invoice.get("outstanding_amount"))
	if gross <= 0:
		return None

	entry = frappe.get_doc(
		{
			"doctype": "Payment Entry",
			"payment_type": "Receive",
			"company": invoice.get("company"),
			"posting_date": getdate(),
			"party_type": "Customer",
			"party": invoice.get("customer"),
			# `paid_from` is the customer's receivable account, which ERPNext
			# fills in from the party. `paid_to` is the one we have to name.
			"paid_to": clearing,
			"reference_no": _id(paid) or invoice_name,
			"reference_date": getdate(),
			"references": [
				{
					"reference_doctype": "Sales Invoice",
					"reference_name": invoice_name,
					"allocated_amount": gross,
				}
			],
		}
	)

	fee = _fee_for(settings, paid, invoice, gross)
	# The customer paid the gross and the clearing account received the net.
	# The difference is the deduction, and ERPNext requires the three to agree.
	entry.paid_amount = entry.received_amount = gross - fee
	if fee:
		entry.append(
			"deductions",
			{
				"account": settings.get("stripe_fee_account"),
				"cost_center": frappe.db.get_value(
					"Company", invoice.get("company"), "cost_center"
				),
				"amount": fee,
				"description": "Stripe processing fee",
			},
		)

	entry.insert(ignore_permissions=True)
	entry.submit()
	return entry.name


def _fee_for(settings, paid: dict, invoice, gross: float) -> float:
	"""The fee, or zero, with every reason it might be zero in one place."""
	if not settings.get("stripe_fee_account"):
		return 0.0

	# A deduction is posted in the company's currency. Where the sale was not,
	# booking the fee would mean converting it at a rate nobody chose.
	company_currency = frappe.db.get_value(
		"Company", invoice.get("company"), "default_currency"
	)
	if company_currency and company_currency != invoice.get("currency"):
		return 0.0

	fee = _fee(paid, invoice.get("currency"))

	# A fee at or above the sale is not a fee — it is a settlement currency we
	# read wrongly, or a refund. Book the gross and leave the drift visible.
	return fee if 0 < fee < gross else 0.0
