"""Provisioning steps.

Each step is a small, idempotent function. Running one twice must be harmless,
because a network timeout leaves us genuinely unable to tell whether the call
landed — and the failure mode we refuse to accept is billing a customer for two
sites because a response was lost.

A step returns:
  * ``None``   — done, advance to the next step
  * ``WAIT``   — not finished, run me again after the backoff (agent polling)

and raises ``PressPermanentError`` to fail the job outright.
"""

import frappe
from frappe.utils import now_datetime

from oneapp_control.press.client import PressPermanentError, get_client

WAIT = "WAIT"

# Terminal agent-job states, per press's Agent Job doctype.
AGENT_SUCCESS = "Success"
AGENT_FAILED = ("Failure", "Delivery Failure")


# --------------------------------------------------------------------------- #
# Create Site
# --------------------------------------------------------------------------- #

def check_availability(job):
	"""Fail early rather than after a half-built site."""
	tenant = frappe.get_doc("Tenant", job.tenant)
	shard = frappe.get_doc("Shard", tenant.shard)

	# If we already created the site on a previous attempt, the name is taken by
	# us and this check would wrongly fail the job.
	if job.press_site:
		return None

	if get_client().site_exists(tenant.tenant_slug, shard.domain):
		raise PressPermanentError(
			f"Subdomain '{tenant.tenant_slug}.{shard.domain}' is already taken."
		)

	return None


def create_site(job):
	"""Ask press for the site. Idempotent via job.press_site."""
	if job.press_site:
		# A previous attempt succeeded; the response was just lost.
		return None

	tenant = frappe.get_doc("Tenant", job.tenant)
	shard = frappe.get_doc("Shard", tenant.shard)

	plan = None
	if tenant.plan:
		plan = frappe.db.get_value("Plan", tenant.plan, "press_site_plan")
	plan = plan or shard.press_site_plan

	result = get_client().create_site(
		subdomain=tenant.tenant_slug,
		domain=shard.domain,
		release_group=shard.press_release_group,
		apps=["frappe", "erpnext", "oneapp"],
		plan=plan,
		server=shard.press_server or None,
		cluster=shard.press_cluster or None,
	)

	if not result or not result.get("site"):
		raise PressPermanentError(f"press.api.site.new returned no site: {result!r}")

	job.db_set("press_site", result["site"])
	job.db_set("agent_job_id", result.get("job"))
	tenant.db_set("press_site", result["site"])

	return None


def await_agent(job):
	"""Poll the agent job until it reaches a terminal state."""
	if not job.agent_job_id:
		# Some actions complete synchronously and give us no job to wait on.
		return None

	status = (get_client().job(job.agent_job_id) or {}).get("status")
	job.db_set("agent_job_status", status)

	if status == AGENT_SUCCESS:
		return None

	if status in AGENT_FAILED:
		raise PressPermanentError(f"Agent job {job.agent_job_id} reported {status}.")

	return WAIT


def push_site_config(job):
	"""Tell the new site who it is.

	This is what lets the tenant site authenticate back to us. Without it the
	site is running but orphaned — it cannot sync entitlements or spend credits.
	"""
	tenant = frappe.get_doc("Tenant", job.tenant)
	settings = frappe.get_single("OneApp Control Settings")

	config = {
		"oneapp_tenant": tenant.name,
		"oneapp_control_url": settings.control_plane_url or "",
		"oneapp_hmac_secret": tenant.signing_secret(),
		"oneapp_site_name": tenant.site_name,
	}

	get_client().update_config(job.press_site or tenant.press_site, config)
	return None


def finalise_creation(job):
	tenant = frappe.get_doc("Tenant", job.tenant)
	tenant.mark_active(press_site=job.press_site)
	return None


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #

def _site_for(job) -> str:
	site = job.press_site or frappe.db.get_value("Tenant", job.tenant, "press_site")
	if not site:
		raise PressPermanentError(f"Tenant {job.tenant} has no press site.")
	return site


