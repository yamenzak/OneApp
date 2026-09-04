"""One tenant's site as Frappe Cloud sees it: jobs, backups, domains, login."""

import frappe
from frappe import _
from .guard import _require_manager
from .press import _degrade, _press, _site_of


@frappe.whitelist(methods=["GET"])
def site_state(tenant: str) -> dict:
	"""Live facts about the site behind a tenant, straight from press."""
	_require_manager()
	doc, site = _site_of(tenant)
	if not site:
		return {"site": None, "reason": "This tenant has no site yet."}

	# The client inside the lambda, like every other read here. Built outside it,
	# a control plane with no press credentials raised while *constructing* the
	# client — before `_degrade` could turn that into a reason — so the one panel
	# that exists to say what is wrong with a site was the one that 500'd.
	facts, error = _degrade(lambda: _press().get_site(site), {})

	# Field names read off a real response rather than guessed: press returns
	# `group` for the bench, `server` for the machine, `frappe_version` for the
	# version, and puts the dates under `info`.
	info = facts.get("info") or {}
	region = facts.get("server_region_info") or {}

	return {
		"site": site,
		"error": error,
		"status": facts.get("status"),
		"bench": facts.get("group"),
		"server": facts.get("server"),
		"region": region.get("title"),
		"version": facts.get("frappe_version"),
		"latest_version": facts.get("latest_frappe_version"),
		"host_name": facts.get("host_name"),
		"setup_wizard_complete": bool(facts.get("setup_wizard_complete")),
		"created_on": info.get("created_on"),
		"last_deployed": info.get("last_deployed"),
		# Press schedules a migration or a version upgrade as its own record;
		# either being present is the answer to "why is this site busy?".
		"site_migration": facts.get("site_migration"),
		"version_upgrade": facts.get("version_upgrade"),
		"archive_failed": bool(facts.get("archive_failed")),
		# What the control plane believes, beside it. Two screens of one site is
		# the point: a disagreement here is the bug an operator is looking for.
		"control_plane": {
			"status": doc.status,
			"plan": doc.plan,
			"shard": doc.shard,
			"primary_domain": doc.primary_domain,
		},
	}


@frappe.whitelist(methods=["GET"])
def site_jobs(tenant: str, limit: int = 10) -> dict:
	"""What press has been doing to the site, newest first."""
	_require_manager()
	_, site = _site_of(tenant)
	if not site:
		return {"jobs": [], "reason": "This tenant has no site yet."}

	jobs, error = _degrade(lambda: _press().site_jobs(site, limit=limit), [])
	return {"jobs": jobs, "error": error}


@frappe.whitelist(methods=["GET"])
def site_backups(tenant: str) -> dict:
	"""Backups press holds, newest first.

	Press runs its own schedule. This is a window onto it rather than a second
	one — two backup schedules over one site is how a restore ends up reaching
	for the copy nobody was maintaining.
	"""
	_require_manager()
	_, site = _site_of(tenant)
	if not site:
		return {"backups": [], "reason": "This tenant has no site yet."}

	rows, error = _degrade(lambda: _press().backups(site), [])
	backups = [
		{
			"name": row.get("name"),
			"created_on": row.get("creation"),
			"status": row.get("status"),
			"with_files": bool(row.get("with_files")),
			"offsite": bool(row.get("offsite")),
			"database_size": row.get("database_size") or 0,
			"private_size": row.get("private_size") or 0,
			"public_size": row.get("public_size") or 0,
		}
		for row in rows
	]
	return {"backups": backups, "error": error}


@frappe.whitelist(methods=["POST"])
def take_backup(tenant: str, with_files: bool = True) -> str:
	"""Ask press for a backup now, before something irreversible."""
	_require_manager()
	doc, site = _site_of(tenant)
	if not site:
		frappe.throw(_("This tenant has no site yet."))

	_press().backup(site, with_files=with_files)
	return _("Backup started. It appears in the list once Frappe Cloud finishes it.")


