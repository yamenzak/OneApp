"""Going back to a backup, and what that costs.

A restore is the one destructive thing a workspace can do to itself. Frappe
Cloud drops the database and reimports the dump, so everything written since the
backup was taken is gone — and, because this product keeps attachments as
objects rather than rows, "gone" would quietly not include the files. A record
restored away leaves its attachment sitting in the bucket referenced by nothing,
invisible to every screen and billed for monthly. That is the orphan this module
exists to prevent, and the reason a restore here is two acts rather than one:

    1. the database goes back to the moment            (the control plane, press)
    2. the bucket is made to agree with it again        (`reconcile`, here)

The second one deletes, and nothing brings those bytes back. So the first thing
this module offers is not the restore but `preview`: how many records were made
since that moment, how many were changed, how many files will be deleted and how
many megabytes they are. Somebody pressing this should know the size of the hole
before they press it, and the numbers are the only honest way to say it.

**Why the reconcile is not a flag in the database.** It cannot be. The database
is the thing being replaced — anything this site writes before the restore is
overwritten by the restore, including a note saying a restore is happening. So
the control plane records when it restored us, sends that down the ordinary
sync, and the site notices the value differs from the one it last acted on. The
site's copy came out of the dump and is therefore always older, which is what
makes a restored site reconcile exactly once without either end keeping a list.
"""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import now_datetime

from oneapp.onespace import backup, control_client
from oneapp.onestorage import r2

#: How many restore points to offer. Retention is seven days on the entry plan
#: and an hourly plan takes 24 a day, so this is comfortably past the oldest one
#: any plan keeps.
POINTS = 200

#: An object younger than this is left alone by the reconcile, whatever the
#: database says about it. A direct upload writes the object first and the `File`
#: row second — a few seconds apart, longer for a multi-part upload of a large
#: file — so a sweep with no settling time is a sweep that eventually deletes a
#: file somebody is in the middle of uploading. After a restore nothing has been
#: written for far longer than this: the site was offline for the whole of it.
SETTLE_MINUTES = 15

#: Doctypes that are always in the preview, whether or not a space declares
#: them. Files because they are what the reconcile deletes, and people because
#: "who could sign in" is the first thing somebody checks after a restore.
ALWAYS = ("File", "User", "Contact", "Comment", "ToDo")

#: And what is never in it. Every one of these is a log: restoring loses them
#: and nobody minds, and counting them would bury the rows that matter under a
#: few hundred thousand view records.
NEVER = {
	"Access Log", "Activity Log", "Authentication Log", "Error Log",
	"Error Snapshot", "Notification Log", "Route History", "Scheduled Job Log",
	"View Log", "Version", "Deleted Document", "Prepared Report",
	"Email Queue", "Email Queue Recipient", "Document Follow",
}

#: How many doctypes the preview counts. A tenant site carries about twelve
#: hundred tables and most of them are the framework's; asking all of them would
#: take a minute and answer with noise.
PREVIEW_DOCTYPES = 60


# --------------------------------------------------------------------------- #
# What there is to go back to
# --------------------------------------------------------------------------- #

def _tenant() -> str:
	return frappe.conf.get("oneapp_tenant") or "unknown"


def _stamp_to_datetime(stamp: str):
	"""`20260412-031500` back into a datetime.

	The stamp is written by `backup.run_backup` in this site's own timezone and
	is the only record of when a set was taken that does not depend on R2's
	clock, so it is what the preview asks its questions against. Parsed here
	rather than through Frappe's `get_datetime`, which takes anything a person
	might type: this format is ours, and a stamp that is not one of ours is not
	a restore point.
	"""
	try:
		return datetime.strptime(stamp, "%Y%m%d-%H%M%S")
	except (ValueError, TypeError):
		return None


def _moment(value):
	"""R2's timestamp as a naive local datetime, or None.

	The listing hands back timezone-aware UTC and everything else on this site
	is naive; comparing the two raises rather than being wrong, which is the
	good failure, but it still has to be dealt with once somewhere.
	"""
	try:
		return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
	except (ValueError, TypeError):
		return None


