"""Write the lifecycle windows onto an existing control plane.

`bench migrate` creates new fields on a Single and leaves them empty. It does not
apply the JSON default — that only fires when a *document* is inserted, and a
Single that already exists never is. So on an existing control plane all six of
these arrive as zero.

For the five day counts that is survivable: `lifecycle.policy` floors anything
below its minimum and reads the default instead, precisely so a mistyped window
cannot suspend the fleet. But the settings page would show six zeros, and a
number an operator reads as the policy while a different number is in force is
worse than either.

`auto_purge_enabled` has no floor and cannot have one — a checkbox has no
"unset". Zero reads as a deliberate off, so without this every existing control
plane would quietly keep every cold copy forever while its settings page showed
a box nobody ever unticked.

Only writes where the field is empty, so an operator who has already set a
window keeps it.
"""

import frappe

DEFAULTS = {
	"dunning_grace_days": 7,
	"suspended_days": 14,
	"cold_retention_days": 60,
	"purge_warning_days": 7,
	"overage_grace_days": 7,
	"auto_purge_enabled": 1,
}


def execute():
	settings = frappe.get_single("OneSpace Control Settings")

	changed = {}
	for field, value in DEFAULTS.items():
		if not settings.get(field):
			changed[field] = value

	if not changed:
		return

	frappe.db.set_value(
		"OneSpace Control Settings", "OneSpace Control Settings", changed,
		update_modified=False,
	)
	frappe.db.commit()
