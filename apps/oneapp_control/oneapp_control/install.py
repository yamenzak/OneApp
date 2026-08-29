"""Post-install setup for the control plane."""

import frappe


def after_install():
	create_default_settings()
	seed_apps()


def create_default_settings():
	settings = frappe.get_single("OneApp Control Settings")
	if not settings.tenant_domain:
		settings.tenant_domain = "4dl.app"
	if not settings.press_api_url:
		settings.press_api_url = "https://cloud.frappe.io"
	settings.save(ignore_permissions=True)
	frappe.db.commit()


# The first app, so a fresh control plane has something to provision rather than
# an empty catalogue. Its doctype list is deliberately small: the transitive set
# ERPNext actually touches on submit is not something that can be enumerated by
# reading, and guessing it produces a workspace that works in a demo and breaks
# on the fifth invoice. It grows from running the real flows. See DECISIONS §8.
SEED_APPS = [
	{
		"app_code": "books",
		"app_label": "Books",
		"module": "Books",
		"role_name": "OneApp Books",
		"icon": "lucide-book-open",
		"route": "/books",
		"sort_order": 10,
		"description": "Invoicing, payments and the ledger behind them.",
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
		if frappe.db.exists("OneApp App", spec["app_code"]):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "OneApp App",
				"is_active": 1,
				"availability": "General",
				**{k: v for k, v in spec.items() if k != "doctypes"},
			}
		)
		for document_type, access, if_owner in spec["doctypes"]:
			doc.append(
				"doctypes",
				{"document_type": document_type, "access": access, "if_owner": if_owner},
			)
		doc.insert(ignore_permissions=True)
