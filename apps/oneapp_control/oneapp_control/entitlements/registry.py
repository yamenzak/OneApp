"""Which apps a tenant may see.

Two independent axes, deliberately:

* **Plan** decides quotas — storage, seats, credits. Never which apps.
* **Entitlement** decides apps. That is what makes a single-tenant bespoke
  solution possible without inventing a plan for one customer.

An app marked General is available to everyone. An app marked Restricted appears
only where an explicit Space Entitlement exists. A Restricted app that nobody has
been entitled to is simply invisible, not an error.
"""

import frappe


# What describes a space to a site. One list, two readers — the tenant sync and
# the local provider — so the two cannot drift into describing different things.
SPACE_FIELDS = (
	"name as space_code", "space_label", "module", "role_name", "icon",
	"logo", "sort_order", "description",
)


def spaces_for_tenant(tenant: str) -> list[dict]:
	"""The manifest OneSpace renders: every space this workspace may open."""
	general = frappe.get_all(
		"OneSpace Space",
		filters={"is_active": 1, "availability": "General"},
		fields=list(SPACE_FIELDS),
	)

	restricted = frappe.db.sql(
		"""
		SELECT a.name AS space_code, a.space_label, a.module, a.role_name, a.icon,
		       a.logo, a.sort_order, a.description
		FROM `tabOneSpace Space` a
		INNER JOIN `tabSpace Entitlement` e ON e.app = a.name
		WHERE a.is_active = 1
		  AND a.availability = 'Restricted'
		  AND e.tenant = %(tenant)s
		  AND e.enabled = 1
		""",
		{"tenant": tenant},
		as_dict=True,
	)

	spaces = general + restricted
	spaces.sort(key=lambda s: (s.get("sort_order") or 0, s.get("space_label") or ""))

	# The screens each space puts in front of a customer — its navigation. Sent
	# with the space rather than fetched per space: OneSpace renders its sidebar
	# from this the moment a workspace opens, and a second round trip for a list
	# of four labels is a spinner where a sidebar should be.
	for space in spaces:
		space["screens"] = screens_for(space["space_code"])

	return spaces


# Every field a Space Screen carries, sent verbatim. Listed rather than `["*"]`
# so a field added here is a deliberate act — and read off the doctype in
# `tests/test_owner_and_manifest.py`, because the failure mode of a forgotten
# one is silent: `status_field` was stored, edited in the console, and never
# sent, so no screen anywhere ever showed a status badge and nothing said why.
SCREEN_FIELDS = (
	"screen", "label", "icon", "document_type", "fields", "component",
	"filters", "order_by", "view_types", "view_settings", "status_field",
	"hide_new",
)


def screens_for(space_code: str) -> list[dict]:
	return frappe.get_all(
		"OneSpace Space Screen",
		filters={"parent": space_code, "parenttype": "OneSpace Space"},
		fields=list(SCREEN_FIELDS),
		order_by="idx asc",
	)


def local_spaces() -> list[dict]:
	"""Every space this site offers itself, for `oneapp` running on it.

	The control plane holds the space registry and has no control plane to ask,
	so where a tenant syncs, this reads the same rows in process. Registered
	through `onespace_space_providers` in hooks, which is `oneapp`'s one seam
	for it.

	No entitlement join, unlike `spaces_for_tenant`: there is no tenant here.
	Who sees which space is decided by role — `visible_spaces` filters on
	`role_name`, so an operator space and a customer's account space separate
	cleanly on one site — and by `_space`, which refuses a space code whose
	role the caller does not hold.
	"""
	spaces = frappe.get_all(
		"OneSpace Space",
		filters={"is_active": 1},
		fields=list(SPACE_FIELDS),
	)
	spaces.sort(key=lambda s: (s.get("sort_order") or 0, s.get("space_label") or ""))
	for space in spaces:
		space["screens"] = screens_for(space["space_code"])
	return spaces


def forget_spaces(doc=None, method=None) -> None:
	"""Drop OneSpace's cached view of this site's spaces.

	Only meaningful where `oneapp` is installed alongside this app — the
	control site. Elsewhere the import fails and there is nothing to forget,
	which is not an error: a tenant's cache is invalidated by its own sync.
	"""
	try:
		from oneapp.oneapp_core import sync
	except ImportError:
		return
	sync.invalidate()


def entitled_modules(tenant: str) -> list[str]:
	return [s["module"] for s in spaces_for_tenant(tenant) if s.get("module")]


def entitled_roles(tenant: str) -> list[str]:
	"""Roles the tenant site should hold.

	Enforcement is native Frappe permissions: each app's doctypes carry
	permissions for its role, and the tenant site adds or removes that role from
	its users on every sync. That covers desk, REST, reports and any future
	surface, which a bespoke permission hook would not.
	"""
	return [a["role_name"] for a in spaces_for_tenant(tenant) if a.get("role_name")]


# The role the workspace owner holds. Deliberately not System Manager: that would
# let them read site_config, which carries the signing secret this site uses to
# talk to us — enough to forge its own usage reports and credit commits. What
# they actually need (inviting users, seats, custom roles) is whitelisted methods
# we run elevated, not a Frappe admin role. See DECISIONS §8.
OWNER_ROLE = "OneSpace Workspace Owner"

# Held by everyone in the workspace, the owner included. It grants nothing —
# the app roles do that — and exists to mark an account as ours.
#
# Without a marker there is no safe way to tell a removed member from a user the
# site created for its own reasons. Reconciling on "holds one of our app roles"
# looks equivalent and is not: a member of a workspace with no apps entitled yet
# holds none of them, so removing that member disabled nobody and they kept
# their sign-in.
MEMBER_ROLE = "OneSpace Workspace Member"


def permission_manifest(tenant: str) -> list[dict]:
	"""Every role the tenant site should define, and what each may touch.

	One row per (role, doctype). The tenant site writes DocPerms from this, so a
	doctype absent here is reachable by nobody — an allowlist by construction
	rather than by remembering to exclude things.
	"""
	manifest = []
	for app in spaces_for_tenant(tenant):
		role = app.get("role_name")
		if not role:
			continue
		rows = frappe.get_all(
			"OneSpace Space Doctype",
			filters={"parent": app["space_code"], "parenttype": "OneSpace Space"},
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


def grant(tenant: str, space_code: str, note: str | None = None):
	if frappe.db.exists("Space Entitlement", {"tenant": tenant, "app": space_code}):
		name = frappe.db.get_value(
			"Space Entitlement", {"tenant": tenant, "app": space_code}, "name"
		)
		frappe.db.set_value("Space Entitlement", name, "enabled", 1)
		return name

	return frappe.get_doc(
		{
			"doctype": "Space Entitlement",
			"tenant": tenant,
			"app": space_code,
			"enabled": 1,
			"note": note,
		}
	).insert(ignore_permissions=True).name


def revoke(tenant: str, space_code: str):
	name = frappe.db.get_value(
		"Space Entitlement", {"tenant": tenant, "app": space_code}, "name"
	)
	if name:
		# Kept as a disabled row rather than deleted, so the history of who had
		# access to what survives.
		frappe.db.set_value("Space Entitlement", name, "enabled", 0)
