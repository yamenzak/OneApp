"""Keep this site's screen of its tenant fresh.

The control plane is authoritative; this site caches. The cache is a Single
doctype rather than only Redis, deliberately: if the control plane is
unreachable, a tenant should keep working with the last known entitlements
rather than have every app vanish from their launcher.
"""

import json

import frappe
from frappe.utils import now_datetime

from oneapp.oneapp_core import control_client, site

CACHE_KEY = "onespace_site_state"
CACHE_TTL = 300


def _spaces(payload: dict) -> list:
	"""The spaces in a sync payload, under either name.

	The control plane sent `apps` and sends `spaces`. Both ends are ours but
	they deploy separately, and a tenant that reads only the new key would
	answer a sync by forgetting every space it has.
	"""
	found = payload.get("spaces")
	if found is None:
		found = payload.get("apps")
	return found or []


def state() -> dict:
	"""Cached tenant state. Falls back to the durable copy, then to empty."""
	cached = frappe.cache().get_value(CACHE_KEY)
	if cached:
		return cached

	doc = frappe.get_single("OneSpace Site State")
	data = {
		"tenant": doc.tenant,
		"status": doc.status,
		"plan_code": doc.plan_code,
		"storage_quota_bytes": doc.storage_quota_bytes or 0,
		"database_quota_bytes": doc.database_quota_bytes or 0,
		"max_users": doc.max_users or 0,
		"background_workers": doc.background_workers or 0,
		"backups_per_day": doc.backups_per_day or 0,
		"quota": json.loads(doc.quota_json or "{}"),
		"credit_balance": doc.credit_balance or 0,
		"spaces": json.loads(doc.spaces_json or "[]") + local_spaces(),
		"roles": json.loads(doc.roles_json or "[]"),
		"last_sync": str(doc.last_sync) if doc.last_sync else None,
	}
	frappe.cache().set_value(CACHE_KEY, data, expires_in_sec=CACHE_TTL)
	return data


def local_spaces() -> list:
	"""Spaces this site provides itself, rather than being told about.

	A tenant learns which spaces it has from the control plane, over HMAC, and
	caches the answer in the Single above. The control plane has no control
	plane to ask — it *is* one — so it needs a second way to say the same thing,
	and an app installed there registers a provider:

	    onespace_space_providers = ["oneapp_control.…:local_spaces"]

	Each returns the same list of space dicts the sync payload carries, so
	everything downstream — `_space`, `_granted_doctypes`, `visible_spaces`, the
	rail, the resolver — is untouched and cannot tell the two apart. Which is
	the point: a space is a space, and where the description came from is not a
	property of it.

	`oneapp` ships no provider. A site with none and no sync has no spaces,
	which is what it had before this existed.

	A provider that raises is skipped rather than fatal. This runs behind every
	page load of the shell, and one app's bad manifest should not be a site that
	will not open.
	"""
	found = []
	for path in frappe.get_hooks("onespace_space_providers") or []:
		try:
			found += frappe.get_attr(path)() or []
		except Exception:
			frappe.log_error(title="OneSpace space provider failed", message=path)
	return found


def invalidate():
	frappe.cache().delete_value(CACHE_KEY)


