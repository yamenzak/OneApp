"""Shards and benches: what capacity there is, and what runs on it."""

import frappe
import json
from frappe import _
from oneapp_control.control_plane.doctype.shard.shard import capacity_report
from .guard import _require_manager
from .press import _degrade, _site_plans


@frappe.whitelist()
def shards() -> list:
	_require_manager()
	return capacity_report()


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
