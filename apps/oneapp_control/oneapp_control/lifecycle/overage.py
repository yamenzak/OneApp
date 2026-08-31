"""What happens when a workspace ends up holding more than it is allowed.

There are two ways to get here and they feel completely different to the person
it happens to.

**They filled it up.** Uploads and records accumulate until the plan's limit is
reached. They were warned at 80%, the number on their account page went up as
they watched, and the block at 100% is the thing they were told about.

**The limit came down.** An add-on line disappeared — dunning, a cancellation,
an edit in the Stripe dashboard — and `webhooks._reconcile_addons` followed it,
because Stripe is the authority on what is being charged. The workspace did not
change; what it was allowed to hold did. From inside, the next upload fails for
no reason they can see, on a day they did nothing unusual.

The second is the one this module exists for, and there is no reliable way to
tell the two apart after the fact — so both get the same treatment, which is a
window rather than a wall:

* **enforcement pauses** for `overage_grace_days`, so nothing they were doing
  stops mid-flow;
* **but usage may not grow.** The ceiling during grace is what they were holding
  at the moment they went over. They can replace a file, finish an invoice, and
  delete their way back under — they cannot treat the window as a free upgrade.

The database has no ceiling of that kind. Its block is on document inserts, and
half-blocking those produces a workspace that can be typed into and not saved,
so during grace database enforcement is simply off. A workspace whose accounting
stops because a storage add-on lapsed is a worse outcome than a few days of a
larger table.
"""

import frappe
from frappe.utils import add_to_date, getdate, today

from oneapp_control.lifecycle import events, policy

RESOURCES = ("storage", "database", "users")


def check(tenant, *, triggered_by: str = "Tenant Site") -> dict:
	"""Reconcile a workspace's overage state. Returns what enforcement should do.

	Called from the usage report, which is the one place that knows both what is
	held and what is allowed. Idempotent — the stamps only move when the answer
	changes, so an hourly report does not restart the window every hour.
	"""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	over = doc.over_quota()

	if not over:
		if doc.over_quota_since:
			doc.db_set({"over_quota_since": None, "over_quota_bytes": 0})
			events.record(
				doc.name,
				"Back Under Quota",
				triggered_by=triggered_by,
				reason="Everything this workspace holds is inside its limits again.",
			)
		return state(doc, over=[])

	if not doc.over_quota_since:
		# The ceiling is taken now, while it is still true. Taking it later —
		# at the first refused upload, say — would ratchet upward every time
		# somebody squeezed one more file through.
		doc.db_set(
			{"over_quota_since": today(), "over_quota_bytes": doc.storage_used_bytes or 0}
		)
		events.record(
			doc.name,
			"Over Quota",
			triggered_by=triggered_by,
			reason="Holding more than the plan and its add-ons allow: "
			       + ", ".join(over),
			detail={
				"over": over,
				"storage_used_bytes": doc.storage_used_bytes,
				"storage_quota_bytes": doc.storage_quota_bytes,
				"database_used_bytes": doc.database_used_bytes,
				"database_quota_bytes": doc.database_quota_bytes,
			},
		)
		_warn(doc, over)

	return state(doc, over=over)


def state(tenant, over: list[str] | None = None) -> dict:
	"""What the site should enforce, and why. Goes out with every sync.

	`enforced` is the only field the enforcement path has to read. The rest is
	there so the workspace can be told what is happening rather than just
	refused.
	"""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	over = doc.over_quota() if over is None else over

	if not doc.over_quota_since:
		return {"enforced": True, "over": over}

	days = policy.window("overage_grace_days")
	until = add_to_date(getdate(doc.over_quota_since), days=days, as_string=True)
	inside = getdate(today()) <= getdate(until)

	return {
		"enforced": not inside,
		"over": over,
		"over_since": str(doc.over_quota_since),
		"grace_until": until,
		# What the workspace may grow to while the window is open: exactly what
		# it was holding when it went over. Sent rather than derived on the site,
		# so the number a refusal quotes is the number we recorded.
		"ceiling_bytes": float(doc.over_quota_bytes or 0),
	}


def _warn(tenant, over: list[str]) -> None:
	from oneapp_control.notifications import emails

	days = policy.window("overage_grace_days")
	emails.over_quota(
		tenant.name,
		resources=over,
		grace_until=add_to_date(today(), days=days, as_string=True),
	)
