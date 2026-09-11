import frappe
from frappe import _
from frappe.model.document import Document

# What a shard names on Frappe Cloud, and where to look each one up. A shard is
# a (server, bench group) pair plus policy, and the pair half is not ours to
# invent — every one of these has to match a record press already holds.
#
# `press_cluster` is deliberately absent: it is informational, press derives it
# from the server, and a mismatch changes nothing about where a site lands.
PRESS_FIELDS = (
	("press_server", "servers", "name", "server"),
	("press_release_group", "release_groups", "name", "bench group"),
)


def _cheapest_site_plan() -> str:
	"""The least expensive plan press offers, which is the right default.

	A shard exists to hold tenants and a tenant's plan is ours, not press's —
	the press plan is the resource envelope underneath. Starting at the bottom
	is the answer that cannot surprise anybody with a bill; an operator who
	wants more says so.
	"""
	from oneapp_control.press import records

	try:
		plans = records.site_plans()
	except Exception:
		return ""
	priced = [
		row for row in plans
		if isinstance(row, dict) and row.get("name") and (row.get("price_usd") or 0) > 0
	]
	if not priced:
		return ""
	return min(priced, key=lambda row: row.get("price_usd") or 0)["name"]


class Shard(Document):
	def validate(self):
		# Both are None on an unsaved document.
		if self.capacity_tenants and (self.tenant_count or 0) > self.capacity_tenants:
			# Not an error — an operator may deliberately overfill — but it should
			# stop attracting new tenants.
			self.accepts_new_tenants = 0

		self.fill_from_press()
		self.validate_against_press()

	def fill_from_press(self):
		"""Derive what Frappe Cloud already knows, and leave the rest alone.

		A shard is one choice and a handful of decisions, not seventeen fields.
		The server determines the cluster, and an account with a single server
		determines the server. Neither is a judgement, so asking somebody to
		copy them off another screen only creates a chance to get one wrong.

		The version and the app list used to be filled here too, and are now not
		stored at all: `press/records.py` answers both at the moment they are
		used. Filling a field from press on save is still a copy — right on the
		day it was made and wrong the day somebody upgrades the bench.

		**Only ever fills a blank.** A value already set is a deliberate one —
		an operator pinning a shard to a cluster press would not have picked, or
		a shard mid-migration between groups — and `validate_against_press`
		still checks whatever ends up here. Filling is a convenience; refusing a
		wrong answer is the guarantee.

		Silent by design where it cannot help: no server named and several to
		choose from is a real decision, and guessing would put tenants on a
		machine nobody chose.
		"""
		# Nothing named at all still derives, as long as the account leaves no
		# choice: one server and one bench group is not a decision anybody has
		# to make, and refusing to make it for them was an inconsistency rather
		# than a principle.

		flags = frappe.flags
		if any(getattr(flags, f, False) for f in
		       ("in_install", "in_migrate", "in_patch", "in_test", "in_import")):
			return

		known = press_inventory()
		if not known:
			return

		servers = known.get("servers") or []
		groups = known.get("release_groups") or []

		# One of a thing on the account is not a choice, so it does not need to
		# be made. Two or more and it is, so this stays out of it — picking for
		# somebody would put their tenants on a machine, or a bench, nobody
		# chose.
		if not self.get("press_server") and len(servers) == 1:
			self.press_server = servers[0].get("name")

		if not self.get("press_release_group") and len(groups) == 1:
			self.press_release_group = groups[0].get("name")

		# The bench group is the pivot. Press knows which machines it runs on
		# and which clusters it can deploy into, so a group named here settles
		# the server as well — where there is one answer. Two servers in a
		# group is a real choice and this stays out of it, the same rule as
		# above.
		if not self.get("press_server") and self.get("press_release_group"):
			from oneapp_control.press import records

			try:
				candidates = records.servers_of(self.press_release_group)
			except Exception:
				candidates = []
			if len(candidates) == 1:
				self.press_server = candidates[0].get("name")

		if not self.get("press_cluster") and self.get("press_server"):
			match = next(
				(s for s in servers if s.get("name") == self.get("press_server")), None
			)
			if match:
				self.press_cluster = match.get("cluster")

		# And the cluster settles the region, which is the field that made this
		# form ask for something the operator had no way to answer. `regions`
		# keeps one row per cluster press reports — see `sync_from_press` — so
		# this is a lookup rather than a guess.
		if not self.get("region") and self.get("press_cluster"):
			found = frappe.db.get_value("Region", {"press_cluster": self.press_cluster})
			if found:
				self.region = found

		# The default domain and the site plan are press's answers too, and
		# both fail *late* when wrong: a site is created on the wrong host, or
		# creation is refused for a plan that does not exist.
		if not self.get("press_site_plan"):
			self.press_site_plan = _cheapest_site_plan()

	def has_headroom(self) -> bool:
		"""Whether the allocator may place another tenant here.

		Three questions in the order they disqualify: is the shard taking
		anything at all, is it Active, and is it under its soft cap. No cap
		means no ceiling here — MariaDB is the real one and an operator who
		left the field empty said so deliberately.
		"""
		if not self.accepts_new_tenants or self.status != "Active":
			return False
		if not self.capacity_tenants:
			return True
		return (self.tenant_count or 0) < self.capacity_tenants

	def validate_against_press(self):
		"""Refuse a shard naming something Frappe Cloud does not have.

		These are typed by hand, read off a different screen, and both fail
		*late*: press matches a bench by server, version and apps, so a wrong
		value gets several steps into a provision — past `create_site`, with a
		real site already made — and then fails naming the wrong cause.

		The version used to be the worst of them and is no longer here at all:
		press is asked for it when the site is created, so it cannot be wrong.

		Checked here rather than in the form so the API, a script and a fixture
		are held to it too.

		**Only a definite answer refuses.** If press cannot be reached, or has no
		credentials yet, the save is allowed: a shard that cannot be edited
		because Frappe Cloud is briefly down is a worse failure than a typo, and
		the readiness board already reports unreachable credentials.
		"""
		if not (self.press_server or self.press_release_group):
			return

		# Installs, migrations and fixtures must not reach the network.
		flags = frappe.flags
		if any(getattr(flags, f, False) for f in
		       ("in_install", "in_migrate", "in_patch", "in_test", "in_import")):
			return

		known = press_inventory()
		if known is None:
			return

		for field, bucket, key, label in PRESS_FIELDS:
			value = (self.get(field) or "").strip()
			if not value:
				continue

			offered = known.get(bucket) or []
			names = {row.get(key) for row in offered} if key else set(offered)
			if not names or value in names:
				continue

			frappe.throw(
				_("Frappe Cloud has no {0} called {1}. It offers: {2}.").format(
					label, frappe.bold(value), ", ".join(sorted(n for n in names if n))
				),
				title=_("That is not a name Frappe Cloud knows"),
			)