def sync_from_control_plane() -> dict:
	"""Pull entitlements, quotas and balance. Scheduled, and callable on demand."""
	if site.is_control():
		# The control plane has no control plane to ask. Answered here rather
		# than left to fail as "not provisioned", which is a different thing and
		# would leave a misleading error on the singleton every fifteen minutes.
		return {"ok": True, "reason": "not_a_tenant"}

	doc = frappe.get_single("OneSpace Site State")

	if not control_client.is_provisioned():
		doc.db_set("last_sync_error", "Site is not provisioned (missing site_config keys).")
		return {"ok": False, "reason": "not_provisioned"}

	try:
		payload = control_client.sync()
	except control_client.ControlPlaneError as e:
		# Keep serving the last known good state rather than degrading the site.
		doc.db_set("last_sync_error", str(e)[:500])
		frappe.log_error(title="OneSpace control-plane sync failed", message=str(e))
		return {"ok": False, "reason": "unreachable", "error": str(e)}

	tenant = payload.get("tenant") or {}
	plan = payload.get("plan") or {}
	credits = payload.get("credits") or {}

	doc.db_set(
		{
			"tenant": tenant.get("slug"),
			"site_name": tenant.get("site_name"),
			"status": tenant.get("status"),
			"plan_code": plan.get("code"),
			"storage_quota_bytes": plan.get("storage_quota_bytes") or 0,
			"database_quota_bytes": plan.get("database_quota_bytes") or 0,
			"max_users": plan.get("max_users") or 0,
			"background_workers": plan.get("background_workers") or 0,
			"backups_per_day": plan.get("backups_per_day") or 0,
			# Whether to enforce quotas at all, and until when if not. Stored
			# rather than only cached: an unreachable control plane must not
			# silently re-block a workspace that was given a window.
			"quota_json": json.dumps(payload.get("quota") or {}),
			"credit_balance": credits.get("balance") or 0,
			"spaces_json": json.dumps(_spaces(payload)),
			"roles_json": json.dumps(payload.get("roles") or []),
			"last_sync": now_datetime(),
			"last_sync_error": None,
		}
	)

	invalidate()
	sync_roles(
		payload.get("roles") or [],
		payload.get("owner_role"),
		payload.get("member_role"),
	)
	sync_permissions(payload.get("permissions") or [])
	created = sync_owner(
		payload.get("owner") or {},
		payload.get("owner_role"),
		payload.get("member_role"),
	)
	# After the owner: an Admin member is given the owner role, which must exist
	# by then, and the reconciliation must not mistake the owner for a removal.
	people = sync_members(
		payload.get("members") or [],
		payload.get("owner_role"),
		payload.get("member_role"),
		(payload.get("owner") or {}).get("email") or "",
	)
	sync_email_account()
	sync_backup_request(payload.get("backup") or {})
	sync_branding(tenant)
	books = sync_books(payload.get("books"))
	sync_ai(payload.get("ai") or {}, credits)

	return {
		"ok": True,
		"spaces": len(_spaces(payload)),
		"owner_created": created,
		"members_created": people["created"],
		"members_disabled": people["disabled"],
		"books": books,
	}


def sync_backup_request(block: dict) -> None:
	"""Take a final full backup, if the control plane has asked for one.

	This is how a workspace about to be archived gets a copy it can be restored
	from. Enqueued rather than run inline: a full backup of a large workspace is
	minutes of dumping and tarring, and the sync job also creates users, writes
	permissions and reconciles the email account — holding all of that behind a
	tarball would turn one slow backup into a site that looks stuck.

	No guard against asking twice. The control plane clears the flag the moment
	the copy is promoted, so the worst a duplicate costs is one extra backup,
	and refusing one would mean a failed upload could never be retried.
	"""
	if not block.get("requested"):
		return

	from oneapp.oneapp_core import backup

	try:
		frappe.enqueue(
			backup.run_backup,
			queue="long",
			timeout=3600,
			with_files=True,
			job_id=f"oneapp-cold-backup-{frappe.local.site}",
			deduplicate=True,
		)
	except Exception:
		# An older Frappe without `deduplicate`, or no worker to enqueue onto.
		# Taking it inline is slower than we would like and better than not
		# taking it at all — this is the copy that decides whether a workspace
		# can be brought back.
		frappe.log_error(
			title="Cold backup could not be enqueued; taking it inline",
			message=frappe.get_traceback(),
		)
		backup.run_backup(with_files=True)


def sync_ai(block: dict, credits: dict) -> None:
	"""Cache the model catalogue and the platform's feature policy, then report
	back what this site declares.

	Cached rather than fetched per call so the settings page renders and a model
	stays chosen while the control plane is unreachable. It is never used to
	price a call — that happens on the control plane, against the same rows.

	Reporting is the other half of autodiscovery: features exist only in app
	code, so an operator would otherwise have no way to know what a site can do.
	"""
	from oneapp.oneapp_core.ai import features

	try:
		frappe.db.set_single_value("OneSpace AI Settings", {
			"catalogue_json": json.dumps(block.get("models") or [], default=str),
			"registry_json": json.dumps(block.get("features") or [], default=str),
			"credit_balance": credits.get("balance") or 0,
			"last_sync": now_datetime(),
		})
	except Exception:
		# A site whose AI settings will not write is still a working site.
		frappe.log_error(title="AI settings cache failed", message=frappe.get_traceback())
		return

	try:
		features.report()
	except Exception:
		frappe.log_error(title="AI feature report failed", message=frappe.get_traceback())


def sync_books(hint: dict | None) -> dict:
	"""Set the accounting app up, if it is installed and not set up yet.

	Books is generally available, so without this every new workspace opens it
	to an ERPNext error about a missing default company — the wizard that would
	have created one lives on a desk the customer never sees. Runs here because
	this is the only channel that reaches a tenant's database.

	Never raises. A workspace whose books could not be set up automatically is a
	workspace that asks in OneSpace instead; one whose whole sync failed for it
	would also stop receiving entitlements and quotas.
	"""
	try:
		from oneapp.oneapp_core import books

		return books.ensure_setup(hint)
	except Exception as e:  # noqa: BLE001 — a failed setup must not fail the sync
		frappe.log_error(title="Books setup failed", message=frappe.get_traceback())
		return {"error": str(e)[:200]}


