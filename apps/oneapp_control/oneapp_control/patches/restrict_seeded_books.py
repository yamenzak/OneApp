"""Take the seeded Books entitlement out of every customer's launcher.

It was seeded General with a description that reads like a product, which put an
app with no interface into every workspace's launcher and granted write on eight
ERPNext doctypes over the REST API. Nobody had decided to build a books app; the
row exists so the entitlement pipeline has something running through it end to
end (see install.py).

Two corrections, each guarded on the value still being the one that was seeded.
A control plane where an operator changed either has made a decision, and a
patch that overrides one is worse than the state it corrects.
"""

import frappe

SEEDED_DESCRIPTION = "Invoicing, payments and the ledger behind them."

HONEST_DESCRIPTION = (
	"Reference entitlement — no interface yet. Grant it to exercise the "
	"pipeline, not to give a customer accounting."
)


def execute():
	if not frappe.db.exists("OneApp App", "books"):
		return

	app = frappe.get_doc("OneApp App", "books")

	if app.description == SEEDED_DESCRIPTION:
		app.db_set("description", HONEST_DESCRIPTION)

	if app.availability != "General" or not app.is_active:
		return

	# Anyone who already had it through General availability keeps it, as an
	# entitlement an operator can now see and revoke — rather than losing their
	# apps to a migration they did not ask for.
	for tenant in frappe.get_all("Tenant", pluck="name"):
		if frappe.db.exists("App Entitlement", {"tenant": tenant, "app": "books"}):
			continue
		frappe.get_doc(
			{
				"doctype": "App Entitlement",
				"tenant": tenant,
				"app": "books",
				"enabled": 1,
				"note": "Carried over when Books stopped being generally available.",
			}
		).insert(ignore_permissions=True)

	app.db_set("availability", "Restricted")
	frappe.db.commit()
