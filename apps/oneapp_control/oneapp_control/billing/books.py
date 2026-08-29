"""Mirror billing into ERPNext.

The control plane runs ERPNext so our own revenue is bookkept in the same system
we sell, rather than in a bespoke table that has to be reconciled by hand at
year end. Tenants are Customers; payments become Sales Invoices.

Everything here is best-effort and must never break a webhook: if bookkeeping
fails, the customer has still paid and their credits must still land. Failures
are logged for an operator, not raised.
"""

import frappe
from frappe.utils import flt, getdate

DEFAULT_ITEM = "OneApp Subscription"
CREDIT_ITEM = "OneApp Credits"


def _safe(fn):
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

	# Stripe can deliver invoice.paid more than once.
	if invoice_id and frappe.db.exists(
		"Sales Invoice", {"po_no": invoice_id, "docstatus": ("<", 2)}
	):
		return None

	customer = ensure_customer(subscription.tenant)
	if not customer:
		return None

	amount = flt(stripe_invoice.get("amount_paid") or 0) / 100
	if amount <= 0:
		return None

	item = ensure_item(DEFAULT_ITEM, "OneApp platform subscription")

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
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
	return invoice.name


@_safe
def record_credit_pack(tenant: str, credits: float, checkout: dict):
	"""Create a Sales Invoice for a one-off credit purchase."""
	session_id = checkout.get("id")

	if session_id and frappe.db.exists(
		"Sales Invoice", {"po_no": session_id, "docstatus": ("<", 2)}
	):
		return None

	customer = ensure_customer(tenant)
	if not customer:
		return None

	amount = flt(checkout.get("amount_total") or 0) / 100
	if amount <= 0:
		return None

	item = ensure_item(CREDIT_ITEM, "OneApp credit pack")

	invoice = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"po_no": session_id,
			"currency": (checkout.get("currency") or "usd").upper(),
			"posting_date": getdate(),
			"items": [
				{
					"item_code": item,
					"qty": 1,
					"rate": amount,
					"description": f"{int(credits)} credits",
				}
			],
			"remarks": f"Credit pack for tenant {tenant}",
		}
	)
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	return invoice.name
