"""Operator-facing endpoints. Session-authenticated, System Manager only."""

import json

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
	return registry.spaces_for_tenant(tenant)


@frappe.whitelist(methods=["GET"])
def tenant_app_access(tenant: str) -> list:
	"""Every app, and whether this workspace has it.

	`spaces_for_tenant` answers the launcher's question — what to render — so it
	returns only what the tenant already has. An operator deciding what to grant
	needs the other half: the restricted apps this workspace does *not* have are
	the only ones there is anything to do about, and they are invisible in a list
	of what it does.
	"""
	_require_manager()
	entitled = {
		row.app
		for row in frappe.get_all(
			"Space Entitlement", filters={"tenant": tenant, "enabled": 1}, fields=["app"]
		)
	}

	apps = frappe.get_all(
		"OneSpace Space",
		filters={"is_active": 1},
		fields=["name as space_code", "space_label", "module", "availability", "icon",
		        "sort_order", "description"],
		order_by="sort_order asc, space_label asc",
	)
	for app in apps:
		app["entitled"] = (
			app.availability != "Restricted" or app.space_code in entitled
		)
	return apps


@frappe.whitelist()
def grant_app(tenant: str, space_code: str, note: str | None = None) -> str:
	_require_manager()
	return registry.grant(tenant, space_code, note)


@frappe.whitelist()
def revoke_app(tenant: str, space_code: str):
	_require_manager()
	registry.revoke(tenant, space_code)
	return {"ok": True}


# Tenants per GB of RAM, and per GB of disk, taken from the sizing table in
# docs/ONEADMIN.md, Tenancy — the one that says MariaDB is the ceiling and a fresh
# ERPNext site is ~150-250MB across ~1,200 tables. Its three rows work out at
# roughly the same ratio each (4GB/80GB → ~30 tenants, 16/320 → ~115,
# 32/640 → ~200), so the recommendation is the table, not a new opinion.
TENANTS_PER_GB_RAM = 7.0
TENANTS_PER_GB_DISK = 0.35


def recommended_capacity(plan: dict | None) -> int | None:
	"""A starting soft cap for a server, from its own specs.

	A number an operator can change, not a limit — the cap is a soft one and
	MariaDB is the real ceiling. But "60" was the form's default for every
	machine, which is wrong in both directions: it overfills a 4GB box and
	wastes half a 32GB one.
	"""
	if not plan:
		return None

	memory_gb = (plan.get("memory") or 0) / 1024
	disk_gb = plan.get("disk") or 0
	if not memory_gb and not disk_gb:
		return None

	limits = [
		int(memory_gb * TENANTS_PER_GB_RAM) if memory_gb else None,
		int(disk_gb * TENANTS_PER_GB_DISK) if disk_gb else None,
	]
	# Disk fills before CPU does, and memory before either — whichever runs out
	# first is the number.
	return min([x for x in limits if x]) or None


