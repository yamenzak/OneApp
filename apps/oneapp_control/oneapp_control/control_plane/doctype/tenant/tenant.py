import secrets

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from oneapp_control.utils.slug import validate_slug

GB = 1024 ** 3


class Tenant(Document):
	def autoname(self):
		self.tenant_slug = validate_slug(self.tenant_slug)
		self.name = self.tenant_slug

	def validate(self):
		self.tenant_slug = validate_slug(self.tenant_slug)
		self.validate_slug_is_immutable()
		self.assign_shard()
		self.set_site_name()
		self.ensure_hmac_secret()

	def validate_slug_is_immutable(self):
		"""The slug is the site's hostname. Renaming it would orphan the site."""
		if self.is_new():
			return

		before = self.get_doc_before_save()
		if before and before.tenant_slug != self.tenant_slug:
			frappe.throw(
				_("Tenant slug cannot be changed after creation — it is the site hostname. "
				  "Add a custom domain instead.")
			)

	def assign_shard(self):
		if self.shard or self.status == "Draft":
			return
		from oneapp_control.control_plane.doctype.shard.shard import pick_shard

		self.shard = pick_shard()

	def set_site_name(self):
		"""Derive the permanent internal address once a shard is known."""
		if self.site_name or not self.shard:
			return

		domain = frappe.db.get_value("Shard", self.shard, "domain") or default_domain()
		self.site_name = f"{self.tenant_slug}.{domain}"

	def ensure_hmac_secret(self):
		if not self.get("hmac_secret"):
			# 32 bytes of urandom, hex encoded.
			self.hmac_secret = secrets.token_hex(32)

	def on_update(self):
		self.sync_shard_counts()

	def after_delete(self):
		self.sync_shard_counts()

	def sync_shard_counts(self):
		before = self.get_doc_before_save()
		shards = {self.shard, before.shard if before else None} - {None}
		for shard in shards:
			refresh_tenant_count(shard)

	# ------------------------------------------------------------------ #
	# Quotas
	# ------------------------------------------------------------------ #

	@property
	def storage_quota_bytes(self) -> int:
		if self.storage_quota_gb_override:
			return int(self.storage_quota_gb_override) * GB

		if not self.plan:
			return 0

		return int(frappe.db.get_value("Plan", self.plan, "storage_gb") or 0) * GB

	@property
	def max_users(self) -> int:
		if not self.plan:
			return 0
		return int(frappe.db.get_value("Plan", self.plan, "max_users") or 0)

	def storage_fraction_used(self) -> float:
		quota = self.storage_quota_bytes
		if not quota:
			return 0.0
		return float(self.storage_used_bytes or 0) / quota

	# ------------------------------------------------------------------ #
	# Lifecycle
	# ------------------------------------------------------------------ #

	def mark_active(self, press_site: str | None = None):
		self.db_set("status", "Active")
		self.db_set("provisioned_on", now_datetime())
		if press_site:
			self.db_set("press_site", press_site)

	def mark_suspended(self, reason: str):
		self.db_set("status", "Suspended")
		self.db_set("suspended_on", now_datetime())
		self.db_set("suspended_reason", reason)

	def mark_failed(self, error: str):
		self.db_set("status", "Failed")
		self.db_set("suspended_reason", error)

	def signing_secret(self) -> str:
		return self.get_password("hmac_secret", raise_exception=False) or ""


def default_domain() -> str:
	return frappe.db.get_single_value("OneApp Control Settings", "tenant_domain") or "4dl.app"


def refresh_tenant_count(shard: str):
	if not shard or not frappe.db.exists("Shard", shard):
		return

	count = frappe.db.count("Tenant", {"shard": shard, "status": ("!=", "Archived")})
	frappe.db.set_value("Shard", shard, "tenant_count", count, update_modified=False)
