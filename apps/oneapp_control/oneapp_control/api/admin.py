"""Operator-facing endpoints. Session-authenticated, System Manager only."""

import frappe
from frappe import _

from oneapp_control.control_plane.doctype.shard.shard import capacity_report
from oneapp_control.entitlements import registry
from oneapp_control.provisioning import runner
from oneapp_control.utils.slug import is_available


def _require_manager():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)


@frappe.whitelist()
def check_slug(slug: str) -> dict:
	return {"slug": slug, "available": is_available(slug)}


@frappe.whitelist()
def create_tenant(tenant_slug: str, tenant_name: str, owner_email: str,
                  plan: str | None = None, provision: bool = True) -> dict:
	_require_manager()

	tenant = frappe.get_doc(
		{
			"doctype": "Tenant",
			"tenant_slug": tenant_slug,
			"tenant_name": tenant_name,
			"owner_email": owner_email,
			"plan": plan,
			"status": "Draft",
		}
	).insert()

	job = None
	if provision:
		job = runner.provision_tenant(tenant.name)

	return {"tenant": tenant.name, "job": job.name if job else None}


@frappe.whitelist()
def provision(tenant: str) -> str:
	_require_manager()
	return runner.provision_tenant(tenant).name


@frappe.whitelist()
def suspend(tenant: str, reason: str = "Suspended by operator") -> str:
	_require_manager()
	return runner.enqueue(
		tenant, "Suspend Site", {"reason": reason}, idempotency_key=f"suspend:{tenant}:{frappe.generate_hash(length=8)}"
	).name


@frappe.whitelist()
def resume(tenant: str) -> str:
	_require_manager()
	return runner.enqueue(
		tenant, "Resume Site", idempotency_key=f"resume:{tenant}:{frappe.generate_hash(length=8)}"
	).name


@frappe.whitelist()
def add_custom_domain(tenant: str, domain: str) -> str:
	_require_manager()
	return runner.enqueue(
		tenant, "Add Domain", {"domain": domain}, idempotency_key=f"domain:{tenant}:{domain}"
	).name


@frappe.whitelist()
def shards() -> list:
	_require_manager()
	return capacity_report()


@frappe.whitelist()
def tenant_apps(tenant: str) -> list:
	_require_manager()
	return registry.apps_for_tenant(tenant)


@frappe.whitelist()
def grant_app(tenant: str, app_code: str, note: str | None = None) -> str:
	_require_manager()
	return registry.grant(tenant, app_code, note)


@frappe.whitelist()
def revoke_app(tenant: str, app_code: str):
	_require_manager()
	registry.revoke(tenant, app_code)
	return {"ok": True}


@frappe.whitelist()
def press_capacity() -> dict:
	"""What exists on the Frappe Cloud account, for the shard form.

	Read live rather than typed in. A shard is a (server, bench group) pair and
	both names have to match press exactly — a typo produces a shard that looks
	fine here and fails at the first provision, several steps in, after a real
	site already exists.
	"""
	_require_manager()
	from oneapp_control.press.client import PressClient

	client = PressClient()
	servers = [
		{
			"name": s.get("name"),
			"title": s.get("title"),
			"cluster": s.get("cluster"),
			"status": s.get("status"),
		}
		for s in client.servers()
		if s.get("status") == "Active"
	]
	groups = [
		{"name": g.get("name"), "title": g.get("title"), "version": g.get("version")}
		for g in client.release_groups()
	]
	taken = frappe.get_all("Shard", fields=["press_server", "press_release_group"])
	return {
		"servers": servers,
		"release_groups": groups,
		"regions": frappe.get_all(
			"Region", filters={"is_active": 1}, fields=["name", "region_name"], order_by="sort_order"
		),
		# So the form can grey out pairs that already have a shard rather than
		# letting one be created twice.
		"existing": [[r.press_server, r.press_release_group] for r in taken],
	}