@frappe.whitelist()
def press_capacity() -> dict:
	"""What exists on the Frappe Cloud account, for the shard form.

	Read live rather than typed in. A shard is a (server, bench group) pair and
	both names have to match press exactly — a typo produces a shard that looks
	fine here and fails at the first provision, several steps in, after a real
	site already exists.

	The same argument applies to everything else the form used to ask for and
	press already knows: the bench group's version, its apps, the server's
	cluster, and the site plans press will accept. All of them fail late and
	obscurely when wrong, so none of them is a text box any more.
	"""
	_require_manager()
	from oneapp_control.press.client import PressClient

	# Degrades like every other press read. The form is opened by an operator who
	# may be *about* to fix the credentials, and a page that 500s tells them
	# nothing; the regions and the tenant domain are ours and still useful.
	try:
		client = PressClient()
		raw_servers, error = _degrade(client.servers, [])
		raw_groups, group_error = _degrade(client.release_groups, [])
		error = error or group_error
		plans = _site_plans(client)
	except Exception as e:  # noqa: BLE001 — no credentials at all lands here
		raw_servers, raw_groups, plans, error = [], [], [], str(e)

	servers = []
	for s in raw_servers:
		if s.get("status") != "Active":
			continue
		plan = s.get("plan") or {}
		servers.append(
			{
				"name": s.get("name"),
				"title": s.get("title"),
				"cluster": s.get("cluster"),
				"status": s.get("status"),
				# Shown so an operator can see which machine they picked, and
				# used for the capacity recommendation below.
				"instance_type": plan.get("instance_type"),
				"vcpu": plan.get("vcpu"),
				"memory_gb": round((plan.get("memory") or 0) / 1024, 1) or None,
				"disk_gb": plan.get("disk"),
				"recommended_capacity": recommended_capacity(plan),
			}
		)

	groups = [
		{
			"name": g.get("name"),
			"title": g.get("title"),
			# The blocking readiness check exists because this being wrong sends
			# press down its public marketplace path and fails naming the wrong
			# cause. It is on every group listing, so there is no reason to ask.
			"version": g.get("version"),
			"sites": g.get("number_of_sites"),
			"apps": g.get("number_of_apps"),
		}
		for g in raw_groups
	]

	taken = frappe.get_all("Shard", fields=["press_server", "press_release_group"])
	return {
		"servers": servers,
		"release_groups": groups,
		"site_plans": plans,
		# Named rather than an empty list: "Frappe Cloud is unreachable" and
		# "you own no servers" are different problems, and only one of them is
		# solved by buying a server.
		"error": error,
		"regions": frappe.get_all(
			"Region", filters={"is_active": 1}, fields=["name", "region_name"], order_by="sort_order"
		),
		"tenant_domain": frappe.db.get_single_value("OneSpace Control Settings", "tenant_domain"),
		# So the form can grey out pairs that already have a shard rather than
		# letting one be created twice.
		"existing": [[r.press_server, r.press_release_group] for r in taken],
	}


def _site_plans(client) -> list[dict]:
	"""Press site plans, deduplicated to the ones worth choosing from.

	Press lists a plan per cluster variant ("USD 5", "USD 5 - Hetzner"), which is
	a long list of near-duplicates in a select. Sorted by price so the cheapest —
	the one a shard default usually wants — is first.
	"""
	# `_degrade` returns (value, error): a form that cannot list site plans should
	# still open, with the field left as it was.
	plans, _error = _degrade(client.site_plans, [])
	rows = [
		{
			"name": p.get("name"),
			"title": p.get("plan_title") or p.get("name"),
			"price_usd": p.get("price_usd"),
			"storage_mb": p.get("max_storage_usage"),
			"database_mb": p.get("max_database_usage"),
		}
		for p in plans
		if p.get("name")
	]
	return sorted(rows, key=lambda r: (r["price_usd"] or 0, r["name"]))


@frappe.whitelist(methods=["GET"])
def bench_apps(release_group: str) -> dict:
	"""The apps on a bench group, in press's own order.

	A site can only install what its bench carries, so `site_apps` was a text box
	whose only correct value was already knowable. Fetched per group rather than
	with the group list, because `deploy_information` is a call each and a form
	only ever needs the one that was picked.
	"""
	_require_manager()
	from oneapp_control.press.client import PressClient

	apps, error = _degrade(lambda: PressClient().group_apps(release_group), None)
	if apps is None:
		# Named rather than silently empty: "we could not ask" and "the bench has
		# no apps" are different problems and only one of them is the operator's.
		return {"available": False, "apps": [], "error": error}

	return {
		"available": True,
		"error": None,
		"apps": [
			{
				"app": a.get("app") or a.get("name"),
				"title": a.get("title") or a.get("app"),
				"branch": a.get("current_branch") or a.get("branch"),
			}
			for a in apps
			if a.get("app") or a.get("name")
		],
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
	press_cluster: str | None = None,
	press_site_plan: str | None = None,
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
			# Both read off the server press told us about rather than typed:
			# create_site passes the cluster through, and a wrong site plan fails
			# at creation.
			"press_cluster": press_cluster or "",
			"press_site_plan": press_site_plan or "",
			"region": region,
			"domain": domain,
			"domain_mode": domain_mode,
			"standby_target": int(standby_target),
			"site_apps": site_apps or "",
		}
	)
	shard.insert(ignore_permissions=True)
	return shard.name


