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
		fields=["name as app_code", "app_label", "module", "role_name", "icon",
			"sort_order", "description"],
	)

	restricted = frappe.db.sql(
		"""
		SELECT a.name AS app_code, a.app_label, a.module, a.role_name, a.icon,
		       a.sort_order, a.description
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

	# The screens each app puts in front of a customer. Sent with the app rather
	# than fetched per app: OneSpace renders its navigation from this the moment
	# a workspace opens, and a second round trip for a list of four labels is a
	# spinner where a sidebar should be.
	for app in apps:
		app["views"] = views_for(app["app_code"])

	return apps


def views_for(app_code: str) -> list[dict]:
	return frappe.get_all(
		"OneApp App View",
		filters={"parent": app_code, "parenttype": "OneApp App"},
		fields=["view", "label", "icon", "document_type", "fields", "component",
		        "filters", "order_by"],
		order_by="idx asc",
	)


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

# Held by everyone in the workspace, the owner included. It grants nothing —
# the app roles do that — and exists to mark an account as ours.
#
# Without a marker there is no safe way to tell a removed member from a user the
# site created for its own reasons. Reconciling on "holds one of our app roles"
# looks equivalent and is not: a member of a workspace with no apps entitled yet
# holds none of them, so removing that member disabled nobody and they kept
# their sign-in.
MEMBER_ROLE = "OneApp Workspace Member"


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
