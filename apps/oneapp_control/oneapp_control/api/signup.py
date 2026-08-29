"""Public signup.

Card first: nothing is provisioned until Stripe confirms payment. That removes
the abuse surface a free trial would open — a fresh ERPNext site per throwaway
email is expensive — at the cost of conversion. Trials can come later by
allowing an Account Request to reach Paid without a charge.

These endpoints are the only ones on the control plane reachable by a guest, so
each one assumes hostile input.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from oneapp_control.utils.slug import is_available, validate_slug

# Cheap protection against someone walking the namespace or scripting signups.
RATE_LIMIT_PER_HOUR = 20


def _client_ip() -> str:
	return frappe.local.request_ip or "unknown"


def _rate_limit(action: str, limit: int = RATE_LIMIT_PER_HOUR):
	key = f"oneapp_signup:{action}:{_client_ip()}:{now_datetime().strftime('%Y%m%d%H')}"
	count = int(frappe.cache().get_value(key) or 0)
	if count >= limit:
		frappe.throw(_("Too many attempts. Please try again shortly."), frappe.ValidationError)
	frappe.cache().set_value(key, count + 1, expires_in_sec=3700)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def check_slug(slug: str) -> dict:
	"""Availability for the signup form."""
	_rate_limit("check_slug", limit=120)
	return {"slug": slug, "available": is_available(slug)}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def regions() -> list[dict]:
	"""Regions with capacity right now.

	Filtered rather than listed in full: offering a region that cannot take a
	tenant turns a clear choice into a failure after payment.
	"""
	from oneapp_control.control_plane.doctype.shard.shard import regions_with_capacity

	return regions_with_capacity()


@frappe.whitelist(allow_guest=True, methods=["GET"])
def signup_open() -> dict:
	"""Whether self-service can run at all.

	Missing plans, Stripe or capacity are all operator problems; showing a
	signup form that cannot complete is worse than saying so plainly.
	"""
	from oneapp_control.api.setup import checks

	items = {c["key"]: c["ok"] for c in checks()}
	from oneapp_control.control_plane.doctype.shard.shard import regions_with_capacity

	reasons = []
	if not items.get("press_credentials") or not items.get("control_plane_url"):
		reasons.append("provisioning")
	if not items.get("plans") or not items.get("stripe_gateway") or not items.get("stripe_webhook"):
		reasons.append("billing")
	if not regions_with_capacity():
		reasons.append("capacity")

	return {"open": not reasons, "blocked_on": reasons}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def plans() -> list[dict]:
	"""Plans as a prospect sees them.

	Only what belongs on a pricing page — never the Stripe ids or the press site
	plan, which are ours.
	"""
	rows = frappe.get_all(
		"Plan",
		filters={"is_active": 1},
		fields=[
			"name as code", "plan_name", "audience", "currency",
			"price_monthly", "price_yearly", "storage_gb", "max_users",
			"monthly_credit_grant", "description",
		],
		order_by="sort_order asc",
	)
	return rows


@frappe.whitelist(allow_guest=True, methods=["POST"])
def start(email: str, workspace_name: str, slug: str, plan: str,
          region: str, storage_jurisdiction: str = "Global",
          interval: str = "Monthly", source: str | None = None) -> dict:
	"""Create an Account Request and return a Stripe Checkout URL.

	Nothing is provisioned here. The tenant only comes into existence once
	Stripe confirms the payment.
	"""
	_rate_limit("start")

	if not signup_open()["open"]:
		frappe.throw(_("Signups are temporarily closed. Please try again shortly."))

	slug = validate_slug(slug)
	email = (email or "").strip().lower()

	if not frappe.utils.validate_email_address(email):
		frappe.throw(_("Enter a valid email address."))
	if not workspace_name.strip():
		frappe.throw(_("Enter a workspace name."))
	if not is_available(slug):
		frappe.throw(_("'{0}' is not available.").format(slug))

	plan_doc = frappe.get_doc("Plan", plan)
	if not plan_doc.is_active:
		frappe.throw(_("That plan is not available."))

	# Offered regions are filtered by capacity, so anything else is either stale
	# or fabricated.
	from oneapp_control.control_plane.doctype.shard.shard import regions_with_capacity

	if region not in {r["code"] for r in regions_with_capacity()}:
		frappe.throw(_("That region is not available right now."))

	if storage_jurisdiction not in ("Global", "EU"):
		frappe.throw(_("Unknown storage jurisdiction."))

	# Resume rather than duplicate: someone who abandoned checkout and came back
	# should not end up with two requests, or lose their slug to themselves.
	existing = frappe.db.get_value(
		"Account Request",
		{"email": email, "requested_slug": slug, "status": "Pending Payment"},
		"name",
	)
	request = (
		frappe.get_doc("Account Request", existing)
		if existing
		else frappe.get_doc(
			{
				"doctype": "Account Request",
				"email": email,
				"workspace_name": workspace_name.strip(),
				"requested_slug": slug,
				"plan": plan,
				"interval": interval,
				"region": region,
				"storage_jurisdiction": storage_jurisdiction,
				"status": "Pending Payment",
				"source": source,
				"ip_address": _client_ip(),
			}
		).insert(ignore_permissions=True)
	)

	from oneapp_control.billing import checkout

	session = checkout.start_signup(request)
	request.db_set("stripe_checkout_session", session["id"])
	frappe.db.commit()

	return {"request": request.name, "url": session["url"]}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def status(request: str) -> dict:
	"""Progress for the post-checkout waiting screen.

	Deliberately sparse — this is reachable by anyone holding the id, so it says
	how far along things are and nothing else.
	"""
	doc = frappe.db.get_value(
		"Account Request",
		request,
		["status", "workspace_name", "requested_slug", "tenant"],
		as_dict=True,
	)
	if not doc:
		frappe.throw(_("Unknown request."), frappe.DoesNotExistError)

	site = None
	tenant_status = None
	if doc.tenant:
		site, tenant_status = frappe.db.get_value(
			"Tenant", doc.tenant, ["site_name", "status"]
		)

	return {
		"status": doc.status,
		"workspace_name": doc.workspace_name,
		"ready": doc.status == "Completed" and tenant_status == "Active",
		"site_url": f"https://{site}" if site and tenant_status == "Active" else None,
	}