# What an operator may change on a shard after it exists. Deliberately not the
# press identity — server, bench group, version, domain and mode are what the
# tenants already on it were created against, and editing them here would leave
# the shard describing a machine those sites are not on. Replacing a shard is
# registering a new one and draining the old.
SHARD_EDITABLE = (
	"status",
	"accepts_new_tenants",
	"capacity_tenants",
	"deploy_ring",
	"standby_target",
	"press_site_plan",
	"region",
	"notes",
)


@frappe.whitelist(methods=["POST"])
def update_shard(shard: str, values: str | dict) -> dict:
	"""Change a shard's operating settings.

	Draining a server is `accepts_new_tenants = 0`, which docs/ONEADMIN.md names
	as the way to drain one — and which, until now, could only be done in the
	desk. So could raising a soft cap on a machine that turned out to hold more.

	One `values` object rather than a parameter per field: the endpoint then
	rejects anything outside SHARD_EDITABLE explicitly, instead of silently
	ignoring a field it does not have a parameter for.
	"""
	_require_manager()

	if isinstance(values, str):
		values = json.loads(values)
	if not isinstance(values, dict):
		frappe.throw(_("Those changes could not be read."))

	rejected = sorted(set(values) - set(SHARD_EDITABLE))
	if rejected:
		frappe.throw(
			_("{0} cannot be changed on an existing shard.").format(", ".join(rejected))
		)

	doc = frappe.get_doc("Shard", shard)
	for field, value in values.items():
		doc.set(field, value)

	doc.save(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["GET"])
def shard(shard: str) -> dict:
	"""One shard, with what press says about the machine under it."""
	_require_manager()
	doc = frappe.get_doc("Shard", shard).as_dict()
	doc["editable"] = list(SHARD_EDITABLE)
	return doc


