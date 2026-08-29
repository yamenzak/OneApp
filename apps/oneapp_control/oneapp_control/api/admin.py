"""Operator-facing endpoints. Session-authenticated, System Manager only."""

import frappe
from frappe import _

from oneapp_control.control_plane.doctype.shard.shard import capacity_report
from oneapp_control.entitlements import registry
from oneapp_control.provisioning import runner
from oneapp_control.utils.slug import is_available


def _require_manager():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)


@frappe.whitelist()
def check_slug(slug: str) -> dict:
	return {"slug": slug, "available": is_available(slug)}


@frappe.whitelist()
def create_tenant(tenant_slug: str, tenant_name: str, owner_email: str,
                  plan: str | None = None, provision: bool = True) -> dict:
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
	_require_manager()
	return runner.provision_tenant(tenant).name


@frappe.whitelist()
def suspend(tenant: str, reason: str = "Suspended by operator") -> str:
	_require_manager()
	return runner.enqueue(
		tenant, "Suspend Site", {"reason": reason}, idempotency_key=f"suspend:{tenant}:{frappe.generate_hash(length=8)}"
	).name


@frappe.whitelist()
def resume(tenant: str) -> str:
	_require_manager()
	return runner.enqueue(
		tenant, "Resume Site", idempotency_key=f"resume:{tenant}:{frappe.generate_hash(length=8)}"
	).name


@frappe.whitelist()
def add_custom_domain(tenant: str, domain: str) -> str:
	_require_manager()
	return runner.enqueue(
		tenant, "Add Domain", {"domain": domain}, idempotency_key=f"domain:{tenant}:{domain}"
	).name


@frappe.whitelist()
def shards() -> list:
	_require_manager()
	return capacity_report()


@frappe.whitelist()
def tenant_apps(tenant: str) -> list:
	_require_manager()
	return registry.apps_for_tenant(tenant)


@frappe.whitelist()
def grant_app(tenant: str, app_code: str, note: str | None = None) -> str:
	_require_manager()
	return registry.grant(tenant, app_code, note)


@frappe.whitelist()
def revoke_app(tenant: str, app_code: str):
	_require_manager()
	registry.revoke(tenant, app_code)
	return {"ok": True}
