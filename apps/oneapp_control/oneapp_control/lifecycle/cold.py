"""Cold storage: the copy a workspace can be rebuilt from after its site is gone.

Archiving a tenant deletes the site from Frappe Cloud. Before this existed that
was the end of it — the workspace was simply gone, and the R2 objects it had
uploaded sat in the bucket forever, orphaned and billed for. So the ladder never
ran, because nobody was willing to wire an automatic deletion to a timer.

A cold copy is not a separate mechanism. It is the daily backup, promoted:

    backups/<tenant>/<stamp>/…   rolling, expired by retention
    cold/<tenant>/<stamp>/…      promoted, expired only by the lifecycle

Promotion is a server-side copy, so a 4 GB backup costs a request rather than
four gigabytes through a control plane with no business carrying them. Beside the
artifacts goes a manifest: who this was, what they were paying for, who could
sign in, and where it all came from. A restore needs the manifest more than it
needs any single file — the database says what the workspace contained, and only
the manifest says what it *was*.

**The control plane cannot reach into a tenant site.** Every call goes the other
way, over HMAC. So asking for a fresh copy is a flag the site picks up on its
next sync, and the fallback when it never does is to promote the newest rolling
backup there is. A workspace whose scheduler died must not be held open forever,
and it must not be archived with nothing behind it either.
"""

import json

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from oneapp_control.cloudflare import r2
from oneapp_control.lifecycle import backups, events

# How fresh a rolling backup has to be before it is promoted as-is rather than a
# new one being asked for. A little over a day, so a workspace on the entry plan
# — one backup, at midnight — is served by the copy it already has rather than
# waiting on a request every single time.
FRESH_HOURS = 26

# How long we wait for a site to answer a request before giving up and promoting
# whatever it already has. A site that has not synced in three days is not about
# to; holding the ladder open for it is a workspace nobody is paying for.
REQUEST_WAIT_DAYS = 3


def key_for(tenant: str, stamp: str) -> str:
	return f"{backups.COLD_PREFIX}/{tenant}/{stamp}"


def bucket_for(tenant) -> str | None:
	"""The R2 bucket name a workspace's objects live in.

	`Tenant.storage_bucket` links a Storage Bucket record; the bucket's actual
	name is a field on it. Reaching for the link name instead is a mistake that
	reads correctly and addresses nothing.
	"""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	if not doc.storage_bucket:
		return None
	return frappe.db.get_value("Storage Bucket", doc.storage_bucket, "bucket_name")


# --------------------------------------------------------------------------- #
# Taking one
# --------------------------------------------------------------------------- #

def ensure(tenant: str, *, triggered_by: str = "Sweep") -> dict:
	"""Make sure a cold copy exists, and say what happened.

	Three outcomes, and the caller has to handle all three:

    * `{"ok": True}` — one exists, or was just promoted. Safe to archive.
    * `{"ok": False, "reason": "requested"}` — the site has been asked for a
      fresh one and has not answered yet. Come back tomorrow.
    * `{"ok": False, "reason": "no_backup"}` — there is nothing to promote and
      the site is not answering. **Never archive on this.**
	"""
	doc = frappe.get_doc("Tenant", tenant)

	if doc.cold_storage_key:
		return {"ok": True, "key": doc.cold_storage_key, "reason": "already_held"}

	bucket = bucket_for(doc)
	if not bucket:
		return {"ok": False, "reason": "no_bucket"}

	held = backups.sets(bucket, tenant)
	fresh = _freshest(held, FRESH_HOURS)

	if fresh:
		return promote(doc, fresh, bucket=bucket, triggered_by=triggered_by)

	# Nothing recent. Ask the site for one, and see how long we have been asking.
	requested_since = doc.get("cold_copy_requested_on")

	if not requested_since:
		request(doc, triggered_by=triggered_by)
		return {"ok": False, "reason": "requested"}

	waited_out = get_datetime(requested_since) < get_datetime(
		add_to_date(now_datetime(), days=-REQUEST_WAIT_DAYS)
	)
	if not waited_out:
		return {"ok": False, "reason": "requested", "since": requested_since}

	# It never answered. Promote the newest thing there is, and say in the log
	# that it is old — an operator reading a restore later has to know the copy
	# predates the archive.
	if held:
		return promote(
			doc, held[-1], bucket=bucket, triggered_by=triggered_by, stale=True
		)

	return {"ok": False, "reason": "no_backup", "asked_since": requested_since}


