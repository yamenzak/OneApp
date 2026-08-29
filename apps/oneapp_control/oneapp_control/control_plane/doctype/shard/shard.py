import frappe
from frappe import _
from frappe.model.document import Document


class Shard(Document):
	def validate(self):
		# Both are None on an unsaved document.
		if self.capacity_tenants and (self.tenant_count or 0) > self.capacity_tenants:
			# Not an error — an operator may deliberately overfill — but it should
			# stop attracting new tenants.
			self.accepts_new_tenants = 0

	def has_headroom(self) -> bool:
		if not self.accepts_new_tenants or self.status != "Active":
			return False
		if not self.capacity_tenants:
			return True
		return (self.tenant_count or 0) < self.capacity_tenants


def pick_shard(region: str | None = None) -> str | None:
	"""Choose where a new tenant's site should live.

	Least-loaded first among shards that are Active, accepting, and below their
	soft cap. Canary is excluded — it carries internal tenants only, and its whole
	purpose is to take migrations before customers do.

	Returns None when nothing has headroom, which the caller must treat as a
	capacity incident rather than silently placing the tenant anyway.
	"""
	# A region choice is the customer's, so it is never silently overridden by
	# the configured default.
	if not region:
		configured = frappe.db.get_single_value("OneApp Control Settings", "default_shard")
		if configured and frappe.db.exists("Shard", configured):
			shard = frappe.get_cached_doc("Shard", configured)
			if shard.has_headroom():
				return shard.name

	filters = {
		"status": "Active",
		"accepts_new_tenants": 1,
		"deploy_ring": ("!=", "Canary"),
	}
	if region:
		filters["region"] = region

	candidates = frappe.get_all(
		"Shard",
		filters=filters,
		fields=["name", "tenant_count", "capacity_tenants"],
		order_by="tenant_count asc",
	)

	for row in candidates:
		if not row.capacity_tenants or (row.tenant_count or 0) < row.capacity_tenants:
			return row.name

	return None


def regions_with_capacity() -> list[dict]:
	"""Regions a customer may currently choose.

	A region with no headroom is not offered rather than accepted and then
	failed at provisioning.
	"""
	rows = frappe.db.sql(
		"""
		SELECT r.name AS code, r.region_name, r.country, r.description
		FROM `tabRegion` r
		WHERE r.is_active = 1
		  AND EXISTS (
			SELECT 1 FROM `tabShard` s
			WHERE s.region = r.name
			  AND s.status = 'Active'
			  AND s.accepts_new_tenants = 1
			  AND s.deploy_ring != 'Canary'
			  AND (s.capacity_tenants = 0 OR s.tenant_count < s.capacity_tenants)
		  )
		ORDER BY r.sort_order ASC, r.region_name ASC
		""",
		as_dict=True,
	)
	return rows


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
		row["utilisation"] = round((row.tenant_count or 0) / cap, 3) if cap else None

	return rows
