"""Freeze existing subscriptions on the terms they are already getting.

Quotas used to be read live from the Plan doctype, so every subscription sold
before this was implicitly on whatever the plan said today. Capturing the plan
as it stands now is therefore not a guess — it is exactly what these customers
have right now, and the only change is that a later edit to the plan can no
longer take it away.

Subscriptions that already carry captured terms are left alone, so re-running
this is safe.
"""

import frappe

from oneapp_control.billing import quotas


def execute():
	if not frappe.db.table_exists("Subscription"):
		return

	names = frappe.get_all(
		"Subscription",
		filters={"terms_captured_on": ("is", "not set")},
		pluck="name",
	)

	for name in names:
		subscription = frappe.get_doc("Subscription", name)
		if not subscription.plan:
			continue
		quotas.capture(subscription)

	if names:
		frappe.db.commit()
