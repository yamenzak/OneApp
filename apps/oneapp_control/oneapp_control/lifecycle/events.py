"""The audit trail for everything the ladder does.

The lifecycle suspends sites, deletes them from Frappe Cloud and eventually
destroys data, on a timer, with nobody watching. A year later somebody will ask
why a workspace is gone, and "check the logs" is not an answer — error logs
rotate and the interesting transitions are not errors.

So every rung writes a row. Two calls rather than one, deliberately:

    row = events.opening(tenant, "Archived", reason=...)
    ... do the work, which may fail ...
    events.close(row, to_status="Archived", detail={...})

An intent that never completed leaves the opening row behind, which is exactly
what you want to find when a purge stopped halfway through a bucket.
"""

import json

import frappe
from frappe.utils import now_datetime

TRIGGERS = ("Sweep", "Webhook", "Operator", "Tenant Site", "Signup")


def record(
	tenant: str,
	event: str,
	*,
	reason: str = "",
	triggered_by: str = "Sweep",
	from_status: str | None = None,
	to_status: str | None = None,
	detail: dict | None = None,
) -> str | None:
	"""Write one completed event. Returns its name, or None if it could not.

	Never raises. A workspace must not stay suspended because the row saying so
	failed to insert — the transition is the thing that matters and the log is
	the record of it, not a precondition for it.
	"""
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Tenant Lifecycle Event",
				"tenant": tenant,
				"event": event,
				"occurred_on": now_datetime(),
				"triggered_by": triggered_by if triggered_by in TRIGGERS else "Sweep",
				"from_status": from_status,
				"to_status": to_status,
				"reason": (reason or "")[:1000],
				"detail": json.dumps(detail or {}, default=str)[:20000],
			}
		).insert(ignore_permissions=True)
		return doc.name
	except Exception:
		frappe.log_error(
			title=f"Lifecycle event not recorded: {tenant} {event}",
			message=frappe.get_traceback(),
		)
		return None


def opening(tenant: str, event: str, **kwargs) -> str | None:
	"""Record an intent before the work is attempted.

	`from_status` is filled in from the tenant if the caller did not, because at
	this point it is still true and afterwards it is not.
	"""
	if "from_status" not in kwargs:
		kwargs["from_status"] = frappe.db.get_value("Tenant", tenant, "status")
	return record(tenant, event, **kwargs)


def close(name: str | None, *, to_status: str | None = None, detail: dict | None = None):
	"""Fill in how an opened row turned out."""
	if not name:
		return
	try:
		values = {}
		if to_status:
			values["to_status"] = to_status
		if detail is not None:
			existing = frappe.db.get_value("Tenant Lifecycle Event", name, "detail")
			merged = {}
			if existing:
				try:
					merged = json.loads(existing)
				except ValueError:
					merged = {}
			merged.update(detail)
			values["detail"] = json.dumps(merged, default=str)[:20000]
		if values:
			frappe.db.set_value("Tenant Lifecycle Event", name, values)
	except Exception:
		frappe.log_error(
			title=f"Lifecycle event not closed: {name}", message=frappe.get_traceback()
		)


def last(tenant: str, event: str) -> dict | None:
	"""The most recent event of a kind, for "have we already warned them"."""
	rows = frappe.get_all(
		"Tenant Lifecycle Event",
		filters={"tenant": tenant, "event": event},
		fields=["name", "occurred_on", "reason"],
		order_by="occurred_on desc",
		limit=1,
	)
	return rows[0] if rows else None