@frappe.whitelist(methods=["GET"])
def points() -> dict:
	"""Every backup this workspace can go back to, newest first.

	Read straight out of the bucket rather than relayed from the control plane:
	the objects are ours, under our own prefix, and the site already holds the
	keys that can list them. What the control plane owns is the policy — how
	often and how long — and that arrives with the ordinary sync.
	"""
	from oneapp.onespace import sync, workspace

	workspace.require_owner()

	if not r2.is_configured():
		return {"ok": False, "reason": "no_storage", "points": []}

	prefix = f"{backup.BACKUP_PREFIX}/{_tenant()}/"
	grouped: dict[str, dict] = {}

	for row in r2.list_objects(prefix):
		stamp, _sep, name = row["key"][len(prefix):].partition("/")
		if not (stamp and name):
			continue
		found = grouped.setdefault(
			stamp, {"stamp": stamp, "bytes": 0, "artifacts": []}
		)
		found["bytes"] += row["size"]
		found["artifacts"].append(name)

	found = []
	for one in sorted(grouped.values(), key=lambda s: s["stamp"], reverse=True)[:POINTS]:
		when = _stamp_to_datetime(one["stamp"])
		found.append({
			"stamp": one["stamp"],
			"when": str(when) if when else None,
			"bytes": one["bytes"],
			# A set with no dump is not a restore point. It is half of an upload
			# that failed, and offering it as one would be offering a button
			# that cannot work.
			"restorable": "database.sql.gz" in one["artifacts"],
		})

	state = sync.state()
	return {
		"ok": True,
		"points": found,
		"per_day": int(state.get("backups_per_day") or 0),
		"retention_days": int(state.get("backup_retention_days") or 0),
		# Said here because the list looks alarming without it: no tarballs, on
		# a workspace whose files are objects, is the correct shape for a set.
		"files_in_bucket": backup.files_live_in_the_bucket(),
	}


# --------------------------------------------------------------------------- #
# What it would cost
# --------------------------------------------------------------------------- #

def _counted_doctypes() -> list[str]:
	"""The doctypes worth counting: what the workspace's spaces show, plus files
	and people. Ordered so the ones a person recognises come first."""
	from oneapp.onespace import sync

	granted = [
		name for name in sorted(sync.granted_doctypes())
		if name not in NEVER
	]
	wanted = list(ALWAYS) + granted
	seen, out = set(), []
	for name in wanted:
		if name in seen or name in NEVER:
			continue
		seen.add(name)
		if frappe.db.table_exists(name):
			out.append(name)
	return out[:PREVIEW_DOCTYPES]


def _since(doctype: str, moment) -> dict:
	"""How many rows of one doctype were made, and how many changed, since then."""
	table = f"tab{doctype}"
	made = frappe.db.sql(
		f"SELECT COUNT(*) FROM `{table}` WHERE creation > %s", moment
	)[0][0]
	changed = frappe.db.sql(
		f"SELECT COUNT(*) FROM `{table}` WHERE modified > %s AND creation <= %s",
		(moment, moment),
	)[0][0]
	return {"doctype": doctype, "made": int(made or 0), "changed": int(changed or 0)}


@frappe.whitelist(methods=["GET"])
def preview(stamp: str) -> dict:
	"""What going back to this point would take with it.

	Counted against the live database rather than read out of the dump, which
	would mean downloading and importing it to answer a question somebody asked
	before deciding. Everything made after the moment is lost and everything
	changed after it reverts, so the two counts are the whole answer — and the
	file numbers are the part that cannot be undone by restoring forward again,
	because the objects are deleted rather than replaced.
	"""
	from oneapp.onespace import workspace
	from oneapp.onestorage import quota

	workspace.require_owner()

	moment = _stamp_to_datetime(stamp)
	if not moment:
		frappe.throw(_("{0} is not a backup this workspace has.").format(stamp))

	rows = [_since(name, moment) for name in _counted_doctypes()]
	rows = [row for row in rows if row["made"] or row["changed"]]
	rows.sort(key=lambda row: -(row["made"] + row["changed"]))

	files = frappe.db.sql(
		"""
		SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM `tabFile`
		WHERE creation > %s AND IFNULL(is_folder, 0) = 0
		""",
		moment,
	)[0]

	# The other direction, and the one nobody expects. A file deleted since the
	# backup comes back as a row, because the row is in the dump — but its bytes
	# went when the bin was emptied, and no restore can produce them again. The
	# row will be there and the file will not open.
	gone = frappe.db.count(
		"Deleted Document", {"deleted_doctype": "File", "creation": (">", moment)}
	)

	return {
		"ok": True,
		"stamp": stamp,
		"when": str(moment),
		"records": rows,
		"made": sum(row["made"] for row in rows),
		"changed": sum(row["changed"] for row in rows),
		"files": {
			"count": int(files[0] or 0),
			"bytes": int(files[1] or 0),
			"label": quota.format_bytes(int(files[1] or 0)),
		},
		"unrecoverable_files": int(gone or 0),
		"people": frappe.db.count("User", {"creation": (">", moment), "enabled": 1}),
	}


# --------------------------------------------------------------------------- #
# Asking for one
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def start(stamp: str) -> dict:
	"""Ask the control plane to put this workspace back to a point.

	The site cannot do this to itself. Restoring means dropping the database
	this request is running inside, which only Frappe Cloud can do — so the ask
	goes up the signed channel and comes back as a site that has been rebuilt.
	Every check that matters is repeated on the control plane; this one is here
	so somebody who is not an admin gets a refusal rather than a job.
	"""
	from oneapp.onespace import workspace

	workspace.require_owner()
	if not _stamp_to_datetime(stamp):
		frappe.throw(_("{0} is not a backup this workspace has.").format(stamp))

	try:
		return control_client.call(
			"workspace_admin",
			{
				"action": "restore_workspace",
				"as_user": frappe.session.user,
				"arguments": {"stamp": stamp},
			},
		)
	except (control_client.NotProvisioned, control_client.ControlPlaneError) as e:
		frappe.throw(
			_("The restore could not be started: {0}").format(str(e)[:200])
		)


