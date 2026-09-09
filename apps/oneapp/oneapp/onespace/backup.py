"""Backups, taken here and pushed straight into R2.

Frappe Cloud keeps its own. This is the second custodian: one provider holding
both your site and the only copy of it is not a backup strategy, and R2 is cheap
enough that the frequency becomes a product lever rather than a cost.

**Why the site does this and not the control plane.** The files only exist here.
The control plane could ask Frappe Cloud for an offsite backup and download it,
which costs bandwidth twice and only works on a plan that has offsite backups
turned on. This site already has the bench, the database credentials and — from
the bench group's common config — R2 keys. So it takes the backup and puts it
where it goes. What the control plane keeps is the *policy*: how often, how long,
and what happens to a workspace that stops paying. See `oneapp_control/lifecycle`.

**Why hourly.** The frequency is a plan term, so the schedule cannot be a cron
line. This runs every hour and decides whether this hour is one of the slots the
plan bought.

**What is in one.** The database and the site config, and on a site whose files
live on disk the two tarballs as well. On a site with a bucket — every hosted
workspace — the tarballs are *not* taken, and that is not a saving so much as
the correction of a duplicate: an attachment is already an object under
`tenants/<tenant>/`, in the same bucket the backup is being written into, so a
tarball was a second copy of the same bytes beside the first, and a big
workspace paid for its files twice and waited on a multi-gigabyte upload every
night to do it. What restores those files is that they were never gone —
`File.r2_key` points at an object the purge is the only thing that deletes. See
`onespace/restore.py` for the half that makes the two agree again afterwards.
"""

import json
import os

import frappe
from frappe.utils import now_datetime

from oneapp.onespace import control_client, site

# One layout, agreed with the control plane. `tests/test_backup_layout.py`
# asserts both sides spell them the same way — they deploy separately, and a
# rolling backup written under a prefix retention does not sweep is a bill
# nobody notices, while a cold copy written where retention *does* sweep is a
# workspace that cannot be restored.
BACKUP_PREFIX = "backups"
COLD_PREFIX = "cold"

# What never leaves this site inside a backup. The HMAC secret is what
# authenticates us to the control plane and the R2 keys open the bucket the
# backup is being written into; a restore mints both again, so carrying them is
# risk without a use.
REDACTED_CONF = (
	"oneapp_hmac_secret",
	"oneapp_r2_access_key",
	"oneapp_r2_secret_key",
	"oneapp_ai_gateway_token",
	"oneapp_cf_api_token",
	"oneapp_cf_email_token",
	"oneapp_google_ai_key",
	"encryption_key",
	"db_password",
	"admin_password",
)

# The four artifacts a workspace can be rebuilt from, and the name each is
# stored under. Fixed names rather than Frappe's timestamped ones, so a restore
# addresses `cold/<tenant>/<stamp>/database.sql.gz` without listing first.
ARTIFACTS = (
	("backup_path_db", "database.sql.gz"),
	("backup_path_files", "public-files.tar"),
	("backup_path_private_files", "private-files.tar"),
	("backup_path_conf", "site-config.json"),
)


def plan_backups_per_day() -> int:
	from oneapp.onespace import sync

	return int(sync.state().get("backups_per_day") or 0)