@frappe.whitelist()
def bench_environment(release_group: str) -> dict:
	"""Who is on a bench group — reported, not enforced.

	Answers "what am I about to restart" before a deploy. It used to be a veto,
	consulted by tooling that patched a running bench; that tooling is gone and
	deploys are made from the Frappe Cloud dashboard by somebody who can read
	this first.

	`safe` is kept in the response because it is the question worth asking —
	whether this group carries a Production tenant — and it becomes a gate again
	the day staging and production are separate benches. Today one bench carries
	both, so enforcing it would refuse every deploy that can actually be made.
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


# --------------------------------------------------------------------------- #
# The rest of the control plane
#
# Everything below exists because the desk is not part of this product
# (docs/ONEADMIN.md, No desk). A record an operator can only reach through /app is a record
# only someone who knows Frappe can reach, and the whole point of the operator
# console is that running this does not require that.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def signups(limit: int = 50) -> list:
	"""Account requests, newest first.

	A signup that took payment and then failed to provision is invisible
	otherwise: the customer has been charged, there is no tenant, and nothing
	surfaces it.
	"""
	_require_manager()
	return frappe.get_all(
		"Account Request",
		fields=[
			"name", "email", "workspace_name", "requested_slug", "status", "plan",
			"interval", "region", "tenant", "paid_on", "completed_on",
			"failure_reason", "creation",
		],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)


@frappe.whitelist(methods=["GET"])
def webhook_events(limit: int = 50, status: str | None = None) -> list:
	"""Stripe events we have seen, and what became of them.

	The webhook answers 200 even when a handler raises, because Stripe would
	otherwise retry a bug forever — the row is the record to replay from once it
	is fixed. That only works if the rows are visible.
	"""
	_require_manager()
	filters = {"status": status} if status else None
	return frappe.get_all(
		"Stripe Webhook Event",
		filters=filters,
		fields=["name", "event_id", "event_type", "status", "tenant", "subscription",
		        "processed_on", "error", "creation"],
		order_by="creation desc",
		limit=min(int(limit), 200),
	)


@frappe.whitelist(methods=["POST"])
def replay_webhook(event: str) -> dict:
	"""Run a stored Stripe event through its handler again.

	The deliberate half of answering 200 on failure. Idempotent by the same
	arguments the handlers already rely on — a replayed invoice does not grant
	twice, and a replayed plan change applies once.
	"""
	_require_manager()
	from oneapp_control.billing import webhooks

	record = frappe.get_doc("Stripe Webhook Event", event)
	if record.event_type not in webhooks.HANDLERS:
		frappe.throw(_("{0} has no handler.").format(record.event_type))

	payload = json.loads(record.payload or "{}")
	obj = (payload.get("data") or {}).get("object")
	if not obj:
		frappe.throw(_("This event was recorded without a payload to replay."))

	try:
		webhooks.HANDLERS[record.event_type](obj, record)
		record.db_set("status", "Processed")
		record.db_set("processed_on", frappe.utils.now_datetime())
		record.db_set("error", None)
		return {"ok": True}
	except Exception as e:
		record.db_set("status", "Failed")
		record.db_set("error", frappe.get_traceback()[:5000])
		frappe.throw(_("Replay failed: {0}").format(str(e)[:200]))


@frappe.whitelist(methods=["GET"])
def standby_pool() -> list:
	"""Warm sites, by shard.

	The pool is what makes signup instant, so an empty one is a slow signup and
	a stuck one is a wasted site. Neither shows anywhere else.
	"""
	_require_manager()
	rows = frappe.get_all(
		"Standby Site",
		fields=["name", "press_site", "status", "shard", "claimed_by", "claimed_on",
		        "created_on", "last_error"],
		order_by="creation desc",
		limit=200,
	)
	targets = {
		s.name: s.standby_target
		for s in frappe.get_all("Shard", fields=["name", "standby_target"])
	}
	for row in rows:
		row["target"] = targets.get(row.shard)
	return rows


@frappe.whitelist(methods=["GET"])
def tenant_billing(tenant: str) -> dict:
	"""What a workspace is on, and on whose terms.

	The operator's screen of the thing the customer sees on their plan page — plus
	the one fact the customer's page cannot show them: whether the terms they
	hold still match the plan as it stands.
	"""
	_require_manager()
	from oneapp_control.billing import quotas

	doc = frappe.get_doc("Tenant", tenant)
	subscription = (
		frappe.get_doc("Subscription", doc.subscription).as_dict()
		if doc.subscription
		else None
	)

	in_force = quotas.for_tenant(doc)
	current = (
		frappe.db.get_value("Plan", doc.plan, quotas.TERMS, as_dict=True) if doc.plan else None
	) or {}

	return {
		"plan": doc.plan,
		"subscription": subscription,
		"terms": in_force,
		"plan_terms": current,
		# Named rather than left to be spotted: an operator asking "why does this
		# workspace have 50GB when the plan says 20" is asking this question.
		"grandfathered": [
			field for field in quotas.TERMS if (in_force.get(field) or 0) != (current.get(field) or 0)
		],
		"credits": _credit_summary(tenant),
	}


def _credit_summary(tenant: str) -> dict:
	from oneapp_control.credits import ledger

	return {
		"balance": ledger.balance(tenant),
		"available": ledger.available(tenant),
		"history": frappe.get_all(
			"Credit Ledger Entry",
			filters={"tenant": tenant},
			fields=["creation", "entry_type", "credits", "expires_on", "remarks"],
			order_by="creation desc",
			limit=50,
		),
	}


@frappe.whitelist(methods=["POST"])
def grant_credits(tenant: str, credits: float, reason: str) -> dict:
	"""Put credits on a workspace by hand.

	Nothing else in the system can. Credits arrive from a paid invoice or a
	purchased pack, and both are Stripe telling us something happened — so a
	goodwill credit, a migration allowance or a demo top-up had no path at all
	and would have meant opening the desk, which this product does not do
	(docs/ONEADMIN.md, No desk).

	A reason is required and lands on the ledger row. The ledger is append-only
	and an entry with no explanation is one nobody can audit six months later;
	this is the one entry type a person creates, so it is the one that most needs
	saying why.

	Posted as `Adjustment` rather than `Grant`: a Grant is what a plan gives and
	expires at the period end, and this should not quietly evaporate. It never
	expires, so it is spent after everything else — `open_grants` orders
	never-expiring last — which is the right order for something given away.
	"""
	_require_manager()
	from oneapp_control.credits import ledger

	amount = float(credits or 0)
	if not amount:
		frappe.throw(_("Nothing to grant."))
	if not (reason or "").strip():
		frappe.throw(_("Say why. It goes on the ledger and somebody will read it."))

	entry = ledger.post_entry(
		tenant=tenant,
		entry_type="Adjustment",
		credits=amount,
		expires_on=None,
		source_doctype="User",
		source_name=frappe.session.user,
		remarks=f"{reason.strip()} — by {frappe.session.user}",
	)
	return {"entry": entry.name if hasattr(entry, "name") else None, "credits": amount}


@frappe.whitelist(methods=["POST"])
def adopt_plan_terms(tenant: str) -> dict:
	"""Move a workspace onto its plan's terms as they stand now.

	The deliberate half of grandfathering. Quotas are captured when a
	subscription is sold precisely so a plan edit cannot move an existing
	customer; this is how an operator moves one on purpose — handing someone the
	newer, larger plan without making them re-subscribe.
	"""
	_require_manager()
	from oneapp_control.billing import quotas

	subscription = frappe.db.get_value("Tenant", tenant, "subscription")
	if not subscription:
		frappe.throw(_("This workspace has no subscription to move."))

	return quotas.adopt_current_terms(subscription)


@frappe.whitelist(methods=["POST"])
def set_tenant_plan(tenant: str, plan: str, interval: str = "Monthly") -> dict:
	"""Change a workspace's plan on the operator's authority.

	Same path the customer's own switch takes, so the fit check, the proration
	and the Frappe Cloud site plan all behave identically — an operator moving
	someone should not be a second, subtly different implementation.
	"""
	_require_manager()
	from oneapp_control.billing import checkout

	return checkout.change_plan(tenant, plan, interval)


# --------------------------------------------------------------------------- #
# AI: the model catalogue, the feature registry, and what tenants spent
#
# All of it operable from the console. There is no desk (docs/ONEADMIN.md, No desk), so a model
# that can only be re-priced by editing a doctype is a model nobody re-prices.
# --------------------------------------------------------------------------- #

AI_MODEL_EDITABLE = ("status", "capability", "is_recommended", "markup_override",
                     "display_name", "description")


@frappe.whitelist(methods=["GET"])
def ai_models(capability: str | None = None, provider: str | None = None,
              status: str | None = None) -> list:
	_require_manager()

	filters = {}
	for field, value in (("capability", capability), ("provider", provider),
	                     ("status", status)):
		if value:
			filters[field] = value

	models = frappe.get_all(
		"AI Model",
		filters=filters,
		fields=[
			"name", "display_name", "provider", "model_id", "capability", "status",
			"input_modalities", "output_modalities", "context_window",
			"max_output_tokens", "supports_tools", "supports_reasoning",
			"is_recommended", "markup_override", "source", "last_synced",
			"deprecation_date", "sync_note", "description",
		],
		order_by="provider asc, capability asc, display_name asc",
	)

	# The rate matters more than any other field here: it is the number a markup
	# is applied to, and the one that moves without anyone being told.
	for model in models:
		model["prices"] = frappe.get_all(
			"AI Model Price",
			filters={"parent": model["name"]},
			fields=["kind", "modality", "unit", "cost_usd", "per_units", "tier",
			        "effective_from", "effective_to", "note"],
			order_by="tier asc, idx asc",
		)
	return models


@frappe.whitelist(methods=["POST"])
def sync_ai_models() -> dict:
	"""Refetch models and prices now, rather than waiting for the nightly run."""
	_require_manager()

	from oneapp_control.ai import catalogue

	return catalogue.sync()


@frappe.whitelist(methods=["POST"])
def update_ai_model(model: str, values: str | dict) -> dict:
	"""Change the commercial facts about a model. Not the technical ones.

	Prices, modalities and limits come from the provider and are overwritten on
	the next sync, so letting an operator edit them would be a control that
	silently stops working. What is genuinely ours — whether to sell it, what to
	charge on top, what to call it — is what this writes.
	"""
	_require_manager()

	if isinstance(values, str):
		values = frappe.parse_json(values)

	updates = {k: v for k, v in (values or {}).items() if k in AI_MODEL_EDITABLE}
	if not updates:
		frappe.throw(_("Nothing to change. Prices come from the provider."))

	doc = frappe.get_doc("AI Model", model)
	doc.update(updates)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True, "model": model, "status": doc.status}


@frappe.whitelist(methods=["GET"])
def ai_features() -> list:
	"""Every feature the fleet's apps declare, as reported by tenant sites."""
	_require_manager()

	return frappe.get_all(
		"AI Feature",
		fields=[
			"name", "label", "app", "capability", "status", "tenant_can_disable",
			"allow_prompt_addendum", "default_model", "max_input_tokens",
			"max_output_tokens", "max_images", "max_outputs", "max_audio_seconds",
			"max_credits",
			"description", "last_seen",
		],
		order_by="app asc, label asc",
	)