# --------------------------------------------------------------------------- #
# Making the bucket agree again
# --------------------------------------------------------------------------- #

def known_keys() -> set[str]:
	"""Every object this database still claims, trashed rows included.

	Trashed included on purpose: a file in the bin is a file whose thirty days
	have not run out, and the bin sweep is what deletes those objects. A
	reconcile that read `Active` only would empty everybody's bin the first time
	it ran, which is a different feature and not this one.
	"""
	return {
		row[0] for row in frappe.db.sql(
			"SELECT r2_key FROM `tabFile` WHERE IFNULL(r2_key, '') != ''"
		)
	}


@frappe.whitelist(methods=["POST"])
def reconcile(dry_run: int | bool = 0) -> dict:
	"""Delete the objects no row points at any more. Irreversible.

	Run after a restore, and weekly regardless — an upload that failed between
	putting the object and writing the row leaves the same kind of orphan, in
	ones rather than thousands.

	Two refusals stand between this and a catastrophe. An object younger than
	`SETTLE_MINUTES` is never touched, because the row that will claim it may
	still be being written. And a database that claims *no* objects at all while
	the bucket holds them is not a workspace with no files — it is a database
	that is mid-restore, half-migrated or broken, and deleting a bucket on its
	word is the single worst thing this code could do.
	"""
	if not r2.is_configured():
		return {"ok": False, "reason": "no_storage"}

	dry_run = bool(int(dry_run or 0))
	prefix = f"tenants/{_tenant()}/"
	present = r2.list_objects(prefix)
	if not present:
		return {"ok": True, "deleted": 0, "bytes": 0, "kept": 0}

	known = known_keys()
	if not known:
		frappe.log_error(
			title="File reconcile refused",
			message=(
				f"{len(present)} objects under {prefix} and not one `File` row "
				"claiming any of them. Refusing to treat that as a workspace "
				"with no files."
			),
		)
		return {"ok": False, "reason": "nothing_claimed", "objects": len(present)}

	settled = now_datetime() - timedelta(minutes=SETTLE_MINUTES)
	orphans, held = [], 0

	for row in present:
		if row["key"] in known:
			continue
		when = _moment(row.get("modified"))
		if when and when > settled:
			# Too new to judge. It will be here next time, and by then the row
			# that claims it either exists or never will.
			held += 1
			continue
		orphans.append(row)

	deleted = 0
	if orphans and not dry_run:
		deleted = r2.delete_keys([row["key"] for row in orphans])

	return {
		"ok": True,
		"dry_run": dry_run,
		"deleted": deleted if not dry_run else 0,
		"orphans": len(orphans),
		"bytes": sum(row["size"] for row in orphans),
		"too_new": held,
		"kept": len(present) - len(orphans),
		# The other half of the disagreement, which this cannot fix and should
		# not hide: rows pointing at objects that are not there. After a restore
		# these are the files somebody deleted since the backup.
		"missing": len(known - {row["key"] for row in present}),
	}


def sweep() -> dict:
	"""Weekly. The same reconcile, for the orphans nobody made on purpose."""
	from oneapp.onespace import site

	if site.is_control() or not r2.is_configured():
		return {"ok": True, "reason": "not_a_tenant"}
	return reconcile()


def after_restore(block: dict) -> None:
	"""Reconcile once, if the control plane says we have just been restored.

	`block["restored_on"]` is the control plane's clock and the site's copy of
	it came out of the dump, so they differ exactly once per restore. Enqueued
	rather than run inline: a workspace with a hundred thousand objects takes
	minutes to list, and the sync that noticed this has fourteen other things to
	do.
	"""
	restored_on = (block or {}).get("restored_on")
	if not restored_on:
		return

	state = frappe.get_single("OneSpace Site State")
	if str(state.files_reconciled_for or "") == str(restored_on):
		return

	# Written before the work rather than after: a reconcile that dies halfway
	# through should not be re-run from the top by the next sync, which is
	# fifteen minutes away and would find the same objects. The weekly sweep
	# picks up whatever the first pass did not.
	state.db_set("files_reconciled_for", str(restored_on))

	try:
		frappe.enqueue(
			"oneapp.onespace.restore.reconcile",
			queue="long",
			timeout=3600,
			job_id=f"oneapp-reconcile-{frappe.local.site}",
			deduplicate=True,
		)
	except Exception:
		frappe.log_error(
			title="Post-restore reconcile could not be enqueued",
			message=frappe.get_traceback(),
		)
