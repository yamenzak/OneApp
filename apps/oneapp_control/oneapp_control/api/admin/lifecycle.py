"""The dunning ladder, cold storage, and the clock that drives them."""

import frappe
from frappe import _
from .guard import _require_manager


@frappe.whitelist(methods=["POST"])
def hold_lifecycle(tenant: str) -> dict:
	"""Freeze a workspace out of the ladder entirely.

	A demo instance, a billing dispute, a legal hold, an account somebody is
	mid-conversation with. Nothing is suspended, archived or purged while this
	is set, and the clock keeps whatever value it had — releasing the hold
	resumes from the same rung rather than starting over.
	"""
	_require_manager()
	from oneapp_control.lifecycle import events

	doc = frappe.get_doc("Tenant", tenant)
	if doc.lifecycle_hold:
		return {"ok": True, "tenant": tenant, "held": True, "already": True}

	doc.db_set("lifecycle_hold", 1)
	events.record(
		tenant,
		"Held",
		triggered_by="Operator",
		reason=f"Held by {frappe.session.user}.",
	)
	return {"ok": True, "tenant": tenant, "held": True}


@frappe.whitelist(methods=["POST"])
def release_lifecycle(tenant: str) -> dict:
	"""Put a held workspace back on the ladder.

	It resumes at whatever rung its dates say it is on, which may be several
	rungs further down than when it was held — the clock did not stop, the
	consequences did. The next sweep will act on that, so this is worth doing
	deliberately rather than as tidying.
	"""
	_require_manager()
	from oneapp_control.lifecycle import events

	doc = frappe.get_doc("Tenant", tenant)
	doc.db_set("lifecycle_hold", 0)
	events.record(
		tenant,
		"Released",
		triggered_by="Operator",
		reason=f"Released by {frappe.session.user}.",
	)
	return {"ok": True, "tenant": tenant, "held": False}


@frappe.whitelist(methods=["POST"])
def run_lifecycle(tenant: str) -> dict:
	"""Apply the ladder to one workspace now, rather than at tomorrow's sweep.

	How a policy change is tested: widen a window, run this, read the event log.
	It takes exactly the path the scheduled sweep takes, including every refusal,
	so what happens here is what would have happened anyway.
	"""
	_require_manager()
	from oneapp_control.lifecycle import sweep

	return {"ok": True, "tenant": tenant, "did": sweep.consider(tenant)}


@frappe.whitelist(methods=["POST"])
def take_cold_copy(tenant: str) -> dict:
	"""Promote a backup to cold storage now.

	Before a migration, before an upgrade somebody is nervous about, or to
	unstick a workspace the ladder refused to archive. If the newest rolling
	backup is stale this asks the site for a fresh one instead, and the site
	answers on its next sync rather than immediately.
	"""
	_require_manager()
	from oneapp_control.lifecycle import cold

	return cold.ensure(tenant, triggered_by="Operator")


@frappe.whitelist(methods=["POST"])
def restore_from_cold(tenant: str) -> dict:
	"""Rebuild an archived workspace from its cold copy.

	Normally this happens on its own the moment somebody pays. This is the
	manual door: a customer who paid by transfer, a workspace archived by
	mistake, a restore rehearsal.
	"""
	_require_manager()
	from oneapp_control.provisioning import runner

	doc = frappe.get_doc("Tenant", tenant)
	if not doc.cold_storage_key:
		frappe.throw(
			_("{0} has no cold copy. There is nothing to restore from.").format(tenant)
		)
	if doc.status not in ("Archived", "Failed"):
		frappe.throw(
			_("{0} is {1}. A restore replaces the site's database, so it is only "
			  "offered for a workspace that no longer has one.").format(tenant, doc.status)
		)

	job = runner.enqueue(
		tenant,
		"Restore Site",
		{"cold_storage_key": doc.cold_storage_key},
		idempotency_key=f"restore:{tenant}:{doc.cold_storage_key}",
	)
	return {"ok": True, "tenant": tenant, "job": job.name}


@frappe.whitelist(methods=["POST"])
def purge_tenant(tenant: str) -> dict:
	"""Delete every object a workspace owns. Irreversible, and it says so.

	The sweep does this on its own once every window and warning has passed.
	This is for the cases a timer should not decide: a deletion request under
	data-protection law, or an operator who knows the retention is pointless.

	Refuses on a workspace that still has a site. Purging one of those would
	delete the backups of a workspace that is still running, which is not what
	anybody means by this word.
	"""
	_require_manager()
	from oneapp_control.lifecycle import cold

	doc = frappe.get_doc("Tenant", tenant)
	if doc.status not in ("Archived", "Purged"):
		frappe.throw(
			_("{0} is {1}. Archive it first — purging a workspace that still has "
			  "a site would delete the backups of something that is running.")
			.format(tenant, doc.status)
		)

	result = cold.purge(
		doc,
		triggered_by="Operator",
		reason=f"Purged by {frappe.session.user}.",
	)
	doc.db_set({"status": "Purged", "dunning_stage": "Purged"})
	return result


