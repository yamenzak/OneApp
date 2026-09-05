"""What a tenant owes, what they were granted, and the webhooks behind it."""

import frappe
import json
from frappe import _
from .guard import _require_manager


@frappe.whitelist(methods=["GET"])
def webhook_events(limit: int = 50, status: str | None = None) -> list:
	"""Stripe events we have seen, and what became of them.

	The webhook answers 200 even when a handler raises, because Stripe would
	otherwise retry a bug forever — the row is the record to replay from once it
	is fixed. That only works if the rows are visible.
	"""
	_require_manager()
	filters = {"status": status} if status else None
	return frappe.get_all(
		"Stripe Webhook Event",
		filters=filters,
		fields=["name", "event_id", "event_type", "status", "tenant", "subscription",
		        "processed_on", "error", "creation"],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)


@frappe.whitelist(methods=["POST"])
def replay_webhook(event: str) -> dict:
	"""Run a stored Stripe event through its handler again.

	The deliberate half of answering 200 on failure. Idempotent by the same
	arguments the handlers already rely on — a replayed invoice does not grant
	twice, and a replayed plan change applies once.
	"""
	_require_manager()
	from oneapp_control.billing import webhooks

	record = frappe.get_doc("Stripe Webhook Event", event)
	if record.event_type not in webhooks.HANDLERS:
		frappe.throw(_("{0} has no handler.").format(record.event_type))

	payload = json.loads(record.payload or "{}")
	obj = (payload.get("data") or {}).get("object")
	if not obj:
		frappe.throw(_("This event was recorded without a payload to replay."))

	try:
		webhooks.HANDLERS[record.event_type](obj, record)
		record.db_set("status", "Processed")
		record.db_set("processed_on", frappe.utils.now_datetime())
		record.db_set("error", None)
		return {"ok": True}
	except Exception as e:
		record.db_set("status", "Failed")
		record.db_set("error", frappe.get_traceback()[:5000])
		frappe.throw(_("Replay failed: {0}").format(str(e)[:200]))


@frappe.whitelist(methods=["GET"])
def tenant_billing(tenant: str) -> dict:
	"""What a workspace is on, and on whose terms.

	The operator's screen of the thing the customer sees on their plan page — plus
	the one fact the customer's page cannot show them: whether the terms they
	hold still match the plan as it stands.
	"""
	_require_manager()
	from oneapp_control.billing import quotas

	doc = frappe.get_doc("Tenant", tenant)
	subscription = (
		frappe.get_doc("Subscription", doc.subscription).as_dict()
		if doc.subscription
		else None
	)

	in_force = quotas.for_tenant(doc)
	current = (
		frappe.db.get_value("Plan", doc.plan, quotas.TERMS, as_dict=True) if doc.plan else None
	) or {}

	return {
		"plan": doc.plan,
		"subscription": subscription,
		"terms": in_force,
		"plan_terms": current,
		# Named rather than left to be spotted: an operator asking "why does this
		# workspace have 50GB when the plan says 20" is asking this question.
		"grandfathered": [
			field for field in quotas.TERMS if (in_force.get(field) or 0) != (current.get(field) or 0)
		],
		"credits": _credit_summary(tenant),
	}


def _credit_summary(tenant: str) -> dict:
	from oneapp_control.credits import ledger

	return {
		"balance": ledger.balance(tenant),
		"available": ledger.available(tenant),
		"history": frappe.get_all(
			"Credit Ledger Entry",
			filters={"tenant": tenant},
			fields=["creation", "entry_type", "credits", "expires_on", "remarks"],
			order_by="creation desc",
			limit=50,
		),
	}


@frappe.whitelist(methods=["POST"])
def grant_credits(tenant: str, credits: float, reason: str) -> dict:
	"""Put credits on a workspace by hand.

	Nothing else in the system can. Credits arrive from a paid invoice or a
	purchased pack, and both are Stripe telling us something happened — so a
	goodwill credit, a migration allowance or a demo top-up had no path at all
	and would have meant opening the desk, which this product does not do
	(docs/ONEADMIN.md, No desk).

	A reason is required and lands on the ledger row. The ledger is append-only
	and an entry with no explanation is one nobody can audit six months later;
	this is the one entry type a person creates, so it is the one that most needs
	saying why.

	Posted as `Adjustment` rather than `Grant`: a Grant is what a plan gives and
	expires at the period end, and this should not quietly evaporate. It never
	expires, so it is spent after everything else — `open_grants` orders
	never-expiring last — which is the right order for something given away.
	"""
	_require_manager()
	from oneapp_control.credits import ledger

	amount = float(credits or 0)
	if not amount:
		frappe.throw(_("Nothing to grant."))
	if not (reason or "").strip():
		frappe.throw(_("Say why. It goes on the ledger and somebody will read it."))

	entry = ledger.post_entry(
		tenant=tenant,
		entry_type="Adjustment",
		credits=amount,
		expires_on=None,
		source_doctype="User",
		source_name=frappe.session.user,
		remarks=f"{reason.strip()} — by {frappe.session.user}",
	)
	return {"entry": entry.name if hasattr(entry, "name") else None, "credits": amount}


@frappe.whitelist(methods=["POST"])
def adopt_plan_terms(tenant: str) -> dict:
	"""Move a workspace onto its plan's terms as they stand now.

	The deliberate half of grandfathering. Quotas are captured when a
	subscription is sold precisely so a plan edit cannot move an existing
	customer; this is how an operator moves one on purpose — handing someone the
	newer, larger plan without making them re-subscribe.
	"""
	_require_manager()
	from oneapp_control.billing import quotas

	subscription = frappe.db.get_value("Tenant", tenant, "subscription")
	if not subscription:
		frappe.throw(_("This workspace has no subscription to move."))

	return quotas.adopt_current_terms(subscription)


@frappe.whitelist(methods=["POST"])
def set_tenant_plan(tenant: str, plan: str, interval: str = "Monthly") -> dict:
	"""Change a workspace's plan on the operator's authority.

	Same path the customer's own switch takes, so the fit check, the proration
	and the Frappe Cloud site plan all behave identically — an operator moving
	someone should not be a second, subtly different implementation.
	"""
	_require_manager()
	from oneapp_control.billing import checkout

	return checkout.change_plan(tenant, plan, interval)
