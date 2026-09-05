"""Which Frappe apps a tenant's site carries.

Three different lists, easy to conflate, and conflating them is what this
module exists to stop:

* **The bench** carries a superset. `Shard.site_apps` is a fact about a press
  release group — what has been built into its image — and every site on that
  bench may draw from it. Nothing outside it can ever be installed.
* **The site** carries a subset. `Tenant.site_apps` is what press actually
  installed, written by provisioning and by nobody else.
* **The grants** imply a third list. A space declares `requires_apps`, and the
  union of what a workspace's spaces need is what its site *ought* to carry.

Until this existed the first list was doing all three jobs: every site on a
bench got every app on it, whether the workspace had bought anything that used
it or not, and a space granted onto a site without its app produced screens
that were simply empty — `sync_permissions` skips a doctype the site lacks and
`_columns` skips a field, both deliberately and both silently.

So: a grant is refused when the bench cannot carry the space, and satisfied by
an Install App job when the bench can and the site has not got there yet.
"""

import frappe
from frappe import _

from oneapp_control.entitlements import registry


def declared(raw) -> list[str]:
	"""The app names in a `requires_apps` field."""
	return [one.strip() for one in str(raw or "").replace("\n", ",").split(",") if one.strip()]


def required_by(space: dict) -> list[str]:
	return declared(space.get("requires_apps"))


def wanted_for(tenant: str) -> list[str]:
	"""Every app this workspace's spaces are written against, plus the base."""
	wanted = set(registry.BASE_APPS)
	for space in registry.spaces_for_tenant(tenant):
		wanted.update(required_by(space))
	return sorted(wanted)


def installed_on(tenant) -> list[str]:
	"""What press has actually put on the site.

	Empty before provisioning, which is the honest answer: there is no site.
	Callers deciding whether to install something check `press_site` rather than
	reading emptiness as "nothing installed".
	"""
	doc = _tenant(tenant)
	return declared(doc.site_apps)


def bench_apps(tenant) -> list[str]:
	"""The ceiling — what the shard's bench was built with."""
	from oneapp_control.provisioning.steps import site_apps

	doc = _tenant(tenant)
	if not doc.shard:
		return []
	return site_apps(frappe.get_doc("Shard", doc.shard))


def missing_from_bench(tenant, apps: list[str]) -> list[str]:
	carried = set(bench_apps(tenant))
	return [app for app in apps if app not in carried]


def missing_from_site(tenant, apps: list[str]) -> list[str]:
	have = set(installed_on(tenant))
	return [app for app in apps if app not in have]


def assert_can_carry(tenant: str, space_code: str) -> None:
	"""Refuse a grant the tenant's bench cannot support, naming the app.

	The bench and not the site, because the site is fixable — that is what
	`reconcile` does — and the bench is not, at least not from here. Moving a
	tenant to a shard whose bench has the app, or building the app into this
	one, is an operator's decision about capacity and takes a deploy.
	"""
	needed = declared(frappe.db.get_value("OneSpace Space", space_code, "requires_apps"))
	if not needed:
		return

	doc = _tenant(tenant)
	if not doc.shard:
		# Nothing to check against yet. Provisioning picks the shard, and
		# `apps_for_site` refuses there if the one it picked cannot carry this.
		return

	missing = missing_from_bench(doc, needed)
	if missing:
		frappe.throw(
			_(
				"{0} needs {1}, which the bench {2} sits on does not carry. "
				"Move the workspace to a shard whose bench has it, or add it to "
				"that bench, and grant this again."
			).format(
				frappe.db.get_value("OneSpace Space", space_code, "space_label") or space_code,
				", ".join(missing),
				doc.shard,
			),
			title=_("This site cannot carry that space"),
		)


def reconcile(tenant: str) -> list[str]:
	"""Install onto a live site whatever its grants now need, and say which.

	Nothing to do before provisioning: `create_site` installs the union in one
	go, which is a great deal cheaper than installing them one at a time
	afterwards. Nothing to do either where the app is already there.

	Each app is its own job, with its own idempotency key. Installing an app is
	a migration on a running site — minutes, and it can fail — so two of them
	failing together in one job would leave nothing to say which.
	"""
	from oneapp_control.provisioning import runner

	doc = _tenant(tenant)
	if not doc.press_site:
		return []

	# What the bench cannot carry is not this function's problem: the grant that
	# would need it was refused, and a space granted before its app was declared
	# should not wedge every later install behind a job that can only fail.
	carried = set(bench_apps(doc))
	missing = [app for app in missing_from_site(doc, wanted_for(tenant)) if app in carried]

	for app in missing:
		runner.enqueue(
			tenant,
			"Install App",
			payload={"app": app},
			idempotency_key=f"Install App:{tenant}:{app}",
		)
	return missing


def record_installed(tenant, apps: list[str]) -> None:
	"""Write what the site now carries. Provisioning's job and nobody else's."""
	doc = _tenant(tenant)
	have = set(installed_on(doc)) | {app for app in apps if app}
	doc.db_set("site_apps", ",".join(sorted(have)), update_modified=False)


def _tenant(tenant):
	return tenant if hasattr(tenant, "doctype") else frappe.get_doc("Tenant", tenant)