@frappe.whitelist(methods=["GET"])
def tenant_lifecycle(tenant: str) -> dict:
	"""Where a workspace stands on the ladder, and what got it there.

	Four things that live in four different places, gathered because an operator
	asking "why is this suspended" needs all four at once: the clock and its
	dates, the copy we hold, the backups arriving from the site, and the log of
	what the sweep actually did.

	Read-only, and it deliberately does not consult R2 — listing a prefix is a
	network call per workspace, and this is opened to answer a question about
	dates. The sizes are the ones recorded when the copy was taken.
	"""
	_require_manager()
	from oneapp_control.lifecycle import overage, policy

	doc = frappe.get_doc("Tenant", tenant)
	windows = policy.windows()

	return {
		"tenant": tenant,
		"status": doc.status,
		"windows": windows,
		"ladder": {
			"stage": doc.dunning_stage,
			"started_on": str(doc.dunning_started_on) if doc.dunning_started_on else None,
			"held": bool(doc.lifecycle_hold),
			"suspended_on": str(doc.suspended_on) if doc.suspended_on else None,
			"suspended_reason": doc.suspended_reason,
			"archived_on": str(doc.archived_on) if doc.archived_on else None,
			"purge_after": str(doc.purge_after) if doc.purge_after else None,
			"purge_warned_on": str(doc.purge_warned_on) if doc.purge_warned_on else None,
			"purged_on": str(doc.purged_on) if doc.purged_on else None,
			"restored_on": str(doc.restored_on) if doc.restored_on else None,
		},
		"cold": {
			"key": doc.cold_storage_key,
			"stored_on": str(doc.cold_stored_on) if doc.cold_stored_on else None,
			"bytes": doc.cold_storage_bytes or 0,
			"requested_on": (
				str(doc.cold_copy_requested_on) if doc.cold_copy_requested_on else None
			),
		},
		"backup": {
			"last_on": str(doc.last_backup_on) if doc.last_backup_on else None,
			"key": doc.last_backup_key,
			"bytes": doc.last_backup_bytes or 0,
			"error": doc.last_backup_error,
			"per_day": int(doc.terms.get("backups_per_day") or 0),
			"retention_days": int(doc.terms.get("backup_retention_days") or 0),
		},
		"quota": overage.state(doc),
		"events": frappe.get_all(
			"Tenant Lifecycle Event",
			filters={"tenant": tenant},
			fields=["name", "event", "occurred_on", "triggered_by", "reason",
			        "from_status", "to_status"],
			order_by="occurred_on desc, creation desc",
			limit=30,
		),
	}


# The lifecycle's windows have floors — `cold_retention_days` will not go below
# seven, on purpose — so the shortest honest walk from a failed payment to a
# purge is about nine days. That is right for production and useless for a
# rehearsal, and a rehearsal is the only way to find out whether a restore
# actually works before a customer needs one.
#
# So the clock moves instead of the windows. Every lifecycle date on the
# workspace shifts back by the days given, and the next `run_lifecycle` sees it
# further down the ladder — with every window, warning and refusal exactly as
# they are in production, which is the point. Nothing about the rules is
# loosened; only the calendar is.
LIFECYCLE_DATES = (
	"dunning_started_on",
	"suspended_on",
	"archived_on",
	"purge_after",
	"purge_warned_on",
	"over_quota_since",
	"cold_stored_on",
	"cold_copy_requested_on",
	"last_backup_on",
	"trial_ends_on",
)


@frappe.whitelist(methods=["POST"])
def advance_lifecycle_clock(tenant: str, days: int) -> dict:
	"""Age a workspace's lifecycle by `days`, for a rehearsal.

	**Refuses on a Production tenant.** `Tenant.environment` is inherited from
	the shard rather than chosen per tenant, so this cannot be pointed at a
	customer by editing the workspace — somebody would have to move it onto a
	staging shard first, which is a deliberate act and a visible one.

	Deliberately not a button in the console. A control that fast-forwards a
	deletion has no business sitting in a row of ordinary actions where somebody
	can reach it while meaning to click the one above; it is called from the
	rehearsal in docs/ONEADMIN.md and nowhere else.
	"""
	_require_manager()
	from frappe.utils import add_to_date, getdate

	from oneapp_control.lifecycle import events

	days = int(days)
	if days <= 0:
		frappe.throw(_("Give a positive number of days to age the workspace by."))

	doc = frappe.get_doc("Tenant", tenant)
	if doc.environment == "Production":
		frappe.throw(
			_(
				"{0} is a Production workspace. Ageing its clock would suspend, "
				"archive and eventually delete somebody's live business several "
				"days early. Rehearse on a staging shard."
			).format(tenant),
			frappe.PermissionError,
		)

	moved = {}
	for field in LIFECYCLE_DATES:
		value = doc.get(field)
		if not value:
			continue
		# Dates and datetimes both, and `add_to_date` keeps whichever it was
		# given — a Datetime field written as a date reads as midnight, which
		# is a day's drift on a window measured in days.
		moved[field] = add_to_date(value, days=-days)

	if moved:
		doc.db_set(moved)

	events.record(
		tenant,
		"Held" if doc.lifecycle_hold else "Dunning Started",
		triggered_by="Operator",
		reason=(
			f"Rehearsal: {frappe.session.user} aged this workspace's lifecycle "
			f"by {days} days. Not a real transition."
		),
		detail={"rehearsal": True, "days": days, "moved": {k: str(v) for k, v in moved.items()}},
	)

	return {
		"ok": True,
		"tenant": tenant,
		"days": days,
		"moved": {k: str(v) for k, v in moved.items()},
		"now": {
			"status": doc.status,
			"dunning_started_on": str(doc.dunning_started_on or ""),
			"purge_after": str(doc.purge_after or ""),
		},
	}
