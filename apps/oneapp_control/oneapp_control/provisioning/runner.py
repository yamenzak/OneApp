"""Drives Provisioning Jobs forward.

Runs on a two-minute cron rather than inline, so a request never blocks on
Frappe Cloud and a worker restart mid-provision loses nothing — the job resumes
from its recorded step.
"""

import frappe
from frappe.utils import add_to_date, now_datetime

from oneapp_control.press.client import PressPermanentError, PressTransientError
from oneapp_control.provisioning.steps import PIPELINES, WAIT

MAX_ATTEMPTS = 12
BASE_BACKOFF_SECONDS = 20
MAX_BACKOFF_SECONDS = 30 * 60

RUNNABLE_STATES = ("Requested", "Running", "Awaiting Agent", "Bootstrapping")


def process_pending_jobs(limit: int = 20):
	"""Scheduled entry point."""
	now = now_datetime()

	names = frappe.get_all(
		"Provisioning Job",
		filters=[
			["state", "in", RUNNABLE_STATES],
			["next_retry_at", "<=", now],
		],
		order_by="creation asc",
		limit=limit,
		pluck="name",
	)

	for name in names:
		try:
			advance(name)
		except Exception:
			# One poisoned job must not stop the queue.
			frappe.log_error(
				title=f"Provisioning job {name} crashed",
				message=frappe.get_traceback(),
			)
		finally:
			frappe.db.commit()

	return len(names)


def advance(job_name: str):
	"""Run the next step of one job."""
	job = frappe.get_doc("Provisioning Job", job_name)

	pipeline = PIPELINES.get(job.action)
	if not pipeline:
		return job.fail(f"No pipeline defined for action '{job.action}'.")

	step_names = [name for name, _fn in pipeline]
	current = job.step or step_names[0]

	if current not in step_names:
		return job.fail(f"Unknown step '{current}' for action '{job.action}'.")

	index = step_names.index(current)
	_name, fn = pipeline[index]

	if not job.started_at:
		job.db_set("started_at", now_datetime())

	job.db_set("state", "Running")
	job.db_set("step", current)

	try:
		result = fn(job)
	except PressTransientError as e:
		return job.retry_later(str(e))
	except PressPermanentError as e:
		return job.fail(str(e))
	except Exception as e:
		# Unknown failures are treated as transient up to the attempt ceiling.
		# A genuine bug then surfaces as a Failed job rather than an infinite loop.
		frappe.log_error(
			title=f"Provisioning step {current} raised",
			message=frappe.get_traceback(),
		)
		return job.retry_later(f"{type(e).__name__}: {e}")

	if result == WAIT:
		return job.wait_for_agent()

	# Step done — advance, or finish.
	if index + 1 < len(step_names):
		job.db_set("step", step_names[index + 1])
		job.db_set("state", "Running")
		job.db_set("attempts", 0)
		job.db_set("next_retry_at", now_datetime())
		return None

	return job.succeed()


def backoff_for(attempts: int) -> int:
	"""Exponential, capped. Frappe Cloud is not ours to hammer."""
	return min(BASE_BACKOFF_SECONDS * (2 ** max(attempts - 1, 0)), MAX_BACKOFF_SECONDS)


# --------------------------------------------------------------------------- #
# Job creation
# --------------------------------------------------------------------------- #

def enqueue(tenant: str, action: str, payload: dict | None = None,
            idempotency_key: str | None = None):
	"""Create a job, or return the existing one for the same idempotency key.

	The default key covers tenant+action, so a double-clicked "provision" button
	cannot produce two sites. Pass an explicit key for actions that legitimately
	repeat, such as backups.
	"""
	import json

	key = idempotency_key or f"{action}:{tenant}"

	existing = frappe.db.get_value(
		"Provisioning Job", {"idempotency_key": key}, ["name", "state"], as_dict=True
	)
	if existing:
		if existing.state in ("Failed", "Cancelled"):
			# Let an operator retry a failed job by re-enqueuing it.
			job = frappe.get_doc("Provisioning Job", existing.name)
			job.reset()
			return job
		return frappe.get_doc("Provisioning Job", existing.name)

	return frappe.get_doc(
		{
			"doctype": "Provisioning Job",
			"tenant": tenant,
			"action": action,
			"state": "Requested",
			"idempotency_key": key,
			"payload": json.dumps(payload or {}),
			"next_retry_at": now_datetime(),
		}
	).insert(ignore_permissions=True)


def provision_tenant(tenant: str):
	"""Kick off site creation for a tenant."""
	doc = frappe.get_doc("Tenant", tenant)

	if not doc.shard:
		frappe.throw(
			f"Tenant {tenant} has no shard. "
			"No shard has headroom — add capacity before provisioning."
		)

	doc.db_set("status", "Provisioning")
	return enqueue(tenant, "Create Site")
