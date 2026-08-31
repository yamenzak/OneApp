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

# Measuring the database costs an information_schema scan over ~1,200 tables, so
# it is taken on a schedule and only the verdict is read per insert. The TTL
# outlives the hourly sweep on purpose: it is not a re-measurement trigger, it is
# the point at which a verdict left behind by a stopped scheduler expires. It
# expiring unblocks the workspace, which is the right way round to fail.
DB_VERDICT_KEY = "oneapp_database_over_quota"
DB_VERDICT_TTL = 6 * 3600

# Blocking every insert would break the very actions a customer needs to get
# back under the limit: Frappe records a Deleted Document when you delete, a
# Version when you edit, and logs as it goes. These stay writable so the site
# stays recoverable, and none of them is what filled the database.
DB_EXEMPT_DOCTYPES = {
	"Access Log",
	"Activity Log",
	"Authentication Log",
	"Comment",
	"Deleted Document",
	"DocShare",
	"Error Log",
	"Error Snapshot",
	"Notification Log",
	"Notification Settings",
	"Route History",
	"Scheduled Job Log",
	"Session Default",
	"View Log",
	"Version",
	"OneSpace Site State",
}


def current_usage() -> int:
	"""Bytes currently stored by this site."""
	return int(frappe.db.sql("SELECT COALESCE(SUM(file_size), 0) FROM `tabFile`")[0][0] or 0)


def quota_bytes() -> int:
	from oneapp.oneapp_core import sync

	return int(sync.state().get("storage_quota_bytes") or 0)


def database_quota_bytes() -> int:
	from oneapp.oneapp_core import sync

	return int(sync.state().get("database_quota_bytes") or 0)


def overage() -> dict:
	"""The control plane's verdict on whether to enforce at all.

	A workspace can end up over its limit without doing anything: an add-on line
	leaves the subscription, the quota comes down, and from in here the next
	upload fails on an ordinary day. The control plane gives them a window
	instead — see `oneapp_control/lifecycle/overage.py` — and this is that
	verdict, cached with everything else.

	Absent reads as "enforce", which is the safe direction and the right answer
	for a site that has never synced.
	"""
	from oneapp.oneapp_core import sync

	return sync.state().get("quota") or {}


def enforcement_ceiling() -> int | None:
	"""How large this site may grow right now, or None for the ordinary quota.

	During the grace window uploads are allowed up to what the workspace was
	holding when it went over — so somebody can replace a file, finish what they
	were doing and delete their way back under, without the window becoming a
	free upgrade.
	"""
	block = overage()
	if block.get("enforced", True):
		return None

	ceiling = int(block.get("ceiling_bytes") or 0)
	return ceiling or None


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

	# Inside the overage window the limit is where they already were, not what
	# the plan says. Whichever is larger, so a grace window can only ever be
	# more permissive than the quota it stands in for — a stale ceiling below
	# the plan's own limit would otherwise enforce something nobody agreed to.
	ceiling = enforcement_ceiling()
	limit = max(quota, ceiling) if ceiling else quota

	if used + incoming > limit:
		if ceiling:
			frappe.throw(
				_(
					"This workspace is over its storage limit and cannot grow "
					"further. Nothing has been deleted — free some space, or add "
					"storage from your account, and uploads resume."
				),
				exc=StorageQuotaExceeded,
			)

		frappe.throw(
			_(
				"Storage limit reached. This file needs {0} but only {1} of {2} remains. "
				"Delete some files or upgrade your plan."
			).format(
				format_bytes(incoming),
				format_bytes(max(limit - used, 0)),
				format_bytes(limit),
			),
			exc=StorageQuotaExceeded,
		)


class StorageQuotaExceeded(frappe.ValidationError):
	pass


class DatabaseQuotaExceeded(frappe.ValidationError):
	pass


def database_over_quota() -> bool:
	"""The cached verdict, measuring nothing.

	Never falls back to measuring. This is read on every insert, and the
	measurement is an information_schema scan over ~1,200 tables — paying for
	that in a request, even rarely, is how a cold cache turns into a slow site.
	An absent verdict reads as "not over", which is also the right answer when
	nothing has been configured yet.
	"""
	return bool(frappe.cache().get_value(DB_VERDICT_KEY))


def measure_database_quota() -> bool:
	"""Take the measurement and cache the verdict. Scheduled, never in a request."""
	quota = database_quota_bytes()
	over = bool(quota) and database_used_bytes() >= quota
	frappe.cache().set_value(DB_VERDICT_KEY, int(over), expires_in_sec=DB_VERDICT_TTL)
	return over


def enforce_database_quota(doc, method=None):
	"""before_insert on every doctype.

	Inserts are what grow a database, so they are what stops. Updates and deletes
	keep working, which means the way out is always available: delete something,
	or upgrade. Nothing is ever removed to enforce this.
	"""
	if doc.doctype in DB_EXEMPT_DOCTYPES:
		return
	# Installs, migrations and patches must not be caught by a customer quota —
	# a site that cannot be upgraded is a site we cannot support.
	if getattr(frappe.flags, "in_install", False) or getattr(frappe.flags, "in_migrate", False):
		return
	if getattr(frappe.flags, "in_patch", False) or getattr(frappe.flags, "in_test", False):
		return
	if not database_over_quota():
		return
	# Inside the overage window, nothing. Unlike files there is no ceiling that
	# would work here: the block is on inserts, and half-blocking those gives a
	# workspace that can be typed into and not saved. A larger table for a few
	# days is a better outcome than accounting that stops because a storage
	# add-on stopped being billed.
	if not overage().get("enforced", True):
		return

	frappe.throw(
		_(
			"Database limit reached ({0}). Nothing has been deleted and your data "
			"is intact, but new records are paused until you free space or upgrade."
		).format(format_bytes(database_quota_bytes())),
		exc=DatabaseQuotaExceeded,
	)


def database_summary() -> dict:
	quota = database_quota_bytes()
	used = database_used_bytes()
	fraction = (used / quota) if quota else 0

	# Keys match what the shared UsageBar component reads. The component is
	# generated into both apps, so the summary shapes it consumes are a contract:
	# renaming one of these silently empties a meter rather than failing.
	return {
		"used": used,
		"quota": quota,
		"fraction": round(fraction, 4),
		"warn": fraction >= WARN_FRACTION,
		"exceeded": bool(quota) and used >= quota,
		"used_label": format_bytes(used),
		"quota_label": format_bytes(quota),
	}


def usage_summary() -> dict:
	quota = quota_bytes()
	used = current_usage()
	fraction = (used / quota) if quota else 0

	# Keys match what the shared UsageBar component reads. The component is
	# generated into both apps, so the summary shapes it consumes are a contract:
	# renaming one of these silently empties a meter rather than failing.
	return {
		"used": used,
		"quota": quota,
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


def refresh_database_verdict() -> dict:
	"""Scheduled. Re-measure and cache whether this site is over its database cap.

	Runs hourly so the insert hook always has a recent answer without paying for
	the scan itself, and so a workspace that deletes data is unblocked on the
	next sweep rather than at the end of the cache window.
	"""
	over = measure_database_quota()
	return {"over_quota": over, **database_summary()}
