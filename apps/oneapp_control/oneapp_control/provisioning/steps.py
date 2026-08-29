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

def creation_domain(shard) -> str:
	"""The domain a site is *created* on, which is not always how it is reached.

	Wildcard mode creates directly on our root domain — one certificate covers
	every tenant. Per-tenant mode creates on Frappe Cloud's own domain and
	attaches ours afterwards, because a site cannot be created on a root domain
	press does not hold a certificate for.
	"""
	if shard.domain_mode == "Wildcard":
		return shard.domain

	if not shard.press_default_domain:
		raise PressPermanentError(
			f"Shard {shard.name} is in Per-tenant mode but has no press_default_domain."
		)
	return shard.press_default_domain


def uses_wildcard(shard) -> bool:
	return shard.domain_mode == "Wildcard"


def site_apps(shard) -> list[str]:
	"""Apps to install, from the shard rather than hardcoded.

	Bench groups differ — a control bench carries payments and oneapp_control, a
	tenant bench carries oneapp — and press rejects a site referencing an app the
	bench does not have.
	"""
	raw = shard.site_apps or "frappe,erpnext,oneapp"
	apps = [a.strip() for a in raw.split(",") if a.strip()]

	# frappe is implicit but press expects it listed first.
	if "frappe" not in apps:
		apps.insert(0, "frappe")

	return apps


