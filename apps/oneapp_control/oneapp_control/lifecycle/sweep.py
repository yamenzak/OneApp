"""The ladder: what happens to a workspace that stops being paid for.

Stripe owns retries, card updates and SCA. We own consequences, and until now we
owned none — `Past Due` did nothing at all, so a workspace whose card failed kept
its site, kept costing us a Frappe Cloud site plan, and was never asked again.

    Active
      │  payment fails → the clock starts
      ▼
    Grace       (dunning_grace_days)   site works; we write, twice
      ▼
    Suspended   (suspended_days)       site off, intact, back in seconds
      ▼
    Archived    (cold_retention_days)  site deleted from Frappe Cloud;
      │                                 the cold copy is what is left
      ▼
    Purged                             every object deleted; irreversible

Four properties hold everything together:

**One clock.** `Tenant.dunning_started_on`, set the first time a subscription is
seen unpaid and cleared the moment it recovers. A workspace that recovers and
fails again restarts at the top rather than resuming mid-fall.

**Date-driven and idempotent.** Every rung is a comparison between two dates, so
running the sweep twice, or after a week of downtime, does the same thing once.

**Only what is on the ladder moves.** A workspace an operator suspended by hand
has no clock, and nothing here advances it. Automation that quietly finishes a
human's half-finished action is how data gets destroyed.

**Nothing irreversible happens without every gate.** Archiving refuses without a
cold copy. Purging refuses without the window, the warning, the switch, and no
hold. See `policy.py` for the floors under the windows themselves.
"""

import frappe
from frappe.utils import add_to_date, getdate, now_datetime, today

from oneapp_control.lifecycle import cold, events, policy
from oneapp_control.notifications import emails

# Subscription states that mean nobody is paying for this workspace. `Trialing`
# is not here — a trial is paid for by us on purpose, and `Tenant.trial_ends_on`
# is what ends it.
UNPAID = ("Past Due", "Canceled", "Incomplete")

# How many days before suspension the second warning goes out. Far enough ahead
# to update a card, close enough that it is not forgotten.
SECOND_WARNING_DAYS = 2


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def run(limit: int = 1000) -> dict:
	"""Daily. Walk every workspace and apply whichever rung it is on."""
	windows = policy.windows()
	acted, failed = [], []

	rows = frappe.get_all(
		"Tenant",
		filters={"status": ("not in", ("Draft", "Provisioning", "Purged"))},
		pluck="name",
		limit=limit,
	)

	for name in rows:
		try:
			outcome = consider(name, windows)
			if outcome:
				acted.append({"tenant": name, "did": outcome})
		except Exception as e:
			# One workspace's failure must not stop the fleet being swept —
			# and it must not be silent either.
			failed.append({"tenant": name, "error": str(e)[:200]})
			frappe.log_error(
				title=f"Lifecycle sweep failed for {name}", message=frappe.get_traceback()
			)

	note = f"{len(acted)} acted on, {len(failed)} failed"
	frappe.db.set_value(
		"OneSpace Control Settings",
		"OneSpace Control Settings",
		{"lifecycle_swept_on": now_datetime(), "lifecycle_note": note},
		update_modified=False,
	)

	return {"ok": True, "acted": acted, "failed": failed}


def consider(name: str, windows: dict | None = None) -> str | None:
	"""Apply the ladder to one workspace. Returns what it did, or None.

	Safe to call by hand on a single tenant, which is how an operator tests a
	policy change without waiting for tomorrow.
	"""
	windows = windows or policy.windows()
	tenant = frappe.get_doc("Tenant", name)

	if tenant.lifecycle_hold:
		return None

	# Purging is the one rung that runs off its own date rather than the clock,
	# so it is checked before the paid/unpaid question. An archived workspace has
	# no live subscription to consult and would otherwise look "unpaid" forever.
	if tenant.status == "Archived":
		return _archived(tenant, windows)

	if is_paid(tenant):
		return recover(tenant) if tenant.dunning_started_on else None

	if not tenant.dunning_started_on:
		return start(tenant, reason=_why_unpaid(tenant))

	days = (getdate(today()) - getdate(tenant.dunning_started_on)).days

	if tenant.status == "Suspended":
		return _suspended(tenant, windows)

	if days >= windows["dunning_grace_days"]:
		return _suspend(tenant, windows)

	return _grace(tenant, days, windows)


# --------------------------------------------------------------------------- #
# Paid, or not
# --------------------------------------------------------------------------- #

def is_paid(tenant) -> bool:
	"""Whether somebody is paying for this workspace right now.

	A workspace with neither a subscription nor an expired trial is *not* on the
	ladder: that is an operator's own creation — an internal instance, a
	migration in progress — and duning it would be automation surprising the
	person who built it.
	"""
	if tenant.subscription:
		status = frappe.db.get_value("Subscription", tenant.subscription, "status")
		return status not in UNPAID

	if tenant.trial_ends_on:
		return getdate(tenant.trial_ends_on) >= getdate(today())

	return True


