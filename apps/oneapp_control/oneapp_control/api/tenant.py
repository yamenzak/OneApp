"""Endpoints tenant sites call on the control plane.

Every request is HMAC-signed with the tenant's own secret. There is no session
and no user — the signature *is* the authentication, and it also proves which
tenant is calling, so a tenant cannot read another tenant's state by asking
nicely.
"""

import json

import frappe
from frappe import _

from oneapp_control.ai import catalogue, pricing
from oneapp_control.credits import ledger
from oneapp_control.entitlements import registry
from oneapp_control.lifecycle import overage
from oneapp_control.utils.signing import TENANT_HEADER, verify


def _authenticate() -> str:
	"""Verify the signature and return the calling tenant's name."""
	tenant = frappe.request.headers.get(TENANT_HEADER)
	if not tenant:
		frappe.throw(_("Missing tenant header."), frappe.PermissionError)

	if not frappe.db.exists("Tenant", tenant):
		# Deliberately the same error as a bad signature — do not confirm which
		# tenant slugs exist to an unauthenticated caller.
		frappe.throw(_("Invalid or expired signature."), frappe.PermissionError)

	secret = frappe.get_doc("Tenant", tenant).signing_secret()
	body = frappe.request.get_data(as_text=True) or ""

	if not verify(
		secret,
		body,
		_header("Signature"),
		_header("Timestamp"),
	):
		frappe.throw(_("Invalid or expired signature."), frappe.PermissionError)

	return tenant


def _body() -> dict:
	raw = frappe.request.get_data(as_text=True) or "{}"
	try:
		return json.loads(raw) or {}
	except json.JSONDecodeError:
		return {}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def sync(since: str | None = None):
	"""Everything a tenant site needs to render itself and enforce limits.

	Called on a schedule and on demand. The tenant site caches this; the control
	plane stays authoritative.

	`since` is the tenant's own watermark for workspace notices — the last one
	it has already shown somebody. There is no channel from here into a tenant
	database, so a notice is something the site collects rather than something
	we deliver, and a watermark is what makes collecting it exactly once
	possible without either side keeping a per-notice record of the other.
	"""
	tenant_name = _authenticate()
	tenant = frappe.get_doc("Tenant", tenant_name)

	return {
		"tenant": {
			"slug": tenant.tenant_slug,
			"name": tenant.tenant_name,
			"status": tenant.status,
			"site_name": tenant.site_name,
			"primary_domain": tenant.primary_domain,
		},
		"plan": {
			"code": tenant.plan,
			"storage_quota_bytes": tenant.storage_quota_bytes,
			"database_quota_bytes": tenant.database_quota_bytes,
			"max_users": tenant.max_users,
			"background_workers": tenant.background_workers,
			# How often this workspace copies itself into R2. The site owns the
			# schedule because it owns the files; the plan owns the number.
			"backups_per_day": int(tenant.terms.get("backups_per_day") or 0),
		},
		# Whether the site should enforce its quotas at all, and until when if
		# not. A workspace over its limit because a line left its subscription
		# did nothing wrong, and blocking it the moment Stripe dropped the line
		# is the surprise this exists to prevent. See `lifecycle/overage.py`.
		"quota": overage.state(tenant),
		# One flag, and it is how the control plane asks for a final full backup
		# before a workspace is archived. There is no channel from here into a
		# tenant site — every wire runs the other way — so a request is something
		# the site collects rather than something we deliver.
		"backup": {"requested": bool(tenant.cold_copy_requested_on)},
		"spaces": registry.spaces_for_tenant(tenant_name),
		"modules": registry.entitled_modules(tenant_name),
		"roles": registry.entitled_roles(tenant_name),
		# One row per (role, doctype). The tenant site writes DocPerms from this
		# because our roles are ours: we use ERPNext for its logic, not for its
		# idea of who an "Accounts Manager" is, so they start with no
		# permissions at all. See docs/ONESPACE.md, Roles.
		"permissions": registry.permission_manifest(tenant_name),
		"owner_role": registry.OWNER_ROLE,
		"member_role": registry.MEMBER_ROLE,
		# Who the workspace belongs to. The tenant site creates this account on
		# first sync — nothing else can, since the control plane has no way to
		# write into a tenant's database, and until it exists the customer has
		# a workspace they cannot sign in to.
		"owner": {
			"email": tenant.owner_email,
			"first_name": (tenant.tenant_name or "").split(" ")[0] or "Owner",
		},
		# Everyone else who may sign in. Sent whole rather than as a diff: the
		# tenant site reconciles against it, so a member removed here is
		# disabled there without anything having to remember to send a removal.
		"members": [
			{
				"email": row.email,
				"full_name": row.full_name or "",
				"access": row.access,
				# Resolved here rather than sent as keys, because the keys mean
				# nothing on a tenant site: it holds Frappe roles, and which
				# Frappe role a key becomes is a question only the control plane
				# can answer — it is the side that knows which spaces this
				# workspace is entitled to and what custom roles it built.
				#
				# Every space's default is already in here, so a member with
				# nothing ticked can still open what the workspace has.
				"roles": registry.roles_for_member(tenant_name, row.roles),
			}
			for row in (tenant.members or [])
		],
		"credits": {
			"balance": ledger.balance(tenant_name),
			"available": ledger.available(tenant_name),
		},
		# The models a workspace may choose from and the policy for each declared
		# feature. Cached on the site so the settings page renders and a model
		# can be chosen while the control plane is unreachable — but never used
		# to price a call, which happens here or not at all.
		"ai": {
			"models": catalogue.catalogue_for_tenant(),
			"features": _ai_features(),
		},
		# What signup already answered, so the tenant site can set its books up
		# without asking again. Sent rather than assumed there: the country came
		# from the region they chose and the currency from the plan they bought,
		# and neither is knowable from inside the site.
		"books": _books_hint(tenant),
		# What has happened to this workspace that the people in it should be
		# told about. See `_notices`.
		"notices": _notices(tenant_name, since),
	}


