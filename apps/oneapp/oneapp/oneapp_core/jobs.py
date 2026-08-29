"""Background work, bounded by plan.

Frappe's workers pull from shared RQ queues per bench, and there is no supported
way to make a worker prefer one site's jobs over another's. Patching the queue is
not something worth carrying across framework upgrades, so this does the two
things that are achievable without touching the framework:

* **Cap concurrency per workspace.** ``Plan.background_workers`` limits how many
  of our jobs a site may have in flight, so no one tenant can occupy every
  worker on a shared bench. Capping is not preemption, but it is what actually
  protects the fleet.
* **Route by plan.** Higher plans enqueue on ``long``, which has its own workers,
  so a large import does not sit behind a small one.

Framework-internal jobs — a tenant's scheduled ERPNext work — are untouched and
run at everyone else's priority. That is a real limit, and stating it here is
better than implying a guarantee we do not make.
"""

import frappe

from oneapp.oneapp_core import sync

# Frappe's stock queues. `long` has a longer timeout and its own workers.
QUEUE_DEFAULT = "default"
QUEUE_LONG = "long"

# Above this many concurrent jobs a plan is treated as entitled to the long
# queue. Derived from the plan rather than named per plan, so adding a tier is a
# quota change and nothing else — the same rule as every other limit.
LONG_QUEUE_MIN_WORKERS = 3

LIVE_STATUSES = ("queued", "started", "deferred")


def worker_limit() -> int:
	"""Concurrent jobs this workspace may have in flight.

	Zero means unconfigured, not zero jobs allowed: refusing all background work
	because a sync failed would take the site down over a limit nobody set.
	"""
	return int(sync.state().get("background_workers") or 0)


def queue_for_plan() -> str:
	limit = worker_limit()
	return QUEUE_LONG if limit >= LONG_QUEUE_MIN_WORKERS else QUEUE_DEFAULT


class TooManyJobs(frappe.ValidationError):
	pass


def inflight() -> int | None:
	"""Jobs this site currently has queued or running.

	Read from RQ rather than from a counter of our own. A counter has to be
	decremented by something, and a worker killed mid-job never decrements it —
	the workspace would then be permanently unable to enqueue, with nothing to
	point at. RQ already knows, so it is asked.

	Returns None when the count cannot be taken, which callers read as "do not
	enforce": failing closed here would stop a tenant's work over a Redis blip.
	"""
	try:
		# Frappe's RQ Job virtual doctype scopes to the current site already.
		return frappe.db.count("RQ Job", {"status": ["in", LIVE_STATUSES]})
	except Exception:
		frappe.log_error(title="OneApp job count failed", message=frappe.get_traceback())
		return None


def enqueue(method, *, queue: str | None = None, **kwargs):
	"""Enqueue one of our jobs, respecting the plan's concurrency cap.

	Use this instead of ``frappe.enqueue`` for anything OneApp starts. Framework
	and ERPNext jobs deliberately keep going through Frappe directly — reaching
	into those would mean maintaining a patch across upgrades.
	"""
	assert_capacity()
	return frappe.enqueue(method, queue=queue or queue_for_plan(), **kwargs)


def assert_capacity():
	"""Refuse when the workspace is already at its concurrency limit."""
	limit = worker_limit()
	if not limit:
		return

	running = inflight()
	if running is None or running < limit:
		return

	frappe.throw(
		frappe._(
			"You already have {0} background jobs running, which is the limit on "
			"your plan. Wait for one to finish, or upgrade for more."
		).format(limit),
		exc=TooManyJobs,
	)


def summary() -> dict:
	"""What the workspace's usage bar shows for jobs."""
	limit = worker_limit()
	running = inflight() or 0
	return {
		"running": running,
		"limit": limit,
		"queue": queue_for_plan(),
		"at_limit": bool(limit) and running >= limit,
	}
