"""What needs a person, in one place.

The console had thirty-two screens and no way to say that anything was wrong.
Twenty of them were machine state or an audit trail — a provisioning job, a
webhook, a standby pool — and the only way to find a problem in one was to
remember to open it. That is not a console, it is a filing cabinet.

So: every condition that wants a human, assembled from queries the crons
already run, in one list. Each check is a function returning zero or more rows;
the registry below is the whole of it, and adding a condition is adding a
function and a line.

**Three rules the checks keep.**

*Cheap.* This runs on a page load and in a daily email. Every check is one
indexed query or a cached press read; nothing here fetches a site.

*Silent when there is nothing to say.* A check returning `[]` contributes
nothing, and a day with no rows sends no email. A console that cries wolf is a
console nobody opens, which is the failure mode this is meant to fix.

*Never raises.* One check that cannot reach press must not take the page with
it. `rows()` catches per check and reports the failure as a row of its own,
because a check that stopped working is itself something a person should know.

The severities are `blocking` (a customer is affected now), `warning` (they
will be), and `notice` (worth knowing before it becomes either).
"""

import frappe
from frappe.utils import add_to_date, now_datetime

#: How long a signup may sit unfinished before somebody should look. Long
#: enough that a slow Stripe redirect and a provisioning run both fit inside it.
SIGNUP_HOURS = 6

#: How far back the failed-backup check reads its own sweep's findings. The
#: sweep runs daily and writes a `Backup Failed` event; two days' worth catches
#: the case where the sweep itself missed a night.
BACKUP_DAYS = 2


def _row(key, severity, title, detail, *, screen="", count=0, record=""):
	return {
		"key": key,
		"severity": severity,
		"title": title,
		"detail": detail,
		"screen": screen,
		"record": record,
		"count": count,
	}


# --------------------------------------------------------------------------- #
# Provisioning and the fleet
# --------------------------------------------------------------------------- #

def stuck_provisioning() -> list[dict]:
	"""A job the runner has given up on, or is about to.

	`runner.advance` retries a transient failure twelve times with a backoff to
	half an hour, so a job still Requested after all of them is not slow — it
	is a job nobody will move without help.
	"""
	from oneapp_control.provisioning.runner import MAX_ATTEMPTS

	failed = frappe.get_all(
		"Provisioning Job",
		filters={"state": "Failed"},
		fields=["name", "tenant", "action", "last_error"],
		limit=25,
	)
	rows = [
		_row(
			f"job:{job['name']}",
			"blocking",
			f"{job['action']} failed for {job['tenant'] or 'a workspace'}",
			(job["last_error"] or "").strip()[:200] or "No error was recorded.",
			screen="provisioning",
			record=job["name"],
		)
		for job in failed
	]

	tiring = frappe.db.count(
		"Provisioning Job",
		{"state": ("in", ("Requested", "Running", "Awaiting Agent", "Bootstrapping")),
		 "attempts": (">=", MAX_ATTEMPTS - 2)},
	)
	if tiring:
		rows.append(_row(
			"job:attempts", "warning",
			f"{tiring} provisioning job(s) are near their last attempt",
			"Two more failures and each of these stops retrying.",
			screen="provisioning", count=tiring,
		))
	return rows


def no_capacity() -> list[dict]:
	"""Nowhere to put the next signup.

	The allocator's own filter, asked as a question rather than discovered when
	a customer has already paid.
	"""
	usable = frappe.db.sql(
		"""SELECT COUNT(*) FROM `tabShard`
		   WHERE status = 'Active' AND accepts_new_tenants = 1
		     AND (capacity_tenants = 0 OR tenant_count < capacity_tenants)"""
	)[0][0]
	if usable:
		return []
	return [_row(
		"shard:none", "blocking",
		"No shard can take a new workspace",
		"Every shard is full, paused or inactive. The next signup will fail "
		"after the customer has paid.",
		screen="shards",
	)]


def full_shards() -> list[dict]:
	rows = frappe.db.sql(
		"""SELECT name, tenant_count, capacity_tenants FROM `tabShard`
		   WHERE status = 'Active' AND capacity_tenants > 0
		     AND tenant_count >= capacity_tenants""",
		as_dict=True,
	)
	return [
		_row(
			f"shard:{row['name']}", "warning",
			f"{row['name']} is full",
			f"{row['tenant_count']} of {row['capacity_tenants']}. Add capacity "
			"or this region stops being offered at signup.",
			screen="shards", record=row["name"],
		)
		for row in rows
	]


