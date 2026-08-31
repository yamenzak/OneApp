"""The windows the ladder runs on, and the floors it will not go under.

Every number here is operator-editable, because the day a customer's card fails
over a long weekend is the day you want the grace period to be a field rather
than a deploy. What is *not* editable is the set of floors below: a window typed
as 0 by accident would otherwise mean "suspend everyone today".
"""

import frappe

DEFAULTS = {
	"dunning_grace_days": 7,
	"suspended_days": 14,
	"cold_retention_days": 60,
	"purge_warning_days": 7,
	"overage_grace_days": 7,
}

# A window shorter than this is treated as unset and the default is used
# instead. Zero is not a policy anybody types on purpose, and the cost of
# reading it literally is a fleet-wide suspension.
FLOORS = {
	"dunning_grace_days": 1,
	"suspended_days": 1,
	# Deliberately the longest floor. Below a week there is no realistic chance
	# for somebody who has been away to notice their workspace is about to be
	# destroyed and stop it.
	"cold_retention_days": 7,
	"purge_warning_days": 1,
	"overage_grace_days": 1,
}


def windows() -> dict:
	"""Every window, floored and defaulted. One read, so a sweep is consistent."""
	settings = frappe.get_single("OneSpace Control Settings")

	found = {}
	for field, default in DEFAULTS.items():
		value = int(settings.get(field) or 0)
		found[field] = value if value >= FLOORS[field] else default

	found["auto_purge_enabled"] = bool(settings.get("auto_purge_enabled"))
	return found


def window(name: str) -> int:
	return windows()[name]