def check_availability(job):
	"""Fail early rather than after a half-built site."""
	tenant = frappe.get_doc("Tenant", job.tenant)
	shard = frappe.get_doc("Shard", tenant.shard)

	# If we already created the site on a previous attempt, the name is taken by
	# us and this check would wrongly fail the job.
	if job.press_site:
		return None

	if get_client().site_exists(tenant.tenant_slug, creation_domain(shard)):
		raise PressPermanentError(
			f"Subdomain '{tenant.tenant_slug}.{creation_domain(shard)}' is already taken."
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
		domain=creation_domain(shard),
		release_group=shard.press_release_group,
		apps=site_apps(shard),
		plan=plan,
		server=shard.press_server or None,
		cluster=shard.press_cluster or None,
		version=shard.press_version or None,
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

	# Without this the site comes up unable to reach us: no entitlements, no
	# credits, no quota. Press silently drops empty values, so shipping a blank
	# would leave a site that looks provisioned and is quietly orphaned.
	if not settings.control_plane_url:
		raise PressPermanentError(
			"control_plane_url is not set in OneApp Control Settings. A site "
			"provisioned without it cannot reach the control plane."
		)

	config = {
		"oneapp_tenant": tenant.name,
		"oneapp_control_url": settings.control_plane_url,
		"oneapp_hmac_secret": tenant.signing_secret(),
		"oneapp_site_name": tenant.site_name,
	}

	get_client().update_config(job.press_site or tenant.press_site, config)
	return None


def create_dns_record(job):
	"""Point <slug>.<our domain> at the Frappe Cloud site.

	No-op in Wildcard mode, where a single record already covers every tenant.
	"""
	from oneapp_control.cloudflare import dns

	tenant = frappe.get_doc("Tenant", job.tenant)
	shard = frappe.get_doc("Shard", tenant.shard)

	if uses_wildcard(shard):
		return None

	if not dns.is_configured():
		raise PressPermanentError(
			"Per-tenant domain mode needs Cloudflare DNS configured in "
			"OneApp Control Settings."
		)

	try:
		dns.upsert_cname(tenant.site_name, job.press_site or tenant.press_site)
	except dns.DNSError as e:
		raise PressTransientError(f"DNS record failed: {e}") from e

	return None


def attach_domain(job):
	"""Ask Frappe Cloud to serve our hostname and issue a certificate for it."""
	tenant = frappe.get_doc("Tenant", job.tenant)
	shard = frappe.get_doc("Shard", tenant.shard)

	if uses_wildcard(shard):
		return None

	existing = {d.get("domain") for d in (get_client().site_domains(_site_for(job)) or [])}
	if tenant.site_name in existing:
		# Added on a previous attempt; adding again would error.
		return None

	try:
		get_client().add_domain(_site_for(job), tenant.site_name)
	except PressPermanentError as e:
		# Press resolves the CNAME synchronously inside add_domain and refuses if
		# it does not yet point at the site. We created that record moments ago,
		# so the usual cause is propagation, not misconfiguration — retry rather
		# than failing the tenant. The attempt ceiling still terminates a record
		# that is genuinely wrong.
		if _is_dns_not_ready(e):
			raise PressTransientError(
				f"DNS for {tenant.site_name} has not propagated yet: {e}"
			) from e
		raise

	return None


DNS_NOT_READY_MARKERS = (
	"unable to connect to the domain",
	"is the dns correct",
	"does not resolve",
)


def _is_dns_not_ready(error) -> bool:
	message = str(error).lower()
	return any(marker in message for marker in DNS_NOT_READY_MARKERS)


def await_domain_active(job):
	"""Wait for the certificate.

	Frappe Cloud resolves the CNAME and answers an ACME challenge, so this covers
	DNS propagation as well as issuance. Broken is terminal — retrying will not
	fix a misconfigured record.
	"""
	tenant = frappe.get_doc("Tenant", job.tenant)
	shard = frappe.get_doc("Shard", tenant.shard)

	if uses_wildcard(shard):
		return None

	for domain in get_client().site_domains(_site_for(job)) or []:
		if domain.get("domain") != tenant.site_name:
			continue

		status = domain.get("status")
		if status == "Active":
			return None
		if status == "Broken":
			raise PressPermanentError(
				f"Domain {tenant.site_name} is Broken. Check that the CNAME is "
				f"DNS-only (not proxied) and points at {tenant.press_site}."
			)
		return WAIT

	# Not listed yet — the add is still settling.
	return WAIT


def promote_domain(job):
	"""Make our hostname primary so Frappe generates links with it."""
	tenant = frappe.get_doc("Tenant", job.tenant)
	shard = frappe.get_doc("Shard", tenant.shard)

	if uses_wildcard(shard):
		return None

	get_client().set_primary_domain(_site_for(job), tenant.site_name)
	return None


def register_mail_routing(job):
	"""Add the tenant to the Cloudflare KV map the email worker reads.

	Without this the worker cannot resolve the tenant and rejects its mail at
	SMTP time, so it belongs in provisioning rather than in someone's runbook.

	Skipped when KV is unconfigured — a deployment not using inbound mail should
	still be able to create sites.
	"""
	from oneapp_control.cloudflare import kv

	if not kv.is_configured():
		return None

	try:
		kv.put_tenant(job.tenant)
	except kv.KVError as e:
		# Transient: the site is fine, only inbound mail is not routable yet.
		raise PressTransientError(f"Cloudflare KV write failed: {e}") from e

	return None


def remove_dns_record(job):
	"""Release the hostname when a tenant is archived."""
	from oneapp_control.cloudflare import dns

	tenant = frappe.get_doc("Tenant", job.tenant)
	shard = frappe.get_doc("Shard", tenant.shard)

	if uses_wildcard(shard) or not dns.is_configured():
		return None

	try:
		dns.delete_cname(tenant.site_name)
	except dns.DNSError:
		# Never block an archive on DNS cleanup.
		frappe.log_error(
			title=f"DNS cleanup failed for {job.tenant}", message=frappe.get_traceback()
		)

	return None


def deregister_mail_routing(job):
	"""Stop accepting mail for an archived tenant."""
	from oneapp_control.cloudflare import kv

	if not kv.is_configured():
		return None

	slug = frappe.db.get_value("Tenant", job.tenant, "tenant_slug")
	try:
		kv.delete_tenant(slug)
	except kv.KVError:
		# Never block an archive on cleanup; resync_all can repair the map.
		frappe.log_error(
			title=f"KV deregistration failed for {job.tenant}",
			message=frappe.get_traceback(),
		)

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
		("create_dns_record", create_dns_record),
		("attach_domain", attach_domain),
		("await_domain_active", await_domain_active),
		("promote_domain", promote_domain),
		("register_mail_routing", register_mail_routing),
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
		("deregister_mail_routing", deregister_mail_routing),
		("remove_dns_record", remove_dns_record),
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