def is_backup_hour(hour: int, per_day: int) -> bool:
	"""Whether this hour is one of the slots the plan bought.

	Evenly spaced from midnight: one a day is 00:00, two are 00:00 and 12:00,
	four are every six hours. Anything above 24 is capped there — an hour is the
	finest this schedule can express, and a plan asking for more should get the
	most it can rather than nothing.
	"""
	if per_day <= 0:
		return False
	per_day = min(per_day, 24)
	return hour % max(24 // per_day, 1) == 0


def is_full_hour(hour: int) -> bool:
	"""Whether this slot would take the file tarballs too, if they were needed.

	The first of the day and no other: a database dump is megabytes and changes
	constantly; the tarballs are gigabytes and mostly do not. On a site with a
	bucket the answer is moot — `files_live_in_the_bucket` overrules it and
	nothing is tarred at all.
	"""
	return hour == 0


def files_live_in_the_bucket() -> bool:
	"""Whether this workspace's attachments are objects rather than files on disk.

	The one question that decides whether a backup carries files. True on every
	hosted workspace, false on a development site and on anybody self-hosting
	without R2 — where the tarballs are the only copy there is and are taken.
	"""
	from oneapp.onestorage import r2

	return r2.is_configured()


def scheduled_backup() -> dict:
	"""Hourly. Takes a backup if this hour is a slot, otherwise does nothing."""
	if site.is_control():
		return {"ok": True, "reason": "not_a_tenant"}
	if not control_client.is_provisioned():
		return {"ok": False, "reason": "not_provisioned"}

	per_day = plan_backups_per_day()
	hour = now_datetime().hour

	if not is_backup_hour(hour, per_day):
		return {"ok": True, "reason": "not_a_backup_hour", "hour": hour, "per_day": per_day}

	return run_backup(with_files=is_full_hour(hour))


def run_backup(with_files: bool = True) -> dict:
	"""Take a backup and push it to R2. Returns what landed.

	A failure is reported upward rather than only logged: a workspace that has
	quietly stopped backing up looks exactly like one that never needed to, and
	the control plane is the only place that can tell the difference.
	"""
	from oneapp.onestorage import r2

	if not r2.is_configured():
		return _failed("R2 is not configured on this bench.")

	# Never both. The objects are already in the bucket this is being written
	# into; tarring them up would put a second copy of every attachment beside
	# the first and charge for it monthly.
	in_bucket = files_live_in_the_bucket()
	with_files = bool(with_files and not in_bucket)

	try:
		artifacts = take(with_files=with_files)
	except Exception as e:
		frappe.log_error(title="OneSpace backup failed", message=frappe.get_traceback())
		return _failed(f"Backup could not be taken: {e}"[:500])

	stamp = now_datetime().strftime("%Y%m%d-%H%M%S")
	tenant = frappe.conf.get("oneapp_tenant") or "unknown"
	prefix = f"{BACKUP_PREFIX}/{tenant}/{stamp}"

	try:
		uploaded = upload(artifacts, prefix)
	except Exception as e:
		frappe.log_error(title="OneSpace backup upload failed", message=frappe.get_traceback())
		return _failed(f"Backup could not be uploaded: {e}"[:500])

	total = sum(row["size"] for row in uploaded)
	_report(
		{
			"ok": True,
			"key": prefix,
			"bytes": total,
			"with_files": with_files,
			# Said out loud so the control plane can tell a backup that
			# deliberately has no tarballs from one that failed to take them.
			"files_in_bucket": in_bucket,
			"files": [row["name"] for row in uploaded],
		}
	)

	return {
		"ok": True, "key": prefix, "bytes": total, "files": uploaded,
		"with_files": with_files, "files_in_bucket": in_bucket,
	}


#: How long a manual backup blocks the next one. A backup is minutes of a
#: worker and a write to the bucket, and the button is in front of anybody who
#: administers the workspace — pressing it eleven times is eleven backups
#: nobody wanted, and the eleventh does not say anything the first did not.
MANUAL_EVERY_SECONDS = 600
MANUAL_KEY = "oneapp_manual_backup_at"


@frappe.whitelist(methods=["POST"])
def back_up_now() -> dict:
	"""Take one now, on request, rather than at the next slot.

	Before an import, before somebody deletes something large, before an upgrade
	they are nervous about — the three moments a schedule cannot know about and
	a person can. Enqueued rather than run inline: a dump of a large workspace
	outlives the request that asked for it, and a settings screen that hangs for
	four minutes reads as broken.
	"""
	from oneapp.onespace import workspace

	workspace.require_owner()

	if frappe.cache().get_value(MANUAL_KEY):
		frappe.throw(
			frappe._("A backup was taken in the last few minutes. Give it a moment.")
		)
	frappe.cache().set_value(
		MANUAL_KEY, str(now_datetime()), expires_in_sec=MANUAL_EVERY_SECONDS
	)

	frappe.enqueue(
		"oneapp.onespace.backup.run_backup",
		queue="long",
		timeout=3600,
		job_id=f"oneapp-manual-backup-{frappe.local.site}",
		deduplicate=True,
	)
	return {"ok": True, "queued": True}


def take(with_files: bool = True) -> dict:
	"""Ask Frappe for a backup and return `{artifact name: path}`.

	`force=True` because the schedule already decided this hour is a slot;
	Frappe's own `older_than` guard would otherwise skip the second run of a day
	as redundant, which is precisely the run a higher plan is paying for.
	"""
	from frappe.utils.backups import new_backup

	generator = new_backup(
		ignore_files=not with_files,
		force=True,
		compress=True,
		verbose=False,
	)

	found = {}
	for attribute, name in ARTIFACTS:
		path = getattr(generator, attribute, None)
		if path and os.path.exists(path):
			found[name] = path
	return found


def upload(artifacts: dict, prefix: str) -> list[dict]:
	"""Put each artifact under the prefix. Returns what was written."""
	from oneapp.onestorage import r2

	bucket = r2.config()["bucket"]
	client = r2.client()
	written = []

	for name, path in artifacts.items():
		if name == "site-config.json":
			body = redacted_config(path)
			client.put_object(
				Bucket=bucket, Key=f"{prefix}/{name}", Body=body,
				ContentType="application/json",
			)
			written.append({"name": name, "size": len(body)})
			continue

		size = os.path.getsize(path)
		with open(path, "rb") as fh:
			client.put_object(Bucket=bucket, Key=f"{prefix}/{name}", Body=fh)
		written.append({"name": name, "size": size})

	return written


def redacted_config(path: str) -> bytes:
	"""The site config with every secret removed.

	Frappe copies `site_config.json` into a backup verbatim, which is right for a
	restore you perform yourself and wrong for one stored in the same bucket the
	config's own keys open. What survives is the shape — which tenant, which
	control plane, which bucket — and a restore mints the secrets again.
	"""
	try:
		with open(path) as fh:
			config = json.load(fh)
	except (OSError, ValueError):
		return b"{}"

	for key in REDACTED_CONF:
		if key in config:
			config[key] = None

	return json.dumps(config, indent=1, sort_keys=True).encode("utf-8")


def _failed(reason: str) -> dict:
	_report({"ok": False, "error": reason})
	return {"ok": False, "error": reason}


def _report(result: dict):
	"""Tell the control plane how it went. Never fatal.

	A backup that succeeded and could not be reported is still a backup; failing
	the whole run because the control plane was unreachable would turn a network
	blip into a missing copy.
	"""
	try:
		control_client.report_backup(result)
	except Exception as e:
		frappe.log_error(title="OneSpace backup report failed", message=str(e))