# Which lifecycle events a customer is told about, and what each one says.
#
# Not all sixteen. A cold copy being taken, a backup succeeding, a hold being
# placed and released are operations — real events, worth recording, and not
# news. What is here is the set a person in the workspace can either act on or
# would otherwise discover by finding something broken.
#
# The wording is the control plane's because the facts are: it is the side that
# knows what a plan costs, when a payment failed and what happens next.
NOTICES = {
	"Dunning Started": (
		"A payment did not go through",
		"We could not charge the card on this workspace. Nothing has changed yet — "
		"update the card to keep everything running.",
	),
	"Dunning Cleared": (
		"Payment received",
		"The workspace is up to date again. Nothing else to do.",
	),
	"Suspended": (
		"This workspace is suspended",
		"Sign-in is off while the account is unpaid. Everything is still here and "
		"comes straight back when it is settled.",
	),
	"Resumed": (
		"This workspace is back",
		"Suspension lifted. Everything is where it was.",
	),
	"Over Quota": (
		"This workspace is over its limit",
		"Uploads and new records are paused until it is back under, or the plan "
		"is raised. Nothing has been deleted.",
	),
	"Back Under Quota": (
		"Back under the limit",
		"Uploads and new records are running again.",
	),
	"Purge Warned": (
		"This workspace is scheduled for deletion",
		"It has been archived and unpaid long enough to be removed. Restoring it "
		"stops the clock.",
	),
	"Archived": (
		"This workspace has been archived",
		"It is stored safely and offline. Restoring brings it back as it was.",
	),
	"Restored": (
		"This workspace has been restored",
		"Everything is back, including the files.",
	),
	"Backup Failed": (
		"A backup did not finish",
		"The last scheduled copy of this workspace failed. We will try again on "
		"the next slot; tell us if it keeps happening.",
	),
}