def suspend_site(job):
	result = get_client().deactivate(_site_for(job))
	_capture_job_id(job, result)
	return None


def finalise_suspend(job):
	payload = job.parsed_payload()
	frappe.get_doc("Tenant", job.tenant).mark_suspended(
		payload.get("reason") or "Suspended"
	)
	return None


def resume_site(job):
	result = get_client().activate(_site_for(job))
	_capture_job_id(job, result)
	return None


def finalise_resume(job):
	tenant = frappe.get_doc("Tenant", job.tenant)
	tenant.db_set("status", "Active")
	tenant.db_set("suspended_reason", None)
	return None


def backup_site(job):
	payload = job.parsed_payload()
	result = get_client().backup(_site_for(job), with_files=payload.get("with_files", True))
	_capture_job_id(job, result)
	return None


def archive_site(job):
	result = get_client().archive(_site_for(job), force=job.parsed_payload().get("force", False))
	_capture_job_id(job, result)
	return None


def finalise_archive(job):
	tenant = frappe.get_doc("Tenant", job.tenant)
	tenant.db_set("status", "Archived")
	tenant.db_set("archived_on", now_datetime())
	return None


def migrate_site(job):
	result = get_client().migrate(_site_for(job))
	_capture_job_id(job, result)
	return None


def change_plan(job):
	payload = job.parsed_payload()
	press_plan = payload.get("press_site_plan")
	if not press_plan:
		raise PressPermanentError("change_plan requires press_site_plan in the payload.")

	get_client().change_plan(_site_for(job), press_plan)

	if payload.get("plan"):
		frappe.db.set_value("Tenant", job.tenant, "plan", payload["plan"])

	return None


# --------------------------------------------------------------------------- #
# Domains
# --------------------------------------------------------------------------- #

def add_domain(job):
	payload = job.parsed_payload()
	domain = payload.get("domain")
	if not domain:
		raise PressPermanentError("add_domain requires a domain in the payload.")

	result = get_client().add_domain(_site_for(job), domain)
	_capture_job_id(job, result)
	return None


def set_primary_domain(job):
	payload = job.parsed_payload()
	domain = payload.get("domain")
	if not domain:
		raise PressPermanentError("set_primary_domain requires a domain in the payload.")

	get_client().set_primary_domain(_site_for(job), domain)

	# The custom domain is presentation only. site_name stays the address we use
	# for every internal call, because the customer controls this DNS record and
	# can break it at any time.
	frappe.db.set_value("Tenant", job.tenant, "primary_domain", domain)
	return None


def _capture_job_id(job, result):
	"""Press returns an agent job id in a few different shapes."""
	if isinstance(result, dict):
		job_id = result.get("job") or result.get("name")
		if job_id:
			job.db_set("agent_job_id", job_id)


# --------------------------------------------------------------------------- #
# Step sequences
# --------------------------------------------------------------------------- #

PIPELINES = {
	"Create Site": [
		("check_availability", check_availability),
		("create_site", create_site),
		("await_agent", await_agent),
		("push_site_config", push_site_config),
		("finalise_creation", finalise_creation),
	],
	"Suspend Site": [
		("suspend_site", suspend_site),
		("await_agent", await_agent),
		("finalise_suspend", finalise_suspend),
	],
	"Resume Site": [
		("resume_site", resume_site),
		("await_agent", await_agent),
		("finalise_resume", finalise_resume),
	],
	"Backup Site": [
		("backup_site", backup_site),
		("await_agent", await_agent),
	],
	"Archive Site": [
		("archive_site", archive_site),
		("await_agent", await_agent),
		("finalise_archive", finalise_archive),
	],
	"Migrate Site": [
		("migrate_site", migrate_site),
		("await_agent", await_agent),
	],
	"Change Plan": [
		("change_plan", change_plan),
	],
	"Add Domain": [
		("add_domain", add_domain),
		("await_agent", await_agent),
	],
	"Set Primary Domain": [
		("set_primary_domain", set_primary_domain),
	],
}
