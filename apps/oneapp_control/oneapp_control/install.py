"""Post-install setup for the control plane."""

import frappe


def after_install():
	create_default_settings()
	seed_apps()
	setup_console()


def after_migrate():
	"""Re-seed the operator console from code on every migration.

	The console's shape lives in `entitlements/operator.py` rather than in a
	fixture somebody edits, so "change the console" is an edit and a migrate.
	Running it here rather than only at install means an existing control plane
	picks up a new screen without anybody remembering to.
	"""
	setup_console()


def setup_console():
	"""The two Spaces this site provides, and the DocPerms they depend on.

	Only where `oneapp` is installed — the console is a Space, and a Space with
	nothing to render it is a row nobody reads. A control plane running only
	this app is a perfectly good control plane; it just has no console yet.
	"""
	try:
		import oneapp  # noqa: F401
	except ImportError:
		return

	from oneapp_control.entitlements import account, operator

	operator.seed()
	account.seed()
	# One call for both: `sync_permissions` reconciles every local space's
	# grants at once, and the account Space deliberately grants nothing.
	operator.sync_permissions()
	frappe.db.commit()


def create_default_settings():
	settings = frappe.get_single("OneSpace Control Settings")
	if not settings.tenant_domain:
		settings.tenant_domain = "4dl.app"
	if not settings.press_api_url:
		settings.press_api_url = "https://cloud.frappe.io"
	settings.save(ignore_permissions=True)
	frappe.db.commit()


# A reference entitlement, not a product.
#
# Nobody has decided to build a books app. This row exists so the entitlement
# pipeline has something running through it end to end — registry row, sync
# payload, role created with desk_access off, DocPerms written from the
# manifest, launcher rendering, reconciliation on removal. With an empty
# catalogue every one of those paths is dead code on a fresh control plane, and
# a break in any of them would go unnoticed until the first real app.
#
# **Restricted**, deliberately. General availability would put it in every
# customer's launcher, where it points at a "Not built yet" screen and grants
# write on eight ERPNext doctypes over the REST API — a promise of software that
# does not exist, made to someone paying. An operator grants it to a workspace
# to exercise the pipeline (the console → a workspace → Apps), and nobody else sees
# it.
#
# Its doctype list is deliberately small: the transitive set ERPNext actually
# touches on submit is not something that can be enumerated by reading, and
# guessing it produces a workspace that works in a demo and breaks on the fifth
# invoice. It grows from running the real flows. See DECISIONS §8.
SEED_APPS = [
	{
		"space_code": "books",
		"space_label": "Books",
		"module": "Books",
		"role_name": "OneSpace Books",
		"icon": "lucide-book-open",
		"sort_order": 10,
		"availability": "Restricted",
		"description": (
			"Reference entitlement — no interface yet. Grant it to exercise the "
			"pipeline, not to give a customer accounting."
		),
		"doctypes": [
			("Customer", "Write", 0),
			("Supplier", "Write", 0),
			("Item", "Write", 0),
			("Sales Invoice", "Manage", 0),
			("Purchase Invoice", "Manage", 0),
			("Payment Entry", "Manage", 0),
			("Address", "Write", 0),
			("Contact", "Write", 0),
		],
	},
]


def seed_apps():
	for spec in SEED_APPS:
		if frappe.db.exists("OneSpace Space", spec["space_code"]):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "OneSpace Space",
				"is_active": 1,
				# Restricted unless a spec says otherwise. Reaching every
				# customer's launcher should be something a seed opts into, not
				# something it gets by forgetting to say.
				"availability": "Restricted",
				**{k: v for k, v in spec.items() if k != "doctypes"},
			}
		)
		for document_type, access, if_owner in spec["doctypes"]:
			doc.append(
				"doctypes",
				{"document_type": document_type, "access": access, "if_owner": if_owner},
			)
		doc.insert(ignore_permissions=True)