def _freshest(sets: list[dict], hours: int) -> dict | None:
	if not sets:
		return None

	newest = sets[-1]
	when = newest.get("modified")
	if not when:
		return None

	if get_datetime(str(when)[:19]) >= get_datetime(add_to_date(now_datetime(), hours=-hours)):
		return newest
	return None


def request(tenant, *, triggered_by: str = "Sweep") -> None:
	"""Ask the site for a fresh full backup on its next sync.

	A flag rather than a call: every wire between the two runs tenant to control
	plane, and inventing a channel the other way for one message would be a lot
	of surface for something a fifteen-minute sync already answers.
	"""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	doc.db_set("cold_copy_requested_on", now_datetime())
	events.record(
		doc.name,
		"Cold Copy Taken",
		triggered_by=triggered_by,
		reason="Asked the site for a final full backup before it is archived.",
		detail={"state": "requested"},
	)


def promote(tenant, backup_set: dict, *, bucket: str | None = None,
            triggered_by: str = "Sweep", stale: bool = False) -> dict:
	"""Copy one backup set into cold storage and write the manifest beside it."""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	bucket = bucket or bucket_for(doc)
	if not bucket:
		return {"ok": False, "reason": "no_bucket"}

	stamp = backup_set.get("stamp") or now_datetime().strftime("%Y%m%d-%H%M%S")
	target = key_for(doc.name, stamp)
	row = events.opening(
		doc.name,
		"Cold Copy Taken",
		triggered_by=triggered_by,
		reason=f"Promoting {backup_set.get('stamp') or 'a backup'} to cold storage.",
		detail={"target": target, "stale": stale},
	)

	copied = []
	for key in backup_set["keys"]:
		name = key.rsplit("/", 1)[-1]
		r2.copy(bucket, key, f"{target}/{name}")
		copied.append(name)

	body = json.dumps(manifest(doc, stamp=stamp, artifacts=copied, stale=stale),
	                  indent=1, default=str).encode("utf-8")
	r2.put(bucket, f"{target}/manifest.json", body)

	total = backup_set.get("bytes") or 0
	doc.db_set(
		{
			"cold_storage_key": target,
			"cold_stored_on": now_datetime(),
			"cold_storage_bytes": total,
			"cold_copy_requested_on": None,
		}
	)
	events.close(row, detail={"artifacts": copied, "bytes": total})

	return {"ok": True, "key": target, "bytes": total, "stale": stale}


def manifest(tenant, *, stamp: str, artifacts: list[str], stale: bool = False) -> dict:
	"""Everything a restore needs that is not in the database.

	The dump says what the workspace contained. Only this says what it *was*:
	which plan, which domains, who could sign in, which region and bucket its
	files came from. Written as plain JSON so it is readable a year later by
	somebody who no longer has this codebase.
	"""
	from oneapp_control.billing import quotas

	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	terms = quotas.for_tenant(doc)

	return {
		"version": 1,
		"taken_on": str(now_datetime()),
		"stamp": stamp,
		"stale": stale,
		"artifacts": sorted(artifacts),
		"tenant": {
			"name": doc.name,
			"slug": doc.tenant_slug,
			"title": doc.tenant_name,
			"status": doc.status,
			"owner_email": doc.owner_email,
			"site_name": doc.site_name,
			"press_site": doc.press_site,
			"primary_domain": doc.primary_domain,
			"region": doc.region,
			"shard": doc.shard,
			"storage_bucket": doc.storage_bucket,
			"storage_jurisdiction": doc.storage_jurisdiction,
			"provisioned_on": str(doc.provisioned_on) if doc.provisioned_on else None,
		},
		"billing": {
			"plan": doc.plan,
			"subscription": doc.subscription,
			"customer": doc.customer,
			"promo_code": doc.promo_code,
			"terms": terms,
			"granted": {
				"extra_storage_gb": doc.extra_storage_gb,
				"extra_database_gb": doc.extra_database_gb,
			},
		},
		"members": [
			{"email": row.email, "full_name": row.full_name, "access": row.access}
			for row in (doc.members or [])
		],
		"usage": {
			"storage_used_bytes": doc.storage_used_bytes,
			"database_used_bytes": doc.database_used_bytes,
			"user_count": doc.user_count,
		},
	}


