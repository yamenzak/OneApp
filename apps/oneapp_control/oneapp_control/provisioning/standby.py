"""Warm sites, built ahead of demand.

Creating an ERPNext site takes minutes. Someone who has just entered card
details should not watch a spinner for that long, so sites are built in advance
under throwaway names and claimed at signup.

The customer never sees the underlying name. In Per-tenant domain mode they
reach their workspace on `<slug>.4dl.app`, which is attached at claim time — so
the Frappe Cloud name is an implementation detail. That also means claiming is
only as fast as certificate issuance; on a Wildcard shard, where no certificate
is needed per tenant, a claim is effectively instant.

Press has its own standby mechanism for product trials, but that is press-side
and unavailable to us as a customer, so this is ours.
"""

import secrets

import frappe
from frappe import _
from frappe.utils import now_datetime

# A pool is only useful if the sites in it are actually finished.
CLAIMABLE = "Ready"


def pool_status() -> list[dict]:
	"""How deep each shard's pool is against its target."""
	rows = []
	for shard in frappe.get_all(
		"Shard",
		filters={"status": "Active", "standby_target": (">", 0)},
		fields=["name", "standby_target"],
	):
		ready = frappe.db.count(
			"Standby Site", {"shard": shard.name, "status": CLAIMABLE}
		)
		building = frappe.db.count(
			"Standby Site", {"shard": shard.name, "status": "Creating"}
		)
		rows.append(
			{
				"shard": shard.name,
				"target": shard.standby_target,
				"ready": ready,
				"building": building,
				"deficit": max(shard.standby_target - ready - building, 0),
			}
		)
	return rows


def ensure_depth(shard: str, limit: int = 1) -> list[str]:
	"""Bring one shard back to its target, now.

	Called the moment a site is claimed rather than waiting for the scheduled
	sweep, because the next signup is the one that would otherwise wait for a
	full site build.
	"""
	target = frappe.db.get_value("Shard", shard, "standby_target") or 0
	if not target:
		return []

	have = frappe.db.count(
		"Standby Site", {"shard": shard, "status": ("in", (CLAIMABLE, "Creating"))}
	)
	created = []
	for _i in range(min(max(target - have, 0), limit)):
		created.append(create_standby(shard))
	return created


def top_up(limit_per_run: int = 2):
	"""Scheduled. Build toward each shard's target.

	Deliberately slow: a couple of sites per run rather than filling a deficit at
	once, so a mistakenly large target cannot flood the server with site builds.
	"""
	created = []

	for row in pool_status():
		for _i in range(min(row["deficit"], limit_per_run)):
			try:
				created.append(create_standby(row["shard"]))
			except Exception:
				frappe.log_error(
					title=f"Standby creation failed on {row['shard']}",
					message=frappe.get_traceback(),
				)
				break

	if created:
		frappe.db.commit()
	return created


def create_standby(shard: str) -> str:
	"""Start building one warm site."""
	from oneapp_control.provisioning import runner

	# Random, unguessable, and obviously not a customer name.
	name = f"pool-{secrets.token_hex(4)}"

	doc = frappe.get_doc(
		{
			"doctype": "Standby Site",
			"press_site": name,
			"shard": shard,
			"status": "Creating",
			"created_on": now_datetime(),
		}
	).insert(ignore_permissions=True)

	job = runner.enqueue(
		tenant=None,
		action="Create Standby Site",
		payload={"standby": doc.name, "subdomain": name, "shard": shard},
		idempotency_key=f"standby:{doc.name}",
	)
	doc.db_set("provisioning_job", job.name)

	return doc.name


def claim(tenant_name: str):
	"""Hand a warm site to a tenant, if one is waiting on its shard.

	Returns the provisioning job that finishes the claim, or None when the pool
	is empty and the caller should build from scratch instead.
	"""
	from oneapp_control.provisioning import runner

	tenant = frappe.get_doc("Tenant", tenant_name)
	if not tenant.shard:
		return None

	# Lock the row so two simultaneous signups cannot claim the same site.
	candidate = frappe.db.sql(
		"""
		SELECT name, press_site FROM `tabStandby Site`
		WHERE shard = %s AND status = %s
		ORDER BY created_on ASC
		LIMIT 1
		FOR UPDATE
		""",
		(tenant.shard, CLAIMABLE),
		as_dict=True,
	)
	if not candidate:
		return None

	standby = frappe.get_doc("Standby Site", candidate[0]["name"])
	standby.db_set("status", "Claimed")
	standby.db_set("claimed_by", tenant.name)
	standby.db_set("claimed_on", now_datetime())

	tenant.db_set("press_site", standby.press_site)
	tenant.db_set("status", "Provisioning")

	return runner.enqueue(
		tenant.name,
		"Claim Standby Site",
		{"standby": standby.name, "press_site": standby.press_site},
		idempotency_key=f"claim:{tenant.name}",
	)


def release(standby_name: str, reason: str = ""):
	"""Return an unusable site to Broken so the pool refills around it."""
	doc = frappe.get_doc("Standby Site", standby_name)
	doc.db_set("status", "Broken")
	doc.db_set("last_error", reason[:500])


@frappe.whitelist()
def status_report() -> list[dict]:
	"""How many sites are warm and waiting, per shard."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	return pool_status()