# How many notices one sync may carry. A workspace that has been left alone for
# a month should not answer its first sync with two hundred of them — the
# watermark still advances past the rest, because what a person needs is the
# state they are in and not a diary of how they got there.
NOTICE_LIMIT = 10


def _notices(tenant_name: str, since: str | None) -> list[dict]:
	"""Lifecycle events this workspace has not been told about yet."""
	filters = {"tenant": tenant_name, "event": ["in", sorted(NOTICES)]}
	if since:
		# By name rather than by timestamp: the series is monotonic and two
		# events in the same second are ordered by it, which a datetime
		# comparison would drop one of.
		filters["name"] = [">", since]

	rows = frappe.get_all(
		"Tenant Lifecycle Event",
		filters=filters,
		fields=["name", "event", "occurred_on", "reason"],
		order_by="name asc",
		limit_page_length=NOTICE_LIMIT,
	)
	return [
		{
			"key": row["name"],
			"event": row["event"],
			"title": NOTICES[row["event"]][0],
			"body": row.get("reason") or NOTICES[row["event"]][1],
			"occurred_on": str(row["occurred_on"]) if row.get("occurred_on") else None,
		}
		for row in rows
	]


def _ai_features() -> list[dict]:
	"""Platform policy per feature: what a workspace may change, and what it may not."""
	return frappe.get_all(
		"AI Feature",
		filters={"status": ["!=", "Withdrawn"]},
		fields=[
			"name as key", "label", "app", "capability", "status",
			"tenant_can_disable", "allow_prompt_addendum", "default_model",
			"max_input_tokens", "max_output_tokens", "max_images",
			"max_outputs", "max_audio_seconds", "max_credits", "description",
		],
		order_by="app asc, label asc",
	)