def press_inventory() -> dict | None:
	"""Servers, bench groups and versions as Frappe Cloud has them now.

	Cached for the request, because a save checks three fields and each would
	otherwise be its own round trip. `None` means "could not ask" — never "there
	is nothing there", which is the distinction the caller acts on.
	"""
	cached = getattr(frappe.local, "_oneapp_press_inventory", "unset")
	if cached != "unset":
		return cached

	found = None
	try:
		from oneapp_control.press.client import PressClient

		client = PressClient()
		groups = client.release_groups() or []
		found = {
			"servers": client.servers() or [],
			"release_groups": groups,
			# No separate versions call: a bench group carries its own, and the
			# versions of the groups you have are exactly the set a shard may
			# name — a version press supports but you run no bench on is not a
			# valid answer here.
			"versions": sorted(
				{(g.get("version") or "").strip() for g in groups} - {""}
			),
		}
	except Exception as e:
		# No credentials yet, or Frappe Cloud is unreachable. Both are reported
		# by the readiness board; neither should stop a shard being saved.
		frappe.log_error(
			title="Could not check a shard against Frappe Cloud",
			message=f"{type(e).__name__}: {e}",
		)

	frappe.local._oneapp_press_inventory = found
	return found


def pick_shard(region: str | None = None) -> str | None:
	"""Choose where a new tenant's site should live.

	Least-loaded first among shards that are Active, accepting, and below their
	soft cap. Canary is excluded — it carries internal tenants only, and its whole
	purpose is to take migrations before customers do.

	Returns None when nothing has headroom, which the caller must treat as a
	capacity incident rather than silently placing the tenant anyway.
	"""
	# A region choice is the customer's, so it is never silently overridden by
	# the configured default.
	if not region:
		configured = frappe.db.get_single_value("OneSpace Control Settings", "default_shard")
		if configured and frappe.db.exists("Shard", configured):
			shard = frappe.get_cached_doc("Shard", configured)
			if shard.has_headroom():
				return shard.name

	# `deploy_ring` used to be here as `!= 'Canary'`, which is the same
	# sentence as `accepts_new_tenants = 0` said twice: Wave 1, Wave 2 and
	# Fleet were indistinguishable to every query in the product, so the field
	# was a four-value Select doing a checkbox's job and a shard could be
	# excluded two ways that had to agree.
	filters = {
		"status": "Active",
		"accepts_new_tenants": 1,
	}
	if region:
		filters["region"] = region

	candidates = frappe.get_all(
		"Shard",
		filters=filters,
		fields=["name", "tenant_count", "capacity_tenants"],
		order_by="tenant_count asc",
	)

	for row in candidates:
		if not row.capacity_tenants or (row.tenant_count or 0) < row.capacity_tenants:
			return row.name

	return None


def regions_with_capacity() -> list[dict]:
	"""Regions a customer may currently choose.

	A region with no headroom is not offered rather than accepted and then
	failed at provisioning.
	"""
	rows = frappe.db.sql(
		"""
		SELECT r.name AS code, r.region_name, r.country, r.description
		FROM `tabRegion` r
		WHERE r.is_active = 1
		  AND EXISTS (
			SELECT 1 FROM `tabShard` s
			WHERE s.region = r.name
			  AND s.status = 'Active'
			  AND s.accepts_new_tenants = 1
			  AND (s.capacity_tenants = 0 OR s.tenant_count < s.capacity_tenants)
		  )
		ORDER BY r.sort_order ASC, r.region_name ASC
		""",
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def capacity_report() -> list[dict]:
	"""Operational screen: how full is each shard."""
	rows = frappe.get_all(
		"Shard",
		fields=[
			"name", "status", "tenant_count", "capacity_tenants",
			"accepts_new_tenants", "press_release_group", "region",
		],
		order_by="region asc, name asc",
	)

	for row in rows:
		cap = row.capacity_tenants or 0
		row["utilisation"] = round((row.tenant_count or 0) / cap, 3) if cap else None

	return rows
