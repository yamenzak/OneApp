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
		fields=["name as app_code", "app_label", "module", "role_name", "icon", "route",
			"sort_order"],
	)

	restricted = frappe.db.sql(
		"""
		SELECT a.name AS app_code, a.app_label, a.module, a.role_name, a.icon, a.route,
		       a.sort_order
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
	return [a["module"] for a in apps_for_tenant(tenant) if a.get("module")]


def entitled_roles(tenant: str) -> list[str]:
	"""Roles the tenant site should hold.

	Enforcement is native Frappe permissions: each app's doctypes carry
	permissions for its role, and the tenant site adds or removes that role from
	its users on every sync. That covers desk, REST, reports and any future
	surface, which a bespoke permission hook would not.
	"""
	return [a["role_name"] for a in apps_for_tenant(tenant) if a.get("role_name")]


# The role the workspace owner holds. Deliberately not System Manager: that would
# let them read site_config, which carries the signing secret this site uses to
# talk to us — enough to forge its own usage reports and credit commits. What
# they actually need (inviting users, seats, custom roles) is whitelisted methods
# we run elevated, not a Frappe admin role. See DECISIONS §8.
OWNER_ROLE = "OneApp Workspace Owner"


def permission_manifest(tenant: str) -> list[dict]:
	"""Every role the tenant site should define, and what each may touch.

	One row per (role, doctype). The tenant site writes DocPerms from this, so a
	doctype absent here is reachable by nobody — an allowlist by construction
	rather than by remembering to exclude things.
	"""
	manifest = []
	for app in apps_for_tenant(tenant):
		role = app.get("role_name")
		if not role:
			continue
		rows = frappe.get_all(
			"OneApp App Doctype",
			filters={"parent": app["app_code"], "parenttype": "OneApp App"},
			fields=["document_type", "access", "if_owner"],
		)
		for row in rows:
			manifest.append(
				{
					"role": role,
					"doctype": row["document_type"],
					"access": row["access"],
					"if_owner": bool(row["if_owner"]),
				}
			)
	return manifest


def allowed_doctypes(tenant: str) -> list[str]:
	"""What a customer's own role may reference.

	The same list the DocPerms come from. User, Role, DocType and the rest are
	out because they appear in no manifest, not because someone remembered to
	name them.
	"""
	return sorted({row["doctype"] for row in permission_manifest(tenant)})


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
