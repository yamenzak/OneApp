"""What kind of site this is.

`oneapp` runs on two kinds of site now: a customer's workspace, and the control
plane — where it is installed for its shell and its Space runtime rather than
for anything a tenant needs. Most of the app behaves identically on both, and
the handful of places that must not are gated here rather than each inventing
its own test.

Declared rather than derived. Asking "is `oneapp_control` installed?" would
make a safety property a consequence of an app list, and its failure mode is
silence: install an app for an unrelated reason and a customer's attachments
quietly stop going to R2. A site says what it is:

    # site_config.json
    "oneapp_role": "control"

Absent means tenant, because every site that exists today is one and a
migration that requires touching every site_config is a migration that will be
half-done forever.

This is a different question from `control_client.is_provisioned()`, which asks
whether a tenant has been handed its identity yet. A site can be a tenant and
not yet provisioned — that is an orphan, and worth telling apart from a site
that was never meant to have a tenant identity at all.
"""

import frappe

TENANT = "tenant"
CONTROL = "control"


def role() -> str:
	value = (frappe.conf.get("oneapp_role") or "").strip().lower()
	return value if value in (TENANT, CONTROL) else TENANT


def is_control() -> bool:
	"""The control plane, running the shell for its own operators and
	customers rather than for a tenant."""
	return role() == CONTROL


def is_tenant() -> bool:
	return not is_control()