@frappe.whitelist(methods=["GET"])
def backup_download(tenant: str, backup: str, file: str = "database") -> dict:
	"""A time-limited link to one file of one backup.

	Only offsite backups have one: a local backup lives on the server and press
	has nothing to hand out.
	"""
	_require_manager()
	_, site = _site_of(tenant)
	if not site:
		frappe.throw(_("This tenant has no site yet."))

	url, error = _degrade(lambda: _press().backup_link(site, backup, file), None)
	if not url and not error:
		error = _("That backup has no offsite copy to download.")
	return {"url": url, "error": error}


@frappe.whitelist(methods=["GET"])
def site_domains(tenant: str) -> dict:
	"""Every domain on the site, the primary one first."""
	_require_manager()
	_, site = _site_of(tenant)
	if not site:
		return {"domains": [], "reason": "This tenant has no site yet."}

	rows, error = _degrade(lambda: _press().site_domains(site), [])
	domains = [
		{
			"domain": row.get("domain"),
			"status": row.get("status"),
			"primary": bool(row.get("primary")),
			"redirect_to_primary": bool(row.get("redirect_to_primary")),
		}
		for row in rows
	]
	return {"domains": domains, "error": error}


@frappe.whitelist(methods=["POST"])
def set_primary_domain(tenant: str, domain: str) -> str:
	"""Make one of the site's domains the one it answers on.

	The control plane's `primary_domain` follows, because it is what every link
	we build for a customer is made from — leaving it behind would send people
	to the old host from emails and invoices.
	"""
	_require_manager()
	doc, site = _site_of(tenant)
	if not site:
		frappe.throw(_("This tenant has no site yet."))

	_press().set_primary_domain(site, domain)
	doc.db_set("primary_domain", domain)
	return _("{0} is now the primary domain.").format(domain)


@frappe.whitelist(methods=["POST"])
def remove_domain(tenant: str, domain: str) -> str:
	_require_manager()
	doc, site = _site_of(tenant)
	if not site:
		frappe.throw(_("This tenant has no site yet."))

	if domain == doc.primary_domain:
		frappe.throw(
			_("{0} is the primary domain. Make another one primary first.").format(domain)
		)

	_press().remove_domain(site, domain)
	return _("{0} removed.").format(domain)


@frappe.whitelist(methods=["POST"])
def support_login(tenant: str, reason: str) -> dict:
	"""Sign in to a customer's workspace, and record that we did.

	Break-glass access to someone else's data, so:

	* `reason` is required — an audit trail of unexplained entries is a list,
	  not an account.
	* The Support Login row is written *before* the session is handed over. A
	  login that succeeds is then always logged; writing it afterwards would
	  lose exactly the ones worth having if anything failed in between.
	* The link lands in the workspace's own app, not `/app`. Support should see
	  what the customer sees, and the desk is not part of this product — putting
	  an operator in it would make it part of theirs.
	"""
	_require_manager()

	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Say why you need to sign in to this workspace."))

	doc, site = _site_of(tenant)
	if not site:
		frappe.throw(_("This tenant has no site yet."))

	record = frappe.get_doc(
		{
			"doctype": "Support Login",
			"tenant": tenant,
			"site": site,
			"operator": frappe.session.user,
			"reason": reason,
			"logged_in_on": frappe.utils.now_datetime(),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()

	result = _press().login_sid(site, reason=reason)
	sid = result.get("sid")
	if not sid:
		frappe.throw(_("Frappe Cloud did not return a session for this site."))

	# Only now did anyone actually get in. An attempt that failed stays on the
	# record — losing it would be worse — but it does not read as an entry.
	record.db_set("succeeded", 1)
	frappe.db.commit()

	host = doc.primary_domain or result.get("site") or site
	return {"url": f"https://{host}/one?sid={sid}", "site": site}


@frappe.whitelist(methods=["GET"])
def support_logins(tenant: str, limit: int = 20) -> list:
	"""Who has been into this workspace, and why."""
	_require_manager()
	return frappe.get_all(
		"Support Login",
		filters={"tenant": tenant},
		fields=["operator", "reason", "logged_in_on", "succeeded"],
		order_by="logged_in_on desc",
		limit_page_length=limit,
	)