def sync_branding(tenant: dict) -> None:
	"""Name the workspace after itself, and keep signup shut.

	Without this a tenant's sign-in page carries Frappe's logo and the word
	"Frappe" — the one screen every user of the workspace sees before they are
	anyone, on a product whose whole premise is that they never see Frappe.
	Provisioning cannot do it: the control plane has no route into this database.

	Only ever fills a blank. The customer owns these afterwards (see
	oneapp_core/workspace.py), and a sync that reset their logo every hour would
	be worse than one that never set it.
	"""
	name = (tenant.get("name") or "").strip()
	if name:
		for doctype, field in (("Website Settings", "app_name"),
		                       ("System Settings", "app_name"),
		                       ("System Settings", "otp_issuer_name")):
			if not frappe.db.get_single_value(doctype, field):
				frappe.db.set_single_value(doctype, field, name)

	# Not a default an owner may change back. Frappe's signup makes an enabled
	# Website User that the control plane never counted a seat for — and that
	# this same sync disables again within the hour, since it reconciles against
	# the member list. See workspace.joining().
	if not frappe.db.get_single_value("Website Settings", "disable_signup"):
		frappe.db.set_single_value("Website Settings", "disable_signup", 1)


def sync_email_account():
	"""Keep the outgoing Email Account in step with bench config.

	The Cloudflare token lives in the bench's common site config, so adding or
	rotating it changes every site's frappe.conf at once. Reconciling here means
	that reaches every tenant on the next sync with no per-site work.
	"""
	from oneapp.oneapp_core.email import outbound

	try:
		outbound.ensure_email_account()
	except Exception:
		# Mail setup must never break an entitlement sync.
		frappe.log_error(
			title="OneSpace email account sync failed", message=frappe.get_traceback()
		)


# What each access level means in DocPerm terms. Three levels rather than a
# checkbox per permission: the manifest is meant to be readable by whoever
# decides what an app exposes, and a matrix of eight flags per row is not.
ACCESS_LEVELS = {
	"Read": {"read": 1},
	"Write": {"read": 1, "write": 1, "create": 1, "print": 1, "email": 1, "export": 1},
	"Manage": {
		"read": 1, "write": 1, "create": 1, "delete": 1,
		"submit": 1, "cancel": 1, "amend": 1,
		"print": 1, "email": 1, "export": 1, "report": 1,
	},
}

PERM_FIELDS = [
	"read", "write", "create", "delete", "submit", "cancel", "amend",
	"print", "email", "export", "report", "share", "if_owner",
]


def ensure_role(name: str):
	"""Create a role that cannot reach the desk.

	desk_access is the whole point. Frappe recomputes User.user_type on every
	save and makes anyone holding a role with desk_access a System User, which
	is exactly who /app lets in. A role created with it set — or an upstream
	role reused — reopens the desk quietly and stays that way until someone
	notices.
	"""
	if frappe.db.exists("Role", name):
		if frappe.db.get_value("Role", name, "desk_access"):
			frappe.db.set_value("Role", name, "desk_access", 0)
		return
	frappe.get_doc(
		{"doctype": "Role", "role_name": name, "desk_access": 0}
	).insert(ignore_permissions=True)


def sync_permissions(manifest: list[dict]):
	"""Write DocPerms for our roles from the control plane's manifest.

	Reconciled, not appended: a doctype dropped from an app's manifest has its
	permission removed here, so revoking access is an edit in one place rather
	than a migration.
	"""
	if not manifest:
		return

	wanted = {}
	for row in manifest:
		role, doctype = row.get("role"), row.get("doctype")
		if not (role and doctype) or not frappe.db.exists("DocType", doctype):
			# A doctype from an app that is not installed on this site is not an
			# error — the manifest describes the catalogue, not this tenant.
			continue
		perms = dict(ACCESS_LEVELS.get(row.get("access") or "Write", ACCESS_LEVELS["Write"]))
		if row.get("if_owner"):
			perms["if_owner"] = 1
		wanted[(doctype, role)] = perms
		ensure_role(role)

	managed_roles = {row["role"] for row in manifest if row.get("role")}
	existing = frappe.get_all(
		"Custom DocPerm",
		filters={"role": ["in", list(managed_roles)]},
		fields=["name", "parent", "role"],
	)

	seen = set()
	for perm in existing:
		key = (perm["parent"], perm["role"])
		if key not in wanted:
			frappe.delete_doc("Custom DocPerm", perm["name"], ignore_permissions=True, force=True)
			continue
		seen.add(key)
		_apply_perm(perm["name"], wanted[key])

	for (doctype, role), perms in wanted.items():
		if (doctype, role) in seen:
			continue
		doc = frappe.get_doc(
			{"doctype": "Custom DocPerm", "parent": doctype, "role": role, "permlevel": 0}
		)
		for field in PERM_FIELDS:
			doc.set(field, perms.get(field, 0))
		doc.insert(ignore_permissions=True)

	frappe.clear_cache()


