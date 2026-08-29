"""Stripe webhook endpoint.

Stripe is the source of truth for billing state; this reflects it into
Subscription, credits and ERPNext. Three properties matter more than anything
else here:

1. **Signature verification.** The endpoint is public, so an unverified payload
   is an attacker granting themselves credits.
2. **Idempotency.** Stripe retries on any non-2xx and can deliver duplicates.
   Every event id is recorded, so replay is a no-op rather than a second grant.
3. **Ordering tolerance.** Events can arrive out of order. State transitions are
   written to be safe regardless of arrival sequence.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

SIGNATURE_TOLERANCE = 300

HANDLED = {
	"checkout.session.completed",
	"customer.subscription.created",
	"customer.subscription.updated",
	"customer.subscription.deleted",
	"invoice.paid",
	"invoice.payment_failed",
}

STRIPE_STATUS_MAP = {
	"trialing": "Trialing",
	"active": "Active",
	"past_due": "Past Due",
	"unpaid": "Past Due",
	"canceled": "Canceled",
	"incomplete": "Incomplete",
	"incomplete_expired": "Canceled",
}


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

@frappe.whitelist(allow_guest=True, methods=["POST"])
def stripe():
	raw = frappe.request.get_data(as_text=True) or ""
	signature = frappe.request.headers.get("Stripe-Signature")

	verify_signature(raw, signature)

	event = json.loads(raw)
	event_id = event.get("id")
	event_type = event.get("type")

	if not event_id:
		frappe.throw(_("Malformed event."))

	# Replay guard. Recorded before handling, so a crash mid-handler still leaves
	# a row we can inspect rather than silently reprocessing later.
	if frappe.db.exists("Stripe Webhook Event", event_id):
		return {"ok": True, "duplicate": True}

	record = frappe.get_doc(
		{
			"doctype": "Stripe Webhook Event",
			"event_id": event_id,
			"event_type": event_type,
			"status": "Received",
			"payload": json.dumps(event)[:100000],
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()

	if event_type not in HANDLED:
		record.db_set("status", "Ignored")
		return {"ok": True, "ignored": event_type}

	try:
		handler = HANDLERS[event_type]
		handler(event["data"]["object"], record)
		record.db_set("status", "Processed")
		record.db_set("processed_on", now_datetime())
	except Exception as e:
		record.db_set("status", "Failed")
		record.db_set("error", frappe.get_traceback()[:5000])
		frappe.log_error(
			title=f"Stripe webhook {event_type} failed", message=frappe.get_traceback()
		)
		# 200 anyway: Stripe would retry forever on a bug, and the row above is
		# our record to replay from deliberately once fixed.
		return {"ok": False, "error": str(e)[:200]}

	return {"ok": True}


def verify_signature(payload: str, header: str | None):
	secret = frappe.get_single("OneApp Control Settings").get_password(
		"stripe_webhook_secret", raise_exception=False
	)
	if not secret:
		frappe.throw(_("Stripe webhook secret is not configured."), frappe.PermissionError)
	if not header:
		frappe.throw(_("Missing Stripe signature."), frappe.PermissionError)

	timestamp, signatures = None, []
	for part in header.split(","):
		key, _sep, value = part.partition("=")
		if key.strip() == "t":
			timestamp = value.strip()
		elif key.strip() == "v1":
			signatures.append(value.strip())

	if not (timestamp and signatures):
		frappe.throw(_("Malformed Stripe signature."), frappe.PermissionError)

	try:
		age = abs(time.time() - int(timestamp))
	except ValueError:
		frappe.throw(_("Malformed Stripe signature."), frappe.PermissionError)

	if age > SIGNATURE_TOLERANCE:
		frappe.throw(_("Stripe signature has expired."), frappe.PermissionError)

	expected = hmac.new(
		secret.encode("utf-8"),
		f"{timestamp}.{payload}".encode("utf-8"),
		hashlib.sha256,
	).hexdigest()

	if not any(hmac.compare_digest(expected, s) for s in signatures):
		frappe.throw(_("Invalid Stripe signature."), frappe.PermissionError)


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #

def _tenant_from(obj: dict) -> str | None:
	meta = obj.get("metadata") or {}
	return meta.get("tenant") or obj.get("client_reference_id")


def handle_checkout_completed(obj: dict, record):
	meta = obj.get("metadata") or {}

	# A signup has no tenant yet — the Account Request is the only handle.
	if meta.get("kind") == "signup" or meta.get("account_request"):
		return handle_signup_paid(obj, record)

	tenant = _tenant_from(obj)
	if not tenant:
		return

	record.db_set("tenant", tenant)
	meta = obj.get("metadata") or {}

	if meta.get("kind") == "storage_pack":
		if obj.get("payment_status") != "paid":
			return
		grant_storage_pack(tenant, int(meta.get("storage_gb") or 0), obj)
		return

	if meta.get("kind") == "credit_pack":
		# Only credit a pack once payment actually succeeded.
		if obj.get("payment_status") != "paid":
			return
		grant_credit_pack(tenant, float(meta.get("credits") or 0), obj)
		return

	# Subscription checkouts are finalised by customer.subscription.* events,
	# which carry the authoritative period boundaries.
	if obj.get("subscription"):
		ensure_subscription(
			tenant=tenant,
			stripe_subscription_id=obj["subscription"],
			stripe_customer_id=obj.get("customer"),
			plan=meta.get("plan"),
			interval=meta.get("interval") or "Monthly",
		)


def handle_signup_paid(obj: dict, record):
	"""Payment cleared for a signup: create the account and start provisioning.

	Runs inside the webhook's idempotency guard, and additionally refuses to act
	twice on the same Account Request — Stripe can deliver checkout.session.completed
	more than once, and the cost of getting that wrong is two sites and two
	subscriptions for one customer.
	"""
	from oneapp_control.provisioning import signup as signup_flow

	name = (obj.get("metadata") or {}).get("account_request") or obj.get("client_reference_id")
	if not name or not frappe.db.exists("Account Request", name):
		return

	request = frappe.get_doc("Account Request", name)
	record.db_set("tenant", request.tenant)

	if request.status not in ("Pending Payment", "Failed"):
		# Already handled.
		return

	if obj.get("payment_status") not in ("paid", "no_payment_required"):
		return

	request.db_set("stripe_customer_id", obj.get("customer"))
	request.db_set("stripe_subscription_id", obj.get("subscription"))
	request.db_set("paid_on", now_datetime())
	request.db_set("status", "Paid")

	signup_flow.fulfil(request.name)


def handle_subscription_change(obj: dict, record):
	tenant = _tenant_from(obj)
	subscription = _find_subscription(obj.get("id"), tenant)

	if not subscription:
		if not tenant:
			return
		subscription = ensure_subscription(
			tenant=tenant,
			stripe_subscription_id=obj.get("id"),
			stripe_customer_id=obj.get("customer"),
			plan=(obj.get("metadata") or {}).get("plan"),
		)

	record.db_set("tenant", subscription.tenant)
	record.db_set("subscription", subscription.name)

	status = STRIPE_STATUS_MAP.get(obj.get("status"), "Incomplete")
	subscription.db_set("status", status)
	subscription.db_set("cancel_at_period_end", 1 if obj.get("cancel_at_period_end") else 0)

	if obj.get("current_period_start"):
		subscription.db_set(
			"current_period_start", _ts(obj["current_period_start"])
		)
	if obj.get("current_period_end"):
		subscription.db_set("current_period_end", _ts(obj["current_period_end"]))

	apply_subscription_status(subscription)


def handle_invoice_paid(obj: dict, record):
	subscription_id = obj.get("subscription")
	if not subscription_id:
		return

	subscription = _find_subscription(subscription_id, _tenant_from(obj))
	if not subscription:
		return

	record.db_set("tenant", subscription.tenant)
	record.db_set("subscription", subscription.name)
	subscription.db_set("last_invoice_id", obj.get("id"))
	subscription.db_set("status", "Active")

	period_end = _period_end_from_invoice(obj) or subscription.current_period_end
	grant_period_credits(subscription, period_end)
	apply_subscription_status(subscription)

	from oneapp_control.billing import books

	books.record_invoice(subscription, obj)


def handle_invoice_failed(obj: dict, record):
	subscription_id = obj.get("subscription")
	if not subscription_id:
		return

	subscription = _find_subscription(subscription_id, _tenant_from(obj))
	if not subscription:
		return

	record.db_set("tenant", subscription.tenant)
	record.db_set("subscription", subscription.name)
	subscription.db_set("status", "Past Due")

	# Stripe runs its own retry schedule. We only suspend once it gives up, which
	# arrives as customer.subscription.updated -> unpaid/canceled.
	apply_subscription_status(subscription)


HANDLERS = {
	"checkout.session.completed": handle_checkout_completed,
	"customer.subscription.created": handle_subscription_change,
	"customer.subscription.updated": handle_subscription_change,
	"customer.subscription.deleted": handle_subscription_change,
	"invoice.paid": handle_invoice_paid,
	"invoice.payment_failed": handle_invoice_failed,
}


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #

def _ts(epoch):
	"""Stripe sends UTC epoch seconds; Frappe stores naive local datetimes."""
	return datetime.fromtimestamp(int(epoch), tz=timezone.utc).replace(tzinfo=None)


def _period_end_from_invoice(invoice: dict):
	for line in (invoice.get("lines") or {}).get("data") or []:
		end = (line.get("period") or {}).get("end")
		if end:
			return _ts(end)
	return None


def _find_subscription(stripe_subscription_id, tenant=None):
	if stripe_subscription_id:
		name = frappe.db.get_value(
			"Subscription", {"stripe_subscription_id": stripe_subscription_id}, "name"
		)
		if name:
			return frappe.get_doc("Subscription", name)

	if tenant:
		name = frappe.db.get_value(
			"Subscription", {"tenant": tenant}, "name", order_by="creation desc"
		)
		if name:
			return frappe.get_doc("Subscription", name)

	return None


def ensure_subscription(tenant, stripe_subscription_id, stripe_customer_id=None,
                        plan=None, interval="Monthly"):
	existing = _find_subscription(stripe_subscription_id)
	if existing:
		return existing

	plan = plan or frappe.db.get_value("Tenant", tenant, "plan")
	if not plan:
		frappe.throw(_("Cannot create a subscription for {0} without a plan.").format(tenant))

	doc = frappe.get_doc(
		{
			"doctype": "Subscription",
			"tenant": tenant,
			"plan": plan,
			"interval": interval,
			"status": "Incomplete",
			"stripe_subscription_id": stripe_subscription_id,
			"stripe_customer_id": stripe_customer_id,
		}
	).insert(ignore_permissions=True)

	frappe.db.set_value("Tenant", tenant, {"subscription": doc.name, "plan": plan})
	return doc


def grant_period_credits(subscription, period_end):
	"""Post this period's non-rollover grant, exactly once.

	`last_grant_period_end` is the guard: a replayed or duplicated invoice.paid
	for the same period must not grant twice.
	"""
	if not period_end:
		return

	if subscription.last_grant_period_end and get_datetime(
		subscription.last_grant_period_end
	) >= get_datetime(period_end):
		return

	credits = frappe.db.get_value("Plan", subscription.plan, "monthly_credit_grant") or 0
	if credits <= 0:
		subscription.db_set("last_grant_period_end", period_end)
		return

	from oneapp_control.credits import ledger

	ledger.grant_for_period(
		tenant=subscription.tenant,
		credits=float(credits),
		period_end=get_datetime(period_end).date(),
		source_name=subscription.name,
	)
	subscription.db_set("last_grant_period_end", period_end)


def apply_subscription_status(subscription):
	"""Translate billing state into tenant lifecycle.

	Suspension is deliberately conservative: Past Due does nothing, because
	Stripe is still retrying and cutting a paying customer off mid-dunning is
	worse than carrying them for a few more days.
	"""
	from oneapp_control.provisioning import runner

	tenant = frappe.get_doc("Tenant", subscription.tenant)

	if subscription.status in ("Active", "Trialing"):
		if tenant.status == "Suspended":
			runner.enqueue(
				tenant.name,
				"Resume Site",
				idempotency_key=f"resume:{tenant.name}:{subscription.name}",
			)
		return

	if subscription.status == "Canceled" and tenant.status == "Active":
		runner.enqueue(
			tenant.name,
			"Suspend Site",
			{"reason": "Subscription canceled"},
			idempotency_key=f"suspend:{tenant.name}:{subscription.name}",
		)


def grant_storage_pack(tenant: str, gb: int, checkout: dict):
	"""Add-on storage is permanent — it is not a grant that expires."""
	if gb <= 0:
		return

	current = frappe.db.get_value("Tenant", tenant, "extra_storage_gb") or 0
	frappe.db.set_value("Tenant", tenant, "extra_storage_gb", int(current) + gb)

	from oneapp_control.billing import books

	books.record_storage_pack(tenant, gb, checkout)


def grant_credit_pack(tenant: str, credits: float, checkout: dict):
	"""Purchased credits roll over — no expiry. That is what makes packs worth buying."""
	if credits <= 0:
		return

	from oneapp_control.credits import ledger

	ledger.post_entry(
		tenant=tenant,
		entry_type="Purchase",
		credits=credits,
		expires_on=None,
		remarks=f"Credit pack via Stripe checkout {checkout.get('id')}",
	)

	from oneapp_control.billing import books

	books.record_credit_pack(tenant, credits, checkout)
