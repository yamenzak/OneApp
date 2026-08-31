"""Give existing plans and subscriptions a backup schedule.

`bench migrate` adds a field and leaves it empty. The JSON default only fires
when a document is *inserted*, and neither an existing Plan nor an existing
Subscription ever is again — so without this every plan sold before backups
existed reads `backups_per_day = 0`, which the tenant site correctly interprets
as "this plan does not include backups" and takes none. Every existing customer
would silently have no copies of their workspace.

**Why this is not the grandfathering it looks like.** `billing/quotas.py` exists
to stop a plan edit moving an existing subscriber, and it is deliberate about
never rewriting a captured term. That rule protects somebody from having
something *taken away*. A term that did not exist when they bought has nothing to
protect: zero here is an absence, not a promise, and reading it as one hands the
customer strictly less than the plan they are on. So a captured value that is
empty is filled in; one that has been set is left exactly alone.

Idempotent. Re-running writes nothing.
"""

import frappe

DEFAULTS = {"backups_per_day": 1, "backup_retention_days": 7}


def execute():
	_fill("Plan", DEFAULTS)

	# The plan's numbers, not the constants, so a plan an operator has already
	# tuned hands its subscribers the same thing a new sale would.
	for name in frappe.get_all("Subscription", pluck="name"):
		subscription = frappe.db.get_value(
			"Subscription", name, ("plan", *DEFAULTS), as_dict=True
		)
		missing = {
			field: _plan_value(subscription.plan, field)
			for field in DEFAULTS
			if not subscription.get(field)
		}
		if missing:
			frappe.db.set_value("Subscription", name, missing, update_modified=False)

	frappe.db.commit()


def _fill(doctype: str, defaults: dict) -> int:
	touched = 0
	for name in frappe.get_all(doctype, pluck="name"):
		row = frappe.db.get_value(doctype, name, tuple(defaults), as_dict=True)
		missing = {f: v for f, v in defaults.items() if not row.get(f)}
		if missing:
			frappe.db.set_value(doctype, name, missing, update_modified=False)
			touched += 1
	return touched


def _plan_value(plan: str | None, field: str):
	if not plan:
		return DEFAULTS[field]
	return frappe.db.get_value("Plan", plan, field) or DEFAULTS[field]
