"""Creating a workspace, suspending it, and what it is entitled to.

Everything below exists because the desk is not part of this product
(docs/ONEADMIN.md, No desk). A record an operator can only reach through /app is a record
only someone who knows Frappe can reach, and the whole point of the operator
console is that running this does not require that.
"""

import frappe
from oneapp_control.entitlements import registry
from oneapp_control.provisioning import runner
from oneapp_control.utils.slug import is_available
from .guard import _require_manager


@frappe.whitelist()
def check_slug(slug: str) -> dict:
	"""Whether a slug is free, asked as somebody types it."""
	return {"slug": slug, "available": is_available(slug)}


@frappe.whitelist()
def create_tenant(tenant_slug: str, tenant_name: str, owner_email: str,
                  plan: str | None = None, provision: bool = True) -> dict:
	"""Create a workspace. Provisioning is a separate step, so this one is cheap."""
	_require_manager()

	tenant = frappe.get_doc(
		{
			"doctype": "Tenant",
			"tenant_slug": tenant_slug,
			"tenant_name": tenant_name,
			"owner_email": owner_email,
			"plan": plan,
			"status": "Draft",
		}
	).insert()

	job = None
	if provision:
		job = runner.provision_tenant(tenant.name)

	return {"tenant": tenant.name, "job": job.name if job else None}


@frappe.whitelist()
def provision(tenant: str) -> str:
	"""Start provisioning a workspace that has been created."""
	_require_manager()
	return runner.provision_tenant(tenant).name


@frappe.whitelist()
def suspend(tenant: str, reason: str = "Suspended by operator") -> str:
	"""Suspend a workspace. Its people keep their data and lose their access."""
	_require_manager()
	return runner.enqueue(
		tenant, "Suspend Site", {"reason": reason}, idempotency_key=f"suspend:{tenant}:{frappe.generate_hash(length=8)}"
	).name


@frappe.whitelist()
def resume(tenant: str) -> str:
	"""Lift a suspension, and let the workspace back in."""
	_require_manager()
	return runner.enqueue(
		tenant, "Resume Site", idempotency_key=f"resume:{tenant}:{frappe.generate_hash(length=8)}"
	).name


@frappe.whitelist()
def add_custom_domain(tenant: str, domain: str) -> str:
	"""Point a customer's own domain at their site."""
	_require_manager()
	return runner.enqueue(
		tenant, "Add Domain", {"domain": domain}, idempotency_key=f"domain:{tenant}:{domain}"
	).name


@frappe.whitelist()
def tenant_apps(tenant: str) -> list:
	"""Which spaces a workspace is entitled to, and which it is not."""
	_require_manager()
	return registry.spaces_for_tenant(tenant)


@frappe.whitelist(methods=["GET"])
def tenant_app_access(tenant: str) -> list:
	"""Every app, and whether this workspace has it.

	`spaces_for_tenant` answers the launcher's question — what to render — so it
	returns only what the tenant already has. An operator deciding what to grant
	needs the other half: the restricted apps this workspace does *not* have are
	the only ones there is anything to do about, and they are invisible in a list
	of what it does.
	"""
	_require_manager()
	entitled = {
		row.app
		for row in frappe.get_all(
			"Space Entitlement", filters={"tenant": tenant, "enabled": 1}, fields=["app"]
		)
	}

	apps = frappe.get_all(
		"OneSpace Space",
		filters={"is_active": 1},
		fields=["name as space_code", "space_label", "module", "availability", "icon",
		        "sort_order", "description"],
		order_by="sort_order asc, space_label asc",
	)
	for app in apps:
		app["entitled"] = (
			app.availability != "Restricted" or app.space_code in entitled
		)
	return apps


@frappe.whitelist()
def grant_app(tenant: str, space_code: str, note: str | None = None) -> str:
	"""Entitle a workspace to a space."""
	_require_manager()
	return registry.grant(tenant, space_code, note)


@frappe.whitelist()
def revoke_app(tenant: str, space_code: str):
	"""Take a space away from a workspace."""
	_require_manager()
	registry.revoke(tenant, space_code)
	return {"ok": True}


@frappe.whitelist(methods=["GET"])
def signups(limit: int = 50) -> list:
	"""Account requests, newest first.

	A signup that took payment and then failed to provision is invisible
	otherwise: the customer has been charged, there is no tenant, and nothing
	surfaces it.
	"""
	_require_manager()
	return frappe.get_all(
		"Account Request",
		fields=[
			"name", "email", "workspace_name", "requested_slug", "status", "plan",
			"interval", "region", "tenant", "paid_on", "completed_on",
			"failure_reason", "creation",
		],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)


@frappe.whitelist(methods=["GET"])
def standby_pool() -> list:
	"""Warm sites, by shard.

	The pool is what makes signup instant, so an empty one is a slow signup and
	a stuck one is a wasted site. Neither shows anywhere else.
	"""
	_require_manager()
	rows = frappe.get_all(
		"Standby Site",
		fields=["name", "press_site", "status", "shard", "claimed_by", "claimed_on",
		        "created_on", "last_error"],
		order_by="creation desc",
		limit=200,
	)
	targets = {
		s.name: s.standby_target
		for s in frappe.get_all("Shard", fields=["name", "standby_target"])
	}
	for row in rows:
		row["target"] = targets.get(row.shard)
	return rows