AI_FEATURE_EDITABLE = ("status", "default_model", "max_input_tokens",
                       "max_output_tokens", "max_images", "max_outputs",
                       "max_audio_seconds", "max_credits")


@frappe.whitelist(methods=["POST"])
def update_ai_feature(feature: str, values: str | dict) -> dict:
	"""Pin a model, tighten a ceiling, or take a feature off the air.

	`tenant_can_disable` is absent from the editable set on purpose: whether a
	workflow can run without AI is a property of the code, declared by the app
	that has to keep working, and an operator flipping it here would be
	overruling the only thing that knows.
	"""
	_require_manager()

	if isinstance(values, str):
		values = frappe.parse_json(values)

	updates = {k: v for k, v in (values or {}).items() if k in AI_FEATURE_EDITABLE}
	if not updates:
		frappe.throw(_("Nothing to change."))

	doc = frappe.get_doc("AI Feature", feature)
	doc.update(updates)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True, "feature": feature, "status": doc.status}


@frappe.whitelist(methods=["GET"])
def ai_usage(tenant: str | None = None, limit: int = 50) -> list:
	"""Recent calls, with the gateway's verdict where it has arrived."""
	_require_manager()

	return frappe.get_all(
		"AI Usage Record",
		filters={"tenant": tenant} if tenant else {},
		fields=["name", "tenant", "feature", "model", "provider", "credits_charged",
		        "cost_usd", "markup", "cached", "gateway_log_id",
		        "gateway_cost_usd", "reconciled_on", "recon_note", "creation"],
		order_by="creation desc",
		limit=min(int(limit or 50), 200),
	)


