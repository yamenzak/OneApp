"""Which apps a tenant may see.

Two independent axes, deliberately:

* **Plan** decides quotas — storage, seats, credits. Never which apps.
* **Entitlement** decides apps. That is what makes a single-tenant bespoke
  solution possible without inventing a plan for one customer.

An app marked General is available to everyone. An app marked Restricted appears
only where an explicit App Entitlement exists. A Restricted app that nobody has
been entitled to is simply invisible, not an error.
"""

import frappe


def apps_for_tenant(tenant: str) -> list[dict]:
	"""The manifest the SPA launcher renders."""
	general = frappe.get_all(
		"OneApp App",
		filters={"is_active": 1, "availability": "General"},
		fields=["name as app_code", "app_label", "module", "icon", "route", "sort_order"],
	)

	restricted = frappe.db.sql(
		"""
		SELECT a.name AS app_code, a.app_label, a.module, a.icon, a.route, a.sort_order
		FROM `tabOneApp App` a
		INNER JOIN `tabApp Entitlement` e ON e.app = a.name
		WHERE a.is_active = 1
		  AND a.availability = 'Restricted'
		  AND e.tenant = %(tenant)s
		  AND e.enabled = 1
		""",
		{"tenant": tenant},
		as_dict=True,
	)

	apps = general + restricted
	apps.sort(key=lambda a: (a.get("sort_order") or 0, a.get("app_label") or ""))
	return apps


def entitled_modules(tenant: str) -> list[str]:
	"""Module names the tenant may reach.

	This is the list the tenant site enforces against — hiding a launcher tile is
	a UX affordance, the module check is the boundary.
	"""
	return [a["module"] for a in apps_for_tenant(tenant) if a.get("module")]


def grant(tenant: str, app_code: str, note: str | None = None):
	if frappe.db.exists("App Entitlement", {"tenant": tenant, "app": app_code}):
		name = frappe.db.get_value(
			"App Entitlement", {"tenant": tenant, "app": app_code}, "name"
		)
		frappe.db.set_value("App Entitlement", name, "enabled", 1)
		return name

	return frappe.get_doc(
		{
			"doctype": "App Entitlement",
			"tenant": tenant,
			"app": app_code,
			"enabled": 1,
			"note": note,
		}
	).insert(ignore_permissions=True).name


def revoke(tenant: str, app_code: str):
	name = frappe.db.get_value(
		"App Entitlement", {"tenant": tenant, "app": app_code}, "name"
	)
	if name:
		# Kept as a disabled row rather than deleted, so the history of who had
		# access to what survives.
		frappe.db.set_value("App Entitlement", name, "enabled", 0)
