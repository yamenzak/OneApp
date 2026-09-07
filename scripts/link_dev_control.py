"""Link the dev tenant site to the dev control plane.

Not part of `dev.sh seed`, and deliberately: a linked site *pulls* its manifest,
its quotas and its members from the control plane every fifteen minutes, which
would put the fixture's own cached copy in a race with a second source of truth.
The fixture writes that cache directly for exactly that reason.

What the link is for is the handful of surfaces that have no other way to be
looked at — People, Roles, Domain and the marketplace all relay through
`oneapp_core/account.py` to `oneapp_control.api.tenant.workspace_admin`, and on
an unlinked site every one of them honestly says it cannot reach the account.

Run it on the **control** site; it writes both halves:

    scripts/dev.sh run scripts/link_dev_control.py

Undo it by deleting the two keys from the tenant's `site_config.json`.

The secret is a constant and is not a secret. This runs on a dev bench where
every site_config is plaintext beside it; a real tenant's is 32 bytes of
urandom written by provisioning and never by anything here.
"""

import json
from pathlib import Path

import frappe

TENANT = "zzdev"
SECRET = "dev-hmac-not-a-secret-" + "0" * 42
CONTROL_URL = "http://control.localhost:8000"
SITE_CONFIG = Path("/home/frappe/bench1/sites/space.localhost/site_config.json")


def tenant():
	"""A Tenant the dev space site can prove it is."""
	if frappe.db.exists("Tenant", TENANT):
		doc = frappe.get_doc("Tenant", TENANT)
	else:
		plan = frappe.get_all("Plan", pluck="name", limit=1)
		doc = frappe.get_doc({
			"doctype": "Tenant",
			"tenant_name": "Dev Workspace",
			"tenant_slug": TENANT,
			"owner_email": "dev@zzmock.test",
			# Administrator on both sites, which is who the browser suite signs
			# in as — so the relay's `as_user` matches this without a fixture
			# person who exists on one site and not the other.
			"owner_user": "Administrator",
			**({"plan": plan[0]} if plan else {}),
		})
		doc.name = TENANT
		doc.insert(ignore_permissions=True)

	doc.db_set("status", "Active", update_modified=False)
	doc.db_set("site_name", "space.localhost", update_modified=False)
	doc.set("hmac_secret", SECRET)
	doc.save(ignore_permissions=True)
	return doc


def offer_something(name: str):
	"""One Restricted space on the shelf, so the marketplace has a card.

	Books, because it is the Restricted space this bench can actually carry —
	RUA declares `hrms` and the dev Shard does not say it has it.
	"""
	from oneapp_control.entitlements import registry

	if not frappe.db.exists("OneSpace Space", "books"):
		print("no books space to offer")
		return
	registry.revoke(name, "books")
	registry.offer(name, "books", note="Seeded by scripts/link_dev_control.py")
	print("offered: books")


def write_site_config():
	held = json.loads(SITE_CONFIG.read_text())
	held["oneapp_tenant"] = TENANT
	held["oneapp_control_url"] = CONTROL_URL
	held["oneapp_hmac_secret"] = SECRET
	SITE_CONFIG.write_text(json.dumps(held, indent=1) + "\n")
	print(f"wrote {SITE_CONFIG}")


if __name__ == "__main__":
	doc = tenant()
	offer_something(doc.name)
	frappe.db.commit()
	write_site_config()
	print(f"linked {doc.name} -> {CONTROL_URL}. Restart the tenant server.")