@frappe.whitelist(methods=["GET"])
def ai_settings() -> dict:
	"""The gateway's own configuration, and how fresh the catalogue is."""
	_require_manager()

	conf = frappe.get_single("OneSpace Control Settings")
	return {
		"cf_account_id": conf.cf_account_id,
		"ai_gateway": conf.ai_gateway,
		"markup": conf.ai_markup_multiplier,
		"synced_on": conf.ai_catalogue_synced_on,
		"note": conf.ai_catalogue_note,
		# Configured means a sync can run at all. Said plainly because the
		# alternative is an empty catalogue with no explanation.
		"has_cloudflare": bool(conf.cf_account_id
		                       and conf.get_password("cf_api_token", raise_exception=False)),
		"has_google": bool(conf.get_password("google_ai_key", raise_exception=False)),
		# Counted in Python rather than grouped in SQL: frappe.get_all rejects
		# an aggregate written as a string, and the catalogue is a few hundred
		# rows at most.
		"counts": _tally(frappe.get_all("AI Model", pluck="status")),
	}


def _tally(values) -> dict:
	counts: dict[str, int] = {}
	for value in values:
		counts[value] = counts.get(value, 0) + 1
	return counts


@frappe.whitelist(methods=["POST"])
def set_ai_markup(markup: float) -> dict:
	"""The multiplier applied to every model that does not override it."""
	_require_manager()

	markup = float(markup)
	if markup <= 0:
		frappe.throw(_("Markup must be greater than zero."))

	frappe.db.set_single_value("OneSpace Control Settings", "ai_markup_multiplier", markup)
	frappe.db.commit()
	return {"ok": True, "markup": markup}


