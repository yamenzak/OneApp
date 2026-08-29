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
	"""Whether a bench group is safe for the development tooling to touch.

	`scripts/live.py` patches code on a running bench and redeploys it. Both are
	fine over staging tenants and unacceptable over a customer's workspace, and
	the two can share a bench group: sites move onto a new bench individually, so
	staging can run ahead while production stays put.

	The rule is simply that a group carrying any Production tenant is off limits.
	Read here rather than guessed by the script, because the control plane is the
	only thing that knows which tenant is which.
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