def standby_short() -> list[dict]:
	"""A warm pool below what its shard asks for.

	Not an incident — a signup falls back to building a site — but a signup
	that waits four minutes instead of forty seconds, which is worth knowing
	before a launch rather than during one.
	"""
	short = []
	for shard in frappe.get_all(
		"Shard",
		filters={"status": "Active", "standby_target": (">", 0)},
		fields=["name", "standby_target"],
	):
		ready = frappe.db.count(
			"Standby Site", {"shard": shard["name"], "status": "Ready"}
		)
		if ready < shard["standby_target"]:
			short.append((shard["name"], ready, shard["standby_target"]))

	if not short:
		return []
	worst = ", ".join(f"{name} {ready}/{target}" for name, ready, target in short[:4])
	return [_row(
		"standby:short", "notice",
		f"{len(short)} shard(s) have a warm pool below target",
		f"{worst}. Signups there build a site instead of claiming one.",
		screen="standby", count=len(short),
	)]


def broken_standby() -> list[dict]:
	count = frappe.db.count("Standby Site", {"status": "Broken"})
	if not count:
		return []
	return [_row(
		"standby:broken", "warning",
		f"{count} standby site(s) are broken",
		"These are paid-for sites nobody can claim. Archive them or find out why.",
		screen="standby", count=count,
	)]


def unbacked_regions() -> list[dict]:
	"""A region customers can choose whose cluster press no longer offers.

	Not fixed automatically: tenants live in these, and the answer is a
	migration rather than a flag flip. `regions.sync_from_press` deliberately
	never deletes for the same reason.
	"""
	from oneapp_control.provisioning import regions

	stray = regions.unbacked()
	if not stray:
		return []
	return [_row(
		"region:unbacked", "warning",
		f"{len(stray)} region(s) name a cluster Frappe Cloud no longer offers",
		", ".join(stray) + ". A signup here places a tenant nowhere.",
		screen="regions", count=len(stray),
	)]


def orphan_sites() -> list[dict]:
	"""A site on the Frappe Cloud account with no workspace against it.

	This is the whole reason the Sites screen existed. It is a comparison
	between two lists, which is a query rather than something to scan for.
	"""
	from oneapp_control.press import records

	known = set(records.tenants_by_site().keys())
	orphans = [
		site["name"]
		for site in records.sites()
		if site.get("name") and site["name"] not in known
	]
	if not orphans:
		return []
	return [_row(
		"press:orphans", "notice",
		f"{len(orphans)} Frappe Cloud site(s) have no workspace",
		", ".join(sorted(orphans)[:5])
		+ ("…" if len(orphans) > 5 else "")
		+ ". Either a provisioning run half-finished, or somebody made a site by hand.",
		screen="sites", count=len(orphans),
	)]


# --------------------------------------------------------------------------- #
# Money
# --------------------------------------------------------------------------- #

def failed_webhooks() -> list[dict]:
	count = frappe.db.count("Stripe Webhook Event", {"status": "Failed"})
	if not count:
		return []
	return [_row(
		"stripe:failed", "blocking",
		f"{count} Stripe webhook(s) failed",
		"A subscription, a payment or a cancellation has not been applied. "
		"Replay them from the Webhooks screen.",
		screen="webhooks", count=count,
	)]


def stalled_signups() -> list[dict]:
	cutoff = add_to_date(now_datetime(), hours=-SIGNUP_HOURS)
	rows = frappe.get_all(
		"Account Request",
		filters={
			"status": ("in", ("Paid", "Provisioning")),
			"tenant": ("in", ("", None)),
			"creation": ("<", cutoff),
		},
		fields=["name", "email", "workspace_name"],
		limit=25,
	)
	return [
		_row(
			f"signup:{row['name']}", "blocking",
			f"{row['email']} paid and has no workspace",
			f"{row['workspace_name'] or 'Unnamed'} — paid more than "
			f"{SIGNUP_HOURS} hours ago and provisioning never finished.",
			screen="signups", record=row["name"],
		)
		for row in rows
	]


def failed_signups() -> list[dict]:
	count = frappe.db.count("Account Request", {"status": "Failed"})
	if not count:
		return []
	return [_row(
		"signup:failed", "warning",
		f"{count} signup(s) failed",
		"Each of these is somebody who tried to buy and could not.",
		screen="signups", count=count,
	)]


# --------------------------------------------------------------------------- #
# Workspaces
# --------------------------------------------------------------------------- #

def over_quota() -> list[dict]:
	rows = frappe.get_all(
		"Tenant",
		filters={"over_quota_since": ("is", "set"), "status": "Active"},
		fields=["name", "tenant_name", "over_quota_since"],
		limit=25,
	)
	return [
		_row(
			f"quota:{row['name']}", "warning",
			f"{row['tenant_name']} is over quota",
			f"Since {row['over_quota_since']}. Grace ends, and then writes stop.",
			screen="tenants", record=row["name"],
		)
		for row in rows
	]


def in_dunning() -> list[dict]:
	rows = frappe.get_all(
		"Tenant",
		filters={"dunning_stage": ("is", "set")},
		fields=["name", "tenant_name", "dunning_stage"],
		limit=25,
	)
	return [
		_row(
			f"dunning:{row['name']}", "warning",
			f"{row['tenant_name']} is in dunning",
			f"Stage {row['dunning_stage']}. The ladder ends in suspension.",
			screen="tenants", record=row["name"],
		)
		for row in rows
	]