def _apply_perm(name: str, perms: dict):
	current = frappe.get_doc("Custom DocPerm", name)
	changed = False
	for field in PERM_FIELDS:
		value = perms.get(field, 0)
		if current.get(field) != value:
			current.set(field, value)
			changed = True
	if changed:
		current.save(ignore_permissions=True)


def sync_owner(owner: dict, owner_role: str | None, member_role: str | None = None) -> bool:
	"""Make sure the workspace's owner can actually sign in.

	Created here rather than by the control plane because there is no route from
	there into a tenant's database — this signed sync is the only channel, and
	it runs on install as well as on a schedule.

	Frappe sends the welcome email itself, so the password link is generated on
	the site the customer is signing in to and never crosses the wire.
	"""
	email = (owner.get("email") or "").strip().lower()
	if not email or not owner_role:
		return False

	ensure_role(owner_role)
	# The owner holds the member role too, so "everyone in this workspace" is one
	# question with one answer rather than "the owner, plus whoever holds this".
	if member_role:
		ensure_role(member_role)

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		_set_role(user, owner_role, True)
		if member_role:
			_set_role(user, member_role, True)
		return False

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": owner.get("first_name") or email.split("@")[0],
			# Frappe's own welcome mail carries a link to set a password. Doing
			# it this way keeps the reset key on this site.
			"send_welcome_email": 1,
			"roles": [{"role": role} for role in (owner_role, member_role) if role],
		}
	)
	user.insert(ignore_permissions=True)
	return True



def sync_members(
	members: list[dict],
	owner_role: str | None,
	member_role: str | None,
	owner_email: str,
) -> dict:
	"""Reconcile workspace accounts against the control plane's member list.

	The control plane cannot write here, so this is where an invite becomes an
	account. It is a reconciliation rather than a queue of events: the whole list
	arrives each time, so a member removed upstream is disabled here without
	anything having to remember to send a removal.

	`member_role` is what makes that safe. It grants nothing — the app roles do
	that — and marks an account as one of ours. Reconciling instead on "holds one
	of our app roles" looks equivalent and is not: a member of a workspace with
	no apps entitled yet holds none of them, so removing them disabled nobody and
	they kept their sign-in.

	Removed members are **disabled, never deleted**. Frappe hangs document
	ownership off the User, and the documents someone created belong to the
	workspace — deleting the account would orphan or destroy them. A disabled
	user cannot sign in, which is the part that matters.

	An Admin member also holds the owner role, which is what lets them manage the
	workspace; the billing contact stays whoever `owner_email` is.
	"""
	if not member_role:
		# Nothing to reconcile against. Doing it anyway would mean guessing which
		# accounts are ours, and guessing wrong disables someone's sign-in.
		return {"created": [], "disabled": []}

	ensure_role(member_role)

	owner_email = (owner_email or "").strip().lower()
	wanted = {}
	for member in members or []:
		email = (member.get("email") or "").strip().lower()
		if email and email != owner_email:
			wanted[email] = member

	created, disabled = [], []

	for email, member in wanted.items():
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
			# Re-invited after a removal: enable rather than create a second
			# account, so their documents come back with them.
			if not user.enabled:
				user.enabled = 1
				user.save(ignore_permissions=True)
		else:
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": member.get("full_name") or email.split("@")[0],
					# Frappe mails the password link from this site, so the reset
					# key never crosses the wire — same as the owner's account.
					"send_welcome_email": 1,
				}
			)
			user.insert(ignore_permissions=True)
			created.append(email)

		wants_owner = member.get("access") == "Admin"
		_set_role(user, member_role, True)
		if owner_role:
			_set_role(user, owner_role, wants_owner)

	# Anyone marked as ours who is no longer on the list. The owner is excluded
	# by email: they are not a member row, and disabling them would lock the
	# workspace's billing contact out of it.
	for email in frappe.get_all(
		"User", filters={"enabled": 1}, pluck="name"
	):
		if email in ("Administrator", "Guest") or email == owner_email or email in wanted:
			continue
		roles = {r.role for r in frappe.get_doc("User", email).roles}
		if member_role in roles:
			frappe.db.set_value("User", email, "enabled", 0)
			disabled.append(email)

	return {"created": created, "disabled": disabled}