def _books_hint(tenant) -> dict:
	"""Country, currency and company name for the accounting setup.

	The tenant site decides whether to act on it — it is the only side that can
	see whether ERPNext is installed or a company already exists.
	"""
	country = (
		frappe.db.get_value("Region", tenant.region, "country") if tenant.region else None
	)
	currency = frappe.db.get_value("Plan", tenant.plan, "currency") if tenant.plan else None

	return {
		"company_name": tenant.tenant_name,
		"country": country,
		"currency": currency,
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def report_usage():
	"""Tenant site reports its own storage and seat consumption."""
	tenant_name = _authenticate()
	data = _body()

	updates = {"usage_synced_on": frappe.utils.now_datetime()}
	if "storage_used_bytes" in data:
		updates["storage_used_bytes"] = float(data["storage_used_bytes"] or 0)
	if "user_count" in data:
		updates["user_count"] = int(data["user_count"] or 0)
	if "database_used_bytes" in data:
		updates["database_used_bytes"] = float(data["database_used_bytes"] or 0)

	frappe.db.set_value("Tenant", tenant_name, updates)

	tenant = frappe.get_doc("Tenant", tenant_name)

	# Warn once per threshold crossing rather than on every report, which is
	# hourly and would be noise.
	_maybe_warn(tenant)

	# And reconcile the overage window. Here rather than in the sweep because
	# this is the one place that sees what is held and what is allowed at the
	# same moment — the sweep runs daily and would leave a workspace refused for
	# up to a day before anybody told it why.
	quota = overage.check(tenant)

	return {
		"storage_used_bytes": tenant.storage_used_bytes,
		"storage_quota_bytes": tenant.storage_quota_bytes,
		"fraction_used": round(tenant.storage_fraction_used(), 4),
		"database_used_bytes": tenant.database_used_bytes,
		"database_quota_bytes": tenant.database_quota_bytes,
		"user_count": tenant.user_count,
		"max_users": tenant.max_users,
		"quota": quota,
	}


def _maybe_warn(tenant):
	"""Email once as each resource crosses the warning threshold.

	The flag resets when usage drops back below, so freeing space and filling up
	again warns again — but steady-state usage does not mail every hour.
	"""
	from oneapp_control.control_plane.doctype.tenant.tenant import WARN_FRACTION
	from oneapp_control.notifications import emails

	for resource, fraction in (
		("storage", tenant.storage_fraction_used()),
		("database", tenant.database_fraction_used()),
	):
		key = f"oneapp_warned:{tenant.name}:{resource}"
		warned = frappe.cache().get_value(key)

		if fraction >= WARN_FRACTION and not warned:
			emails.quota_warning(tenant.name, resource, fraction)
			frappe.cache().set_value(key, 1, expires_in_sec=7 * 24 * 3600)
		elif fraction < WARN_FRACTION and warned:
			frappe.cache().delete_value(key)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def report_backup():
	"""Take delivery of a backup result, good or bad.

	Recorded on the tenant rather than only logged, because "when did this
	workspace last have a restorable copy" is a question an operator has to be
	able to answer per workspace and across the fleet at once. A failure clears
	nothing — the last good backup stays the last good backup, and the error sits
	beside it.
	"""
	tenant_name = _authenticate()
	data = _body()

	from oneapp_control.lifecycle import events

	if data.get("ok"):
		frappe.db.set_value(
			"Tenant",
			tenant_name,
			{
				"last_backup_on": frappe.utils.now_datetime(),
				"last_backup_key": (data.get("key") or "")[:140],
				"last_backup_bytes": float(data.get("bytes") or 0),
				"last_backup_error": None,
			},
		)
		events.record(
			tenant_name,
			"Backup Taken",
			triggered_by="Tenant Site",
			reason=data.get("key") or "",
			detail={
				"bytes": data.get("bytes"),
				"with_files": data.get("with_files"),
				"files": data.get("files"),
			},
		)

		# This is the copy we asked for. Promote it now rather than waiting for
		# tomorrow's sweep: a workspace held one rung short of suspension for a
		# day because its backup landed an hour after the sweep is a day we are
		# carrying somebody who has stopped paying.
		promoted = _promote_if_requested(tenant_name, data)
		return {"ok": True, **({"cold": promoted} if promoted else {})}

	error = (data.get("error") or "Backup failed")[:1000]
	frappe.db.set_value("Tenant", tenant_name, "last_backup_error", error)
	events.record(
		tenant_name, "Backup Failed", triggered_by="Tenant Site", reason=error
	)
	return {"ok": True, "recorded": "failure"}


def _promote_if_requested(tenant_name: str, data: dict) -> dict | None:
	"""Promote a just-reported backup to cold storage, if one was asked for.

	Only a full backup will do. An intra-day database-only run carries no files
	and restoring from it would silently produce a workspace with every record
	and no attachments — which looks like it worked.
	"""
	tenant = frappe.get_doc("Tenant", tenant_name)
	if not tenant.cold_copy_requested_on or tenant.cold_storage_key:
		return None
	if not data.get("with_files"):
		return None

	from oneapp_control.lifecycle import backups as backup_policy
	from oneapp_control.lifecycle import cold

	bucket = cold.bucket_for(tenant)
	if not bucket:
		return None

	held = backup_policy.sets(bucket, tenant_name)
	if not held:
		return None

	try:
		return cold.promote(tenant, held[-1], bucket=bucket, triggered_by="Tenant Site")
	except Exception:
		# The backup itself arrived and is recorded. Failing the report because
		# a copy between two prefixes failed would make the site take it again.
		frappe.log_error(
			title=f"Cold promotion failed for {tenant_name}", message=frappe.get_traceback()
		)
		return None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def reserve_credits():
	"""Hold credits before an expensive operation."""
	tenant_name = _authenticate()
	data = _body()

	credits = float(data.get("credits") or 0)
	purpose = data.get("purpose") or "unspecified"

	try:
		reservation = ledger.reserve(tenant_name, credits, purpose)
	except ledger.InsufficientCredits:
		return {
			"ok": False,
			"reason": "insufficient_credits",
			"available": ledger.available(tenant_name),
		}

	return {
		"ok": True,
		"reservation": reservation.name,
		"expires_at": str(reservation.expires_at),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def ai_reserve():
	"""Hold the most an AI call may cost, before it is made.

	The tenant site does not price its own calls. It says which model and which
	feature; the ceiling and, later, the charge are both computed here against
	the synced catalogue. One place holds the prices, and a site cannot bill
	itself a number of its own choosing.
	"""
	tenant_name = _authenticate()
	data = _body()

	model_key = data.get("model")
	if not frappe.db.exists("AI Model", model_key):
		return {"ok": False, "reason": "unknown_model", "model": model_key}

	status = frappe.db.get_value("AI Model", model_key, "status")
	if status not in ("Available", "Preview"):
		return {"ok": False, "reason": "model_unavailable", "status": status}

	try:
		ceiling = pricing.ceiling(model_key, data.get("limits") or {})
	except pricing.Unpriceable as e:
		return {"ok": False, "reason": "unpriceable", "message": str(e)}

	purpose = f"ai:{data.get('feature') or 'unspecified'}"
	try:
		reservation = ledger.reserve(tenant_name, ceiling, purpose)
	except ledger.InsufficientCredits:
		return {
			"ok": False,
			"reason": "insufficient_credits",
			"available": ledger.available(tenant_name),
			"needed": ceiling,
		}

	return {
		"ok": True,
		"reservation": reservation.name,
		"ceiling": ceiling,
		"expires_at": str(reservation.expires_at),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def ai_settle():
	"""Charge what the call actually used, and keep the receipt.

	`units` are counts the provider returned — tokens by modality, tiles, audio
	minutes. Nothing here is estimated, and a unit the catalogue cannot price
	is an error rather than a zero.
	"""
	tenant_name = _authenticate()
	data = _body()

	reservation = frappe.get_doc("Credit Reservation", data["reservation"])
	if reservation.tenant != tenant_name:
		frappe.throw(_("Reservation does not belong to this tenant."), frappe.PermissionError)

	if data.get("release"):
		reservation.release(data.get("reason") or "call failed")
		return {"ok": True, "status": reservation.status, "credits": 0,
		        "balance": ledger.balance(tenant_name)}

	model_key = data.get("model")
	units = data.get("units") or []

	try:
		priced = pricing.charge(model_key, units, data.get("tier") or "Standard")
	except (pricing.Unpriceable, frappe.DoesNotExistError) as e:
		# The work is done and the customer has their answer. Releasing the hold
		# is the only honest move: we cannot name a price, so we do not charge
		# one, and the record below says why.
		reservation.release("could not be priced")
		_usage_record(tenant_name, data, {"credits": 0, "cost_usd": 0, "markup": 0,
		                                  "provider": ""}, note=str(e))
		frappe.log_error(title="AI call could not be priced", message=str(e))
		return {"ok": True, "status": reservation.status, "credits": 0,
		        "unpriced": True, "balance": ledger.balance(tenant_name)}

	remarks = f"{model_key} {data.get('feature') or ''}".strip()
	held = float(reservation.credits_reserved or 0)
	reservation.commit_usage(priced["credits"], remarks)

	# commit_usage never charges more than was held, which is the right rule for
	# a hold and the wrong one for a bill: a call that overran its ceiling still
	# cost us the money. Post the remainder rather than absorb it silently.
	overrun = round(float(priced["credits"]) - held, 2)
	if overrun > 0:
		ledger.post_entry(
			tenant=tenant_name,
			entry_type="Adjustment",
			credits=-overrun,
			remarks=f"{remarks} exceeded its {held} credit ceiling by {overrun}.",
		)
		frappe.log_error(
			title="AI call exceeded its ceiling",
			message=f"{remarks}: held {held}, used {priced['credits']}.",
		)

	_usage_record(tenant_name, data, priced)

	return {
		"ok": True,
		"status": reservation.status,
		"credits": priced["credits"],
		"cost_usd": priced["cost_usd"],
		"balance": ledger.balance(tenant_name),
	}


def _usage_record(tenant_name: str, data: dict, priced: dict, note: str = ""):
	"""One row per call: what it used, what it cost, and the gateway log id.

	The log id is the whole point of writing this down. It is how a later job
	compares what we charged against what Cloudflare says the call cost.
	"""
	frappe.get_doc({
		"doctype": "AI Usage Record",
		"tenant": tenant_name,
		"feature": data.get("feature"),
		"model": data.get("model") if frappe.db.exists("AI Model", data.get("model")) else None,
		"provider": priced.get("provider"),
		"credits_charged": priced.get("credits") or 0,
		"cost_usd": priced.get("cost_usd") or 0,
		"markup": priced.get("markup") or 0,
		"reservation": data.get("reservation"),
		"units": json.dumps(data.get("units") or [], sort_keys=True),
		"gateway_log_id": data.get("log_id"),
		"cached": 1 if data.get("cached") else 0,
		"recon_note": note,
	}).insert(ignore_permissions=True)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def report_ai_features():
	"""Take delivery of a site's feature registry.

	Features exist in app code behind a decorator, which is the only thing that
	knows they exist. Sites report what they found; this is the upsert, so an
	operator can see the whole surface and pin a model or suspend a feature
	without a deploy and without anyone maintaining a list.
	"""
	_authenticate()
	features = _body().get("features") or []

	for spec in features:
		key = spec.get("key")
		if not key:
			continue

		existing = frappe.db.exists("AI Feature", key)
		doc = frappe.get_doc("AI Feature", key) if existing else frappe.new_doc("AI Feature")
		doc.update({
			"feature_key": key,
			"label": spec.get("label") or key,
			"app": spec.get("app"),
			"capability": spec.get("capability") or "Text Generation",
			# Declared in code, not configured here: whether a feature can run
			# without AI is a property of the process, and an operator toggling
			# it would be overruling the app that has to work afterwards.
			"tenant_can_disable": 1 if spec.get("tenant_can_disable") else 0,
			"allow_prompt_addendum": 1 if spec.get("allow_prompt_addendum") else 0,
			"max_input_tokens": spec.get("max_input_tokens") or 0,
			"max_output_tokens": spec.get("max_output_tokens") or 0,
			"max_images": spec.get("max_images") or 0,
			"max_outputs": spec.get("max_outputs") or 0,
			"max_audio_seconds": spec.get("max_audio_seconds") or 0,
			"description": spec.get("description"),
			"last_seen": frappe.utils.now_datetime(),
		})
		if not existing:
			doc.status = "Active"
		doc.save(ignore_permissions=True)

	return {"ok": True, "features": len(features)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def commit_credits():
	"""Settle a reservation against what was actually used."""
	tenant_name = _authenticate()
	data = _body()

	reservation = frappe.get_doc("Credit Reservation", data["reservation"])
	if reservation.tenant != tenant_name:
		frappe.throw(_("Reservation does not belong to this tenant."), frappe.PermissionError)

	if data.get("release"):
		reservation.release(data.get("reason") or "released by tenant")
	else:
		reservation.commit_usage(float(data.get("credits") or 0), data.get("remarks"))

	return {
		"ok": True,
		"status": reservation.status,
		"committed": reservation.credits_committed,
		"balance": ledger.balance(tenant_name),
	}


def _header(name: str) -> str | None:
	"""One header, under either name.

	The signing headers were `X-OneApp-*` and are `X-OneSpace-*`. Both ends are
	ours, but they deploy separately — a tenant on the old build talking to a
	control plane on the new one would be refused, and "signature missing" is
	not a message anybody would trace back to a rename. The sender writes the
	new name; the receiver takes either, for one release.
	"""
	headers = frappe.request.headers
	return headers.get(f"X-OneSpace-{name}") or headers.get(f"X-OneApp-{name}")
