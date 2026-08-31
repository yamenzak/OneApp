"""Retention, and noticing when a workspace stops backing itself up.

Taking the backup is the site's job — see `oneapp/oneapp_core/backup.py`. Two
things are deliberately not: deciding when an old copy may go, and noticing that
new ones stopped arriving. Both have to keep working for a workspace whose site
is suspended, off, or gone, which is exactly when the site cannot do them.

The rolling backups live under `backups/<tenant>/<stamp>/` and this expires them.
The cold copy lives under `cold/<tenant>/` and this never touches it — that
prefix answers to the lifecycle windows instead, and mixing the two would let a
seven-day retention delete the only copy of an archived workspace.
"""

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from oneapp_control.cloudflare import r2
from oneapp_control.lifecycle import events

BACKUP_PREFIX = "backups"
COLD_PREFIX = "cold"

# Retention never takes the newest set, whatever the window says. A workspace
# whose site stopped backing up a month ago has one copy left and a literal
# reading of a seven-day window would delete it — turning a stalled scheduler
# into data loss, which is the opposite of what a backup policy is for.
KEEP_AT_LEAST = 1

DEFAULT_RETENTION_DAYS = 7


def prefix_for(tenant: str) -> str:
	return f"{BACKUP_PREFIX}/{tenant}/"


def cold_prefix_for(tenant: str) -> str:
	return f"{COLD_PREFIX}/{tenant}/"


def sets(bucket: str, tenant: str) -> list[dict]:
	"""The backup sets a workspace holds, oldest first.

	A "set" is one `<stamp>/` folder — the database, the two file tarballs and
	the config that were taken together. Grouped because they are restored
	together and expired together; deleting half a set leaves something that
	looks like a backup and is not one.
	"""
	prefix = prefix_for(tenant)
	grouped: dict[str, dict] = {}

	for row in r2.objects(bucket, prefix):
		rest = row["key"][len(prefix):]
		stamp, _, name = rest.partition("/")
		if not stamp or not name:
			# An object directly under the tenant's prefix belongs to no set.
			# The flat layout this replaced wrote them; they are expired with
			# everything else rather than left to sit forever.
			stamp = ""
			name = rest

		found = grouped.setdefault(
			stamp, {"stamp": stamp, "keys": [], "bytes": 0, "modified": row["modified"]}
		)
		found["keys"].append(row["key"])
		found["bytes"] += row["size"]
		if row["modified"] and (
			not found["modified"] or row["modified"] > found["modified"]
		):
			found["modified"] = row["modified"]

	return sorted(grouped.values(), key=lambda s: s["stamp"])


def expired(sets_: list[dict], keep_days: int) -> list[dict]:
	"""Which sets may go: older than the window, and not the last one standing."""
	if len(sets_) <= KEEP_AT_LEAST:
		return []

	cutoff = add_to_date(now_datetime(), days=-max(int(keep_days or 0), 1))
	candidates = sets_[:-KEEP_AT_LEAST]

	out = []
	for one in candidates:
		when = one.get("modified")
		if when is None:
			continue
		# R2 hands back timezone-aware datetimes; Frappe's are naive local.
		when = get_datetime(str(when)[:19])
		if when < get_datetime(cutoff):
			out.append(one)
	return out


def retention_sweep(limit: int = 200) -> dict:
	"""Daily. Expire each workspace's backups past what its plan keeps."""
	if not r2.is_configured():
		return {"ok": False, "reason": "r2_not_configured"}

	from oneapp_control.billing import quotas

	swept, freed, failures = 0, 0, []

	tenants = frappe.get_all(
		"Tenant",
		filters={
			"storage_bucket": ("is", "set"),
			"status": ("not in", ("Draft", "Purged")),
		},
		fields=["name", "storage_bucket"],
		limit=limit,
	)

	for row in tenants:
		bucket = frappe.db.get_value("Storage Bucket", row["storage_bucket"], "bucket_name")
		if not bucket:
			continue

		keep_days = (
			int(quotas.for_tenant(row["name"]).get("backup_retention_days") or 0)
			or DEFAULT_RETENTION_DAYS
		)

		try:
			going = expired(sets(bucket, row["name"]), keep_days)
			keys = [key for one in going for key in one["keys"]]
			if keys:
				r2.delete_keys(bucket, keys)
				swept += len(going)
				freed += sum(one["bytes"] for one in going)

			# And the promoted copies this workspace no longer points at.
			expire_orphaned_cold(row["name"], bucket, keep_days)
		except Exception as e:
			# One unreachable bucket must not stop the rest being swept.
			failures.append({"tenant": row["name"], "error": str(e)[:200]})
			frappe.log_error(
				title=f"Backup retention failed for {row['name']}",
				message=frappe.get_traceback(),
			)

	return {"ok": True, "sets_expired": swept, "bytes_freed": freed, "failed": failures}