def _why_unpaid(tenant) -> str:
	if tenant.subscription:
		status = frappe.db.get_value("Subscription", tenant.subscription, "status")
		return f"Subscription {tenant.subscription} is {status}."
	return f"The trial ended on {tenant.trial_ends_on}."


def start(tenant, *, reason: str = "", triggered_by: str = "Sweep") -> str:
	"""Put a workspace on the ladder and tell them why."""
	if tenant.dunning_started_on:
		return "already on the ladder"

	tenant.db_set({"dunning_started_on": today(), "dunning_stage": "Grace"})
	events.record(
		tenant.name,
		"Dunning Started",
		triggered_by=triggered_by,
		reason=reason or "No active subscription.",
	)

	windows = policy.windows()
	emails.payment_failed(
		tenant.name,
		suspends_on=add_to_date(today(), days=windows["dunning_grace_days"], as_string=True),
	)
	return "started dunning"


def recover(tenant, *, triggered_by: str = "Sweep") -> str:
	"""Somebody paid. Take the workspace off the ladder and bring it back.

	The clock is cleared whatever rung it was on, including from `Archived`,
	because a workspace whose subscription is live must not be sitting on a
	timer that will delete it.
	"""
	from oneapp_control.provisioning import runner

	was = tenant.status
	tenant.db_set(
		{
			"dunning_started_on": None,
			"dunning_stage": None,
			"purge_after": None,
			"purge_warned_on": None,
			"suspended_reason": None,
		}
	)
	events.record(
		tenant.name,
		"Dunning Cleared",
		triggered_by=triggered_by,
		reason="The subscription is being paid again.",
		from_status=was,
	)

	if was == "Suspended":
		runner.enqueue(
			tenant.name,
			"Resume Site",
			idempotency_key=f"resume:{tenant.name}:{tenant.suspended_on}",
		)
		return "resuming"

	if was == "Archived":
		if not tenant.cold_storage_key:
			# Purged, or archived before cold copies existed. Say so rather than
			# queueing a restore that would produce an empty workspace and look
			# like it worked.
			events.record(
				tenant.name,
				"Restored",
				triggered_by=triggered_by,
				reason="Nothing to restore from — this workspace has no cold copy.",
			)
			emails.nothing_to_restore(tenant.name)
			return "recovered, but there is nothing to restore"

		runner.enqueue(
			tenant.name,
			"Restore Site",
			{"cold_storage_key": tenant.cold_storage_key},
			idempotency_key=f"restore:{tenant.name}:{tenant.cold_storage_key}",
		)
		return "restoring"

	return "cleared"


# --------------------------------------------------------------------------- #
# The rungs
# --------------------------------------------------------------------------- #

def _grace(tenant, days: int, windows: dict) -> str | None:
	"""Still working, still being written to. Nothing is done to the site."""
	if tenant.dunning_stage != "Grace":
		tenant.db_set("dunning_stage", "Grace")

	remaining = windows["dunning_grace_days"] - days
	if remaining != SECOND_WARNING_DAYS:
		return None

	# Once per fall, not once per sweep. A warning is compared against the clock
	# rather than against today, so a workspace that recovered and failed again
	# is warned again — the previous warning was about a different lapse.
	warned = events.last(tenant.name, "Warned")
	if warned and getdate(warned["occurred_on"]) >= getdate(tenant.dunning_started_on):
		return None

	events.record(
		tenant.name,
		"Warned",
		reason=f"{remaining} days until this workspace is suspended.",
	)
	emails.suspension_warning(
		tenant.name,
		suspends_on=add_to_date(today(), days=remaining, as_string=True),
	)
	return "warned"


def _suspend(tenant, windows: dict) -> str:
	"""Grace is over. Take the last cold copy while the site can still make one,
	then turn it off.

	The order matters and is not obvious: Frappe Cloud's deactivate puts the site
	into maintenance mode, and Frappe's scheduler refuses to run at all under
	maintenance mode. So a suspended site cannot sync, cannot back itself up, and
	cannot be asked for anything. Whatever copy we want, we take now.
	"""
	from oneapp_control.provisioning import runner

	copy = cold.ensure(tenant.name)

	if copy.get("reason") == "requested":
		# The site has been asked and has not answered yet. Waiting costs a day
		# of a workspace nobody is paying for; suspending now costs the only
		# chance of a fresh copy. `cold.ensure` gives up on its own after a few
		# days, so this cannot wait forever.
		tenant.db_set("dunning_stage", "Grace")
		return "waiting for a final backup"

	row = events.opening(
		tenant.name,
		"Suspended",
		reason="Grace period elapsed with no payment.",
		detail={"cold": copy},
	)
	tenant.db_set("dunning_stage", "Suspended")
	runner.enqueue(
		tenant.name,
		"Suspend Site",
		{"reason": "Payment overdue"},
		idempotency_key=f"suspend:{tenant.name}:{tenant.dunning_started_on}",
	)
	events.close(row, to_status="Suspended")

	emails.suspended(
		tenant.name,
		archives_on=add_to_date(today(), days=windows["suspended_days"], as_string=True),
		has_copy=bool(copy.get("ok")),
	)
	return "suspended"