def _set_role(user, role: str, should_hold: bool):
	"""Add or remove one role, saving only when it actually changes."""
	holds = any(r.role == role for r in user.roles)
	if should_hold and not holds:
		user.append("roles", {"role": role})
		user.save(ignore_permissions=True)
	elif holds and not should_hold:
		user.roles = [r for r in user.roles if r.role != role]
		user.save(ignore_permissions=True)


def sync_roles(
	entitled_roles: list[str],
	owner_role: str | None = None,
	member_role: str | None = None,
):
	"""Reconcile Frappe Roles against entitlements.

	Enforcement is native permissions, so revoking an app is a role removal that
	applies everywhere — desk, REST, reports — not just the launcher.
	"""
	if not entitled_roles:
		return

	for role in entitled_roles:
		ensure_role(role)

	# Roles this app manages but the tenant is no longer entitled to.
	#
	# The owner and member roles are excluded explicitly. Neither is an
	# entitlement — one says who the workspace belongs to, the other marks an
	# account as ours — so neither appears in entitled_roles, and the day either
	# lands in the managed set it would be stripped on the very next sync: the
	# owner locked out of their own workspace, and every member invisible to the
	# reconciliation that is supposed to disable them.
	managed = set(all_managed_roles()) - {owner_role, member_role}
	revoked = managed - set(entitled_roles)

	# Not filtered to System Users. Our roles carry no desk access, so every
	# workspace member is a Website User — filtering on System User would skip
	# all of them and silently stop reconciling entitlements entirely.
	for user in frappe.get_all(
		"User", filters={"enabled": 1}, pluck="name"
	):
		if user in ("Administrator", "Guest"):
			continue
		_reconcile_user_roles(user, entitled_roles, revoked)


def _reconcile_user_roles(user: str, granted: list[str], revoked: set):
	existing = set(
		frappe.get_all("Has Role", filters={"parent": user}, pluck="role")
	)

	to_add = [r for r in granted if r not in existing]
	to_remove = [r for r in revoked if r in existing]

	if not (to_add or to_remove):
		return

	doc = frappe.get_doc("User", user)
	if to_remove:
		doc.set("roles", [r for r in doc.roles if r.role not in to_remove])
	for role in to_add:
		doc.append("roles", {"role": role})
	doc.save(ignore_permissions=True)


def all_managed_roles() -> list[str]:
	"""Roles this app is responsible for, from the last synced manifest.

	Only roles we know about are ever revoked — a role an operator created by
	hand is left alone.
	"""
	doc = frappe.get_single("OneSpace Site State")
	try:
		spaces = json.loads(doc.spaces_json or "[]")
	except (json.JSONDecodeError, TypeError):
		return []
	return [s["role_name"] for s in spaces if s.get("role_name")]


def report_usage_to_control_plane() -> dict:
	"""Push storage and seat counts upward."""
	if site.is_control():
		return {"ok": True, "reason": "not_a_tenant"}
	if not control_client.is_provisioned():
		return {"ok": False, "reason": "not_provisioned"}

	storage = (
		frappe.db.sql("SELECT COALESCE(SUM(file_size), 0) FROM `tabFile`")[0][0] or 0
	)

	# The database is the resource that actually constrains how many sites fit
	# on a server, so it is measured and capped alongside files.
	database = (
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(data_length + index_length), 0)
			FROM information_schema.tables WHERE table_schema = DATABASE()
			"""
		)[0][0]
		or 0
	)
	# Seats, counted without a user_type filter. Our roles carry no desk access,
	# so every workspace member is a Website User — counting System Users would
	# report zero on a full workspace, and max_users would never be enforced
	# while the account page showed no members at all.
	users = frappe.db.count(
		"User", {"enabled": 1, "name": ("not in", ("Administrator", "Guest"))}
	)

	try:
		result = control_client.report_usage(int(storage), int(users), int(database))
	except control_client.ControlPlaneError as e:
		frappe.log_error(title="OneSpace usage report failed", message=str(e))
		return {"ok": False, "error": str(e)}

	doc = frappe.get_single("OneSpace Site State")
	doc.db_set("storage_used_bytes", storage)
	doc.db_set("database_used_bytes", database)
	invalidate()
	return {"ok": True, **result}
