"""Nobody loses an app to a rule change.

A General space used to reach every launcher whether or not anybody wanted it:
`spaces_for_tenant` returned all of them plus the entitled Restricted ones. It
now returns exactly what an entitlement enables, which is what makes a
marketplace possible — a space everybody already had was a space with no button
to press.

Applied to what exists, that rule would empty every workspace. So every tenant
is switched on for every active General space, as a row an operator can see and
a customer can now turn off. Which is also the honest record of what was true a
minute before this ran.

Guarded on the row not existing rather than on its value: a workspace an
operator had already revoked a General space from — possible only by hand, but
possible — keeps that decision.
"""

import frappe


def execute():
	general = frappe.get_all(
		"OneSpace Space",
		filters={"is_active": 1, "availability": "General"},
		pluck="name",
	)
	if not general:
		return

	made = 0
	for tenant in frappe.get_all("Tenant", pluck="name"):
		for code in general:
			if frappe.db.exists("Space Entitlement", {"tenant": tenant, "app": code}):
				continue
			frappe.get_doc({
				"doctype": "Space Entitlement",
				"tenant": tenant,
				"app": code,
				"enabled": 1,
				"offered": 1,
				"note": "Carried over when spaces stopped being switched on for everybody.",
			}).insert(ignore_permissions=True)
			made += 1

	frappe.db.commit()
	print(f"switched on {made} entitlements across {len(general)} general spaces")