@frappe.whitelist(methods=["POST"])
def reconcile_ai_usage() -> dict:
	"""Run the comparison against the gateway's logs now."""
	_require_manager()

	from oneapp_control.ai import reconcile

	return reconcile.run()


# --------------------------------------------------------------------------- #
# App screens
#
# An app is configuration before it is code: a screen names a doctype and the
# fields worth showing, and OneSpace renders it from the tenant site's own
# metadata. So this is where an app gets built, and it has to be reachable
# without the desk like everything else.
# --------------------------------------------------------------------------- #

APP_VIEW_FIELDS = ("screen", "label", "icon", "document_type", "fields",
                   "component", "filters", "order_by")


@frappe.whitelist(methods=["GET"])
def app_views(app: str) -> list:
	_require_manager()

	return frappe.get_all(
		"OneSpace Space Screen",
		filters={"parent": app, "parenttype": "OneSpace Space"},
		fields=["name", *APP_VIEW_FIELDS, "idx"],
		order_by="idx asc",
	)


@frappe.whitelist(methods=["POST"])
def set_app_views(app: str, screens: str | list) -> dict:
	"""Replace an app's screens with what was sent.

	Replaced rather than patched: the order of these is the order of the app's
	navigation, so a partial update would need a second way to express it.
	"""
	_require_manager()

	if isinstance(screens, str):
		screens = frappe.parse_json(screens)
	if not isinstance(screens, list):
		frappe.throw(_("Expected a list of screens."))

	slugs = [str(row.get("screen") or "").strip() for row in screens]
	if not all(slugs):
		frappe.throw(_("Every screen needs a slug — it is what a bookmark points at."))
	if len(set(slugs)) != len(slugs):
		frappe.throw(_("Two screens share a slug, so one of them is unreachable."))

	doc = frappe.get_doc("OneSpace Space", app)
	doc.set("screens", [
		{field: row.get(field) for field in APP_VIEW_FIELDS} for row in screens
	])
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"ok": True, "screens": len(screens)}


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
# The ladder runs on a timer and destroys data at the end of it, so an operator
# needs four things it cannot get from editing a field: a way to stop it, a way
# to run it now on one workspace, a way to take a copy on demand, and a way to
# bring one back. All four are here rather than on a form, because each is a
# decision with a consequence and the confirmation text is part of it.

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