def _suspended(tenant, windows: dict) -> str | None:
	"""Off, intact, and on the clock to be archived."""
	if not tenant.suspended_on:
		return None

	days = (getdate(today()) - getdate(tenant.suspended_on)).days
	if days < windows["suspended_days"]:
		return None

	return _archive(tenant, windows)


def _archive(tenant, windows: dict) -> str:
	"""Delete the site from Frappe Cloud. Refuses without a cold copy.

	This is the rung where we stop paying for the site, and the first one that
	cannot be undone by flipping a switch — the site is gone and what is left is
	the copy. So "there is no copy" is a stop, not a warning: the workspace stays
	suspended, an operator is told, and nothing is deleted.
	"""
	from oneapp_control.provisioning import runner

	if not tenant.cold_storage_key:
		# One more attempt. A suspended site cannot answer, but a rolling backup
		# taken before suspension can still be promoted.
		copy = cold.ensure(tenant.name)
		tenant.reload()

		if not copy.get("ok"):
			events.record(
				tenant.name,
				"Archived",
				reason=(
					"Refused: this workspace has no cold copy, so archiving it "
					"would destroy it. It stays suspended until an operator "
					"resolves this."
				),
				detail=copy,
			)
			frappe.log_error(
				title=f"Cannot archive {tenant.name}: no cold copy",
				message=frappe.as_json(copy),
			)
			return "refused to archive without a cold copy"

	purge_after = add_to_date(today(), days=windows["cold_retention_days"], as_string=True)

	row = events.opening(
		tenant.name,
		"Archived",
		reason="Suspension period elapsed with no payment.",
		detail={"cold_storage_key": tenant.cold_storage_key, "purge_after": purge_after},
	)
	tenant.db_set({"dunning_stage": "Archived", "purge_after": purge_after})
	runner.enqueue(
		tenant.name,
		"Archive Site",
		{"reason": "Payment overdue"},
		idempotency_key=f"archive:{tenant.name}:{tenant.dunning_started_on}",
	)
	events.close(row, to_status="Archived")

	emails.archived(tenant.name, purge_after=purge_after)
	return "archiving"


def _archived(tenant, windows: dict) -> str | None:
	"""Gone from Frappe Cloud, held in R2, on the clock to be destroyed.

	Recovery is checked first: a workspace that starts paying again while
	archived is restored from its cold copy, and must not be purged on the way.
	"""
	if is_paid(tenant) and tenant.dunning_started_on:
		return recover(tenant)

	if not tenant.purge_after:
		# Archived by hand rather than by the ladder. An operator who wants it
		# destroyed sets the date; automation does not decide that for them.
		return None

	days_left = (getdate(tenant.purge_after) - getdate(today())).days

	if days_left <= windows["purge_warning_days"] and not tenant.purge_warned_on:
		tenant.db_set("purge_warned_on", today())
		events.record(
			tenant.name,
			"Purge Warned",
			reason=f"Everything held for this workspace is deleted on {tenant.purge_after}.",
		)
		emails.purge_warning(tenant.name, purge_after=tenant.purge_after)
		return "warned about the purge"

	if days_left > 0:
		return None

	return _purge(tenant, windows)


def _purge(tenant, windows: dict) -> str | None:
	"""Delete everything. Four gates, and all of them have to be open.

	This is the only irreversible step in the product, so the refusals are
	written out one at a time rather than folded into a single condition — a
	reader has to be able to see each one.
	"""
	if not windows["auto_purge_enabled"]:
		return None

	if tenant.lifecycle_hold:
		return None

	if not tenant.purge_warned_on:
		# The window elapsed without a warning ever going out — a window that was
		# widened and then narrowed, or a sweep that did not run. Warn now and
		# purge on the next pass.
		tenant.db_set("purge_warned_on", today())
		emails.purge_warning(tenant.name, purge_after=tenant.purge_after)
		return "warned about the purge"

	warned_days_ago = (getdate(today()) - getdate(tenant.purge_warned_on)).days
	if warned_days_ago < windows["purge_warning_days"]:
		return None

	result = cold.purge(tenant, reason="Cold retention elapsed with no payment.")
	tenant.db_set({"status": "Purged", "dunning_stage": "Purged"})
	emails.purged(tenant.name)

	return f"purged ({result.get('deleted', 0)} objects)"
