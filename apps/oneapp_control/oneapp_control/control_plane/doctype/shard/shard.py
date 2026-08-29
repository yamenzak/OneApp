import frappe
from frappe import _
from frappe.model.document import Document


class Shard(Document):
	def validate(self):
		if self.capacity_tenants and self.tenant_count > self.capacity_tenants:
			# Not an error — an operator may deliberately overfill — but it should
			# stop attracting new tenants.
			self.accepts_new_tenants = 0

	def has_headroom(self) -> bool:
		if not self.accepts_new_tenants or self.status != "Active":
			return False
		if not self.capacity_tenants:
			return True
		return self.tenant_count < self.capacity_tenants


def pick_shard() -> str | None:
	"""Choose where a new tenant's site should live.

	Least-loaded first among shards that are Active, accepting, and below their
	soft cap. Canary is excluded — it carries internal tenants only, and its whole
	purpose is to take migrations before customers do.

	Returns None when nothing has headroom, which the caller must treat as a
	capacity incident rather than silently placing the tenant anyway.
	"""
	configured = frappe.db.get_single_value("OneApp Control Settings", "default_shard")
	if configured:
		shard = frappe.get_cached_doc("Shard", configured)
		if shard.has_headroom():
			return shard.name

	candidates = frappe.get_all(
		"Shard",
		filters={
			"status": "Active",
			"accepts_new_tenants": 1,
			"deploy_ring": ("!=", "Canary"),
		},
		fields=["name", "tenant_count", "capacity_tenants"],
		order_by="tenant_count asc",
	)

	for row in candidates:
		if not row.capacity_tenants or row.tenant_count < row.capacity_tenants:
			return row.name

	return None


@frappe.whitelist()
def capacity_report() -> list[dict]:
	"""Operational view: how full is each shard."""
	rows = frappe.get_all(
		"Shard",
		fields=[
			"name", "status", "deploy_ring", "tenant_count", "capacity_tenants",
			"accepts_new_tenants", "press_release_group",
		],
		order_by="deploy_ring asc, name asc",
	)

	for row in rows:
		cap = row.capacity_tenants or 0
		row["utilisation"] = round(row.tenant_count / cap, 3) if cap else None

	return rows