def staleness_sweep(limit: int = 500) -> dict:
	"""Daily. Notice the workspaces that have quietly stopped backing up.

	A stalled scheduler looks exactly like a workspace that never needed a
	backup, from here — right up until somebody asks for a restore. Twice the
	interval is the threshold: one missed slot is a blip, two is a fault.
	"""
	from oneapp_control.billing import quotas

	stale = []
	for row in frappe.get_all(
		"Tenant",
		filters={"status": "Active"},
		fields=["name", "last_backup_on", "last_backup_error"],
		limit=limit,
	):
		per_day = int(quotas.for_tenant(row["name"]).get("backups_per_day") or 0)
		if per_day <= 0:
			continue

		# Two slots' worth, floored at a day: an hourly plan should not be
		# reported stale two hours after a deploy restarted the scheduler.
		hours = max((24 / min(per_day, 24)) * 2, 24)
		cutoff = add_to_date(now_datetime(), hours=-hours)

		if not row["last_backup_on"] or get_datetime(row["last_backup_on"]) < get_datetime(cutoff):
			stale.append(row["name"])

	for tenant in stale:
		events.record(
			tenant,
			"Backup Failed",
			reason="No backup has arrived within twice this workspace's interval.",
			detail={"detected_by": "staleness_sweep"},
		)

	if stale:
		frappe.log_error(
			title="Workspaces with stale backups",
			message="\n".join(stale),
		)

	return {"ok": True, "stale": stale}


def cold_sets(bucket: str, tenant: str) -> list[dict]:
	"""The promoted copies a workspace holds, oldest first.

	Same shape as `sets`, over the cold prefix. Separate function rather than a
	parameter because every other caller of `sets` must never be handed the cold
	prefix by accident — that is the one thing retention may not touch.
	"""
	prefix = cold_prefix_for(tenant)
	grouped: dict[str, dict] = {}

	for row in r2.objects(bucket, prefix):
		stamp, _, name = row["key"][len(prefix):].partition("/")
		if not name:
			continue
		found = grouped.setdefault(
			stamp, {"stamp": stamp, "keys": [], "bytes": 0, "modified": row["modified"]}
		)
		found["keys"].append(row["key"])
		found["bytes"] += row["size"]

	return sorted(grouped.values(), key=lambda s: s["stamp"])


def expire_orphaned_cold(tenant: str, bucket: str, keep_days: int) -> int:
	"""Delete promoted copies that are no longer *the* cold copy.

	A workspace holds one at a time, named by `Tenant.cold_storage_key`, and
	that one is never touched — it may be the only copy of somebody's business.
	What this expires is the leftovers: the copy a restore drew from, which
	stops being the cold copy the moment the site is back, and any earlier
	promotion superseded by a newer one.

	Without this a workspace that fell and recovered twice would accumulate
	permanent copies of itself, under the one prefix nothing else expires.
	"""
	held = frappe.db.get_value("Tenant", tenant, "cold_storage_key") or ""
	going = []

	for one in cold_sets(bucket, tenant):
		prefix = f"{COLD_PREFIX}/{tenant}/{one['stamp']}"
		if held and (held == prefix or held.rstrip("/") == prefix):
			continue
		going.append(one)

	# Same window as an ordinary backup: once a workspace is live again, an old
	# promoted copy is an old backup and nothing more.
	return r2.delete_keys(
		bucket, [key for one in expired(going, keep_days) for key in one["keys"]]
	)


def scheduled_run() -> dict:
	"""What the scheduler calls: expire, then look for gaps."""
	return {"retention": retention_sweep(), "staleness": staleness_sweep()}