def read_manifest(tenant) -> dict | None:
	"""The manifest of the cold copy a workspace holds, if it holds one."""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	bucket = bucket_for(doc)
	if not (bucket and doc.cold_storage_key):
		return None

	body = r2.get(bucket, f"{doc.cold_storage_key}/manifest.json")
	if not body:
		return None
	try:
		return json.loads(body)
	except ValueError:
		return None


def links(tenant, ttl: int = 3600) -> dict:
	"""Presigned URLs for the cold artifacts, for Frappe Cloud to restore from.

	An hour, because press fetches the files itself and a database dump of any
	size takes longer than the five minutes an attachment redirect is given.
	"""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	bucket = bucket_for(doc)
	if not (bucket and doc.cold_storage_key):
		return {}

	found = {}
	for row in r2.objects(bucket, f"{doc.cold_storage_key}/"):
		name = row["key"].rsplit("/", 1)[-1]
		if name == "manifest.json":
			continue
		found[name] = r2.presign(bucket, row["key"], ttl=ttl)
	return found


# --------------------------------------------------------------------------- #
# Destroying one
# --------------------------------------------------------------------------- #

# Every prefix a workspace owns. Named here rather than built at the call site,
# because a purge that misses one leaves objects nobody will ever look for and
# we go on paying for them.
PREFIXES = (backups.COLD_PREFIX, backups.BACKUP_PREFIX, "tenants")


def purge(tenant, *, triggered_by: str = "Sweep", reason: str = "") -> dict:
	"""Delete everything this workspace has in R2. Irreversible.

	Called only by `lifecycle.sweep`, and only after every window and warning in
	`lifecycle.policy` has passed. The refusals that make that safe live in the
	sweep; what lives here is the one refusal that has to be closest to the
	delete — a prefix that does not name a tenant.
	"""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)
	bucket = bucket_for(doc)

	row = events.opening(
		doc.name,
		"Purged",
		triggered_by=triggered_by,
		reason=reason or "Retention elapsed; deleting every object this workspace owns.",
		detail={"bucket": bucket, "prefixes": list(PREFIXES)},
	)

	if not bucket:
		# Nothing was ever stored, so there is nothing to delete. Still a purge.
		events.close(row, to_status="Purged", detail={"deleted": 0, "note": "no bucket"})
		return {"ok": True, "deleted": 0}

	deleted, failures = 0, []
	for prefix in PREFIXES:
		try:
			deleted += r2.delete_prefix(bucket, f"{prefix}/{doc.name}/")
		except Exception as e:
			failures.append({"prefix": prefix, "error": str(e)[:200]})
			frappe.log_error(
				title=f"Purge failed under {prefix} for {doc.name}",
				message=frappe.get_traceback(),
			)

	doc.db_set(
		{
			"cold_storage_key": None,
			"cold_storage_bytes": 0,
			"purged_on": now_datetime(),
		}
	)
	events.close(row, to_status="Purged", detail={"deleted": deleted, "failed": failures})

	return {"ok": not failures, "deleted": deleted, "failed": failures}