def stale_backups() -> list[dict]:
	"""What `backups.staleness_sweep` found, rather than a second opinion.

	The sweep already knows each workspace's interval and writes a
	`Backup Failed` event when two slots go by without one. Reading its events
	keeps one rule in one place.
	"""
	cutoff = add_to_date(now_datetime(), days=-BACKUP_DAYS)
	names = frappe.get_all(
		"Tenant Lifecycle Event",
		filters={"event": "Backup Failed", "occurred_on": (">=", cutoff)},
		pluck="tenant",
		limit=200,
	)
	unique = sorted(set(name for name in names if name))
	if not unique:
		return []
	return [_row(
		"backup:stale", "warning",
		f"{len(unique)} workspace(s) have not backed up",
		", ".join(unique[:5]) + ("…" if len(unique) > 5 else "")
		+ ". A missing backup is invisible until somebody asks for a restore.",
		screen="tenants", count=len(unique),
	)]


# --------------------------------------------------------------------------- #
# The registry
# --------------------------------------------------------------------------- #

#: Every check, in the order a person should read them. Ordering here rather
#: than sorting by severity: two blocking rows about the same incident read
#: better adjacent than interleaved with an unrelated one.
CHECKS = (
	("provisioning", stuck_provisioning),
	("capacity", no_capacity),
	("shards", full_shards),
	("stripe", failed_webhooks),
	("signups", stalled_signups),
	("signups-failed", failed_signups),
	("quota", over_quota),
	("dunning", in_dunning),
	("backups", stale_backups),
	("standby-broken", broken_standby),
	("standby", standby_short),
	("regions", unbacked_regions),
	("press", orphan_sites),
)

RANK = {"blocking": 0, "warning": 1, "notice": 2}


def rows() -> list[dict]:
	"""Everything that needs a person, worst first.

	A check that raises becomes a row rather than an exception: a console that
	goes blank because Frappe Cloud is unreachable has told you nothing, and
	"the press check is broken" is itself worth reading.
	"""
	found: list[dict] = []
	for name, check in CHECKS:
		try:
			found.extend(check() or [])
		except Exception:
			frappe.log_error(
				title=f"Attention check '{name}' failed",
				message=frappe.get_traceback(),
			)
			found.append(_row(
				f"check:{name}", "notice",
				f"The '{name}' check could not run",
				"Its answer is missing from this list. See the error log.",
			))
	found.sort(key=lambda row: RANK.get(row["severity"], 3))
	return found


@frappe.whitelist()
def board() -> dict:
	"""What the screen renders: the rows and a count per severity."""
	from oneapp_control.api.admin.guard import _require_manager

	_require_manager()
	found = rows()
	return {
		"rows": found,
		"counts": {
			level: sum(1 for row in found if row["severity"] == level)
			for level in RANK
		},
		"checked_on": str(now_datetime()),
	}


# --------------------------------------------------------------------------- #
# The days it has something to say
# --------------------------------------------------------------------------- #

def _recipients() -> list[str]:
	"""Whoever holds the console. Read from roles rather than configured.

	A settings field for "who gets the email" is a field that goes stale the
	first time somebody leaves, and the answer is already written down: the
	people who can open the console are the people who should be told what is
	in it.
	"""
	return sorted({
		row["parent"]
		for row in frappe.get_all(
			"Has Role",
			filters={"role": "System Manager", "parenttype": "User"},
			fields=["parent"],
		)
		if row["parent"] not in ("Administrator", "Guest")
		and frappe.db.get_value("User", row["parent"], "enabled")
	})


def digest() -> dict:
	"""Daily. Sends nothing on a quiet day, which is the point.

	A console that only shows problems is a console you stop opening, so the
	problems have to come to you. And an email that arrives every morning
	saying "nothing is wrong" is an email that gets filtered, so this one only
	arrives when there is something in it.
	"""
	found = rows()
	if not found:
		return {"sent": 0, "rows": 0}

	people = _recipients()
	if not people:
		return {"sent": 0, "rows": len(found), "note": "nobody to tell"}

	worst = min(RANK.get(row["severity"], 3) for row in found)
	label = next(level for level, rank in RANK.items() if rank == worst)
	lines = [
		f"[{row['severity']}] {row['title']}\n    {row['detail']}"
		for row in found
	]
	url = frappe.utils.get_url("/one/space/onespace-ops?screen=attention")

	frappe.sendmail(
		recipients=people,
		subject=f"OneAdmin: {len(found)} thing(s) need you ({label})",
		message=(
			"<pre style='font:13px/1.5 ui-monospace,monospace'>"
			+ frappe.utils.escape_html("\n\n".join(lines))
			+ f"</pre><p><a href='{url}'>Open the console</a></p>"
		),
		now=True,
	)
	return {"sent": len(people), "rows": len(found)}
