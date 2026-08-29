"""Storage quota enforcement.

Enforced at upload time, in a before_insert hook, because discovering you are
3 GB over after the fact is a far worse experience than a clear rejection at the
moment it happens.

R2 exposes no per-prefix usage metric, so the counter is ours to maintain: the
running total lives on this site and is reported upward to the control plane,
which is authoritative for the quota itself.
"""

import frappe
from frappe import _

WARN_FRACTION = 0.8


def current_usage() -> int:
	"""Bytes currently stored by this site."""
	return int(frappe.db.sql("SELECT COALESCE(SUM(file_size), 0) FROM `tabFile`")[0][0] or 0)


def quota_bytes() -> int:
	from oneapp.oneapp_core import sync

	return int(sync.state().get("storage_quota_bytes") or 0)


def database_quota_bytes() -> int:
	from oneapp.oneapp_core import sync

	return int(sync.state().get("database_quota_bytes") or 0)


def database_used_bytes() -> int:
	return int(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(data_length + index_length), 0)
			FROM information_schema.tables WHERE table_schema = DATABASE()
			"""
		)[0][0]
		or 0
	)


def enforce_quota(doc, method=None):
	"""before_insert on File.

	A quota of zero means unconfigured, not "no storage allowed" — refusing every
	upload because a sync failed would be worse than briefly allowing overage.
	"""
	quota = quota_bytes()
	if not quota:
		return

	incoming = int(doc.file_size or 0)
	if not incoming:
		return

	used = current_usage()

	if used + incoming > quota:
		frappe.throw(
			_(
				"Storage limit reached. This file needs {0} but only {1} of {2} remains. "
				"Delete some files or upgrade your plan."
			).format(
				format_bytes(incoming),
				format_bytes(max(quota - used, 0)),
				format_bytes(quota),
			),
			exc=StorageQuotaExceeded,
		)


class StorageQuotaExceeded(frappe.ValidationError):
	pass


def usage_summary() -> dict:
	quota = quota_bytes()
	used = current_usage()
	fraction = (used / quota) if quota else 0

	return {
		"used_bytes": used,
		"quota_bytes": quota,
		"fraction": round(fraction, 4),
		"warn": fraction >= WARN_FRACTION,
		"exceeded": bool(quota) and used >= quota,
		"used_label": format_bytes(used),
		"quota_label": format_bytes(quota),
	}


def format_bytes(value: int) -> str:
	value = float(value or 0)
	for unit in ("B", "KB", "MB", "GB", "TB"):
		if value < 1024 or unit == "TB":
			return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
		value /= 1024
	return f"{value:.1f} TB"
