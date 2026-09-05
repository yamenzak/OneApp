"""Write down what every existing site already carries.

Until now a site got its shard's whole app list, so `Tenant.site_apps` is empty
on every workspace provisioned before this — and empty does not mean "nothing
installed", it means "nobody wrote it down". Left that way, the first grant on
an old workspace would compute a gap against nothing and queue an install of
ERPNext onto a site that has had ERPNext all along.

Press is not asked, deliberately. The shard's list is exactly what
`create_site` passed, so it is the right answer for every site this patch can
see, and asking Frappe Cloud once per tenant during a migration is minutes of
network for a fact we already hold.

Only where the site exists and the field is empty. A tenant provisioned after
this shipped has its own list, and rewriting it with the bench's would undo the
whole point.
"""

import frappe

from oneapp_control.provisioning.steps import site_apps


def execute():
	rows = frappe.get_all(
		"Tenant",
		filters={"press_site": ["is", "set"], "site_apps": ["in", ("", None)]},
		fields=["name", "shard"],
	)

	carried = {}
	for row in rows:
		if not row.shard:
			continue
		if row.shard not in carried:
			carried[row.shard] = site_apps(frappe.get_doc("Shard", row.shard))
		frappe.db.set_value(
			"Tenant", row.name, "site_apps", ",".join(carried[row.shard]),
			update_modified=False,
		)

	frappe.db.commit()