@frappe.whitelist()
def create_shard(
	shard_name: str,
	press_server: str,
	press_release_group: str,
	region: str,
	domain: str,
	press_version: str = "Nightly",
	capacity_tenants: int = 60,
	deploy_ring: str = "Fleet",
	environment: str = "Production",
	domain_mode: str = "Per-tenant",
	standby_target: int = 1,
	site_apps: str | None = None,
) -> str:
	"""Register a server as somewhere tenants can be placed.

	This is the whole of adding capacity: buy a server on Frappe Cloud, add a
	bench group on it, then create a shard here. The allocator picks up the new
	shard on the next signup without any further work — least-loaded first among
	shards that are Active, accepting, and below their cap — and the region
	becomes selectable at signup as soon as one shard in it has headroom.
	"""
	_require_manager()

	if frappe.db.exists("Shard", shard_name):
		frappe.throw(_("A shard called {0} already exists.").format(shard_name))

	duplicate = frappe.db.exists(
		"Shard", {"press_server": press_server, "press_release_group": press_release_group}
	)
	if duplicate:
		# Two shards over one bench group would both count capacity against the
		# same machine, so the allocator would happily overfill it.
		frappe.throw(
			_("{0} already covers that server and bench group.").format(duplicate)
		)

	shard = frappe.get_doc(
		{
			"doctype": "Shard",
			"shard_name": shard_name,
			"status": "Active",
			"deploy_ring": deploy_ring,
			"environment": environment,
			"accepts_new_tenants": 1,
			"capacity_tenants": int(capacity_tenants),
			"press_server": press_server,
			"press_release_group": press_release_group,
			"press_version": press_version,
			"region": region,
			"domain": domain,
			"domain_mode": domain_mode,
			"standby_target": int(standby_target),
			"site_apps": site_apps or "",
		}
	)
	shard.insert(ignore_permissions=True)
	return shard.name


@frappe.whitelist()
def bench_environment(release_group: str) -> dict:
	"""Who is on a bench group — reported, not enforced.

	`scripts/live.py` prints this in `status`. It used to be a veto: any group
	carrying a Production tenant was off limits to the tooling. That is the right
	rule once staging and production are separate benches, and the wrong one
	while a single bench carries both — it refused every deploy we could actually
	make. Everything ships from `main` to every site until there is budget for a
	second bench.

	`safe` is kept in the response because the shape is part of the tooling's
	contract, and it becomes a gate again the day the benches split.
	"""
	_require_manager()

	shards = frappe.get_all(
		"Shard", filters={"press_release_group": release_group}, pluck="name"
	)
	if not shards:
		return {"safe": False, "reason": f"No shard covers {release_group}."}

	production = frappe.get_all(
		"Tenant",
		filters={
			"shard": ["in", shards],
			"environment": "Production",
			"status": ["not in", ["Archived", "Draft"]],
		},
		fields=["name", "tenant_name"],
		limit_page_length=5,
	)
	if production:
		names = ", ".join(t["tenant_name"] or t["name"] for t in production)
		return {
			"safe": False,
			"reason": f"{release_group} carries production workspaces: {names}.",
		}

	return {"safe": True, "reason": f"{release_group} carries only staging tenants."}


# --------------------------------------------------------------------------- #
# What Frappe Cloud knows about a tenant's site
#
# The control plane holds intent — the plan, the quotas, who owns it. Press
# holds what is actually running. When those disagree the answer is nearly
# always in press, so the tenant page reads it live rather than caching a copy
# that can be wrong in a way nobody notices.
#
# Every one of these degrades rather than raising: press being unreachable
# should grey out a panel, not take down the page that would tell an operator
# why the site is unhappy.
# --------------------------------------------------------------------------- #


def _site_of(tenant: str) -> tuple:
	"""The Tenant doc and the press site name, or a reason there is none."""
	doc = frappe.get_doc("Tenant", tenant)
	return doc, (doc.press_site or doc.site_name or "")


def _press():
	from oneapp_control.press.client import PressClient

	return PressClient()


def _degrade(fn, default):
	"""Run a press call, or report why it could not run.

	Returns `(value, error)`. A panel that says "Frappe Cloud is unreachable" is
	worth more than a page that fails to load, and far more than one that shows
	an empty list as though the answer were nothing.
	"""
	from oneapp_control.press.client import PressError

	try:
		return fn(), None
	except PressError as e:
		return default, str(e)
	except Exception as e:  # noqa: BLE001 — a panel must not take down the page
		frappe.log_error(title="Press read failed", message=frappe.get_traceback())
		return default, str(e)


@frappe.whitelist(methods=["GET"])
def site_state(tenant: str) -> dict:
	"""Live facts about the site behind a tenant, straight from press."""
	_require_manager()
	doc, site = _site_of(tenant)
	if not site:
		return {"site": None, "reason": "This tenant has no site yet."}

	client = _press()
	facts, error = _degrade(lambda: client.get_site(site), {})

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
		# What the control plane believes, beside it. Two views of one site is
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
