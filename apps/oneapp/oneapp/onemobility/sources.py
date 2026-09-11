"""The four doors data comes in through, and the one pipeline behind them.

README §5 is the argument; this is it in code. A **source** says how data
arrives and in which dialect, and every kind ends at the same two steps —
record a `Transit Feed`, then normalise it onto the model. Only the fetch
differs:

    Upload   somebody drops a file on the screen. Nothing to fetch.
    HTTP     a URL, asked for on a schedule. A GET and a byte range.
    SFTP     a host and a folder. The most common thing an authority runs, and
             the reason `paramiko` is a dependency.
    Socket   the source pushes to us. Nothing to fetch either, and its door is
             `live.report` rather than anything here.

Two rules the whole module turns on:

* **The delivery is kept.** Every fetch writes the bytes it got as a `File`
  attached to the feed, before anything is parsed. A number somebody disputes
  is then answerable — "this is the file it came from, at this minute" — and a
  loader that turns out to be wrong can be re-run over the same input rather
  than over whatever the source is serving today.

* **A failing source stays visible.** A fetch that throws marks the source
  Failing and writes the reason on it, rather than logging somewhere nobody
  reads. Five sources and one of them quietly stopped a fortnight ago is the
  failure mode that makes a data product untrustworthy.
"""

import io

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

#: The largest delivery this will take in one fetch. A GTFS feed for a large
#: German operator is tens of megabytes; a gigabyte is a misconfiguration or a
#: redirect to something that is not a feed, and pulling it into memory to find
#: out is how a worker dies.
MAX_BYTES = 256 * 1024 * 1024

#: How long to wait on a host that has stopped answering. Long enough for a
#: slow authority, short enough that a scheduled poll does not sit on a worker
#: for the rest of the hour.
TIMEOUT = 120

#: Which formats have a normaliser, and which module is it. The rest are
#: declared on the doctype because a customer should be able to say what they
#: have before we can read it — and be told so plainly rather than have it fail
#: as a parse error.
#:
#: Every one of these is an importer onto the *one* model, never a second model:
#: README §1, which is also why they share a signature and why `deliver` below
#: does not know which of them it called.
LOADERS = {
	"GTFS": "gtfs",
	"VDV 452": "vdv452",
	# The odd one out, and deliberately here rather than beside it: the two
	# above bring a *network* into existence — the lines and stops everything
	# else hangs off — and this one counts a network somebody else described.
	# It shares the signature because the door is the same, not because the
	# result is.
	"VDV 457-3": "vdv457",
}


def _refuse(feed, message: str):
	feed.db_set("status", "Refused", update_modified=False)
	feed.db_set("notes", message[:400], update_modified=False)


def deliver(source: str, content: bytes, label: str = "", file_url: str = "") -> dict:
	"""Record one delivery and read it. Every door ends here.

	`file_url` is passed when the bytes are already a `File` — an upload, or a
	re-run of a delivery that is still attached. Otherwise the bytes are kept
	as one, because a feed whose file has gone is a number nobody can explain.
	"""
	doc = frappe.get_doc("Transit Source", source)
	feed = frappe.get_doc(
		{
			"doctype": "Transit Feed",
			"label": label or f"{doc.source_name} {now_datetime():%Y-%m-%d %H:%M}",
			"source": source,
			"status": "Received",
			"received_on": now_datetime(),
			"file": file_url,
		}
	).insert(ignore_permissions=True)

	if not file_url and content:
		kept = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{feed.name}.zip",
				"attached_to_doctype": "Transit Feed",
				"attached_to_name": feed.name,
				"is_private": 1,
				"content": content,
			}
		).insert(ignore_permissions=True)
		feed.db_set("file", kept.file_url, update_modified=False)

	if not content:
		_refuse(feed, _("The delivery was empty."))
		return {"feed": feed.name, "loaded": False}

	if doc.format not in LOADERS:
		_refuse(feed, _("{0} is not a format this can read yet.").format(doc.format))
		return {"feed": feed.name, "loaded": False}

	reader = frappe.get_attr(f"oneapp.onemobility.{LOADERS[doc.format]}.load")

	try:
		counts = reader(feed.name, content)
	except Exception:
		_refuse(feed, frappe.get_traceback(with_context=False)[-400:])
		raise

	frappe.db.set_value(
		"Transit Source",
		source,
		{
			"last_run": now_datetime(),
			"status": "Connected",
			"last_message": _("Read {0} lines, {1} stops and {2} trips.").format(
				counts.get("lines", 0), counts.get("stops", 0), counts.get("trips", 0)
			),
			"rows_seen": cint(doc.rows_seen) + sum(cint(v) for v in counts.values()),
		},
		update_modified=False,
	)
	return {"feed": feed.name, "loaded": True, **counts}


# --------------------------------------------------------------------------- #
# The fetches
# --------------------------------------------------------------------------- #

def _over_http(doc) -> bytes:
	"""A URL, asked for once.

	Streamed and counted rather than `.content`, because `MAX_BYTES` has to be
	a limit on what is read and not a check on what was already read.
	"""
	import requests

	if not (doc.endpoint or "").startswith(("http://", "https://")):
		frappe.throw(_("An HTTP source needs a URL as its endpoint."))

	auth = (doc.username, doc.get_password("secret")) if doc.username else None
	answer = requests.get(doc.endpoint, timeout=TIMEOUT, stream=True, auth=auth)
	answer.raise_for_status()

	buffer = io.BytesIO()
	for chunk in answer.iter_content(64 * 1024):
		buffer.write(chunk)
		if buffer.tell() > MAX_BYTES:
			frappe.throw(_("The delivery is larger than this can take in one fetch."))
	return buffer.getvalue()


def _over_sftp(doc) -> tuple[bytes, str]:
	"""The newest file in the folder, and what it was called.

	Newest rather than every file: an authority's drop folder holds months of
	deliveries, and taking all of them on every poll is a fetch that gets
	slower for ever. `watermark` is what stops the same file being taken twice.
	"""
	try:
		import paramiko
	except ImportError:
		frappe.throw(_("SFTP needs paramiko, which is not installed on this site."))

	if not doc.endpoint:
		frappe.throw(_("An SFTP source needs a host as its endpoint."))

	host, _sep, port = doc.endpoint.partition(":")
	transport = paramiko.Transport((host, cint(port) or 22))
	try:
		transport.connect(username=doc.username, password=doc.get_password("secret"))
		client = paramiko.SFTPClient.from_transport(transport)
		folder = doc.folder or "."
		entries = [one for one in client.listdir_attr(folder) if one.st_size]
		if not entries:
			return b"", ""

		newest = max(entries, key=lambda one: one.st_mtime)
		if doc.watermark and newest.st_mtime <= _epoch(doc.watermark):
			return b"", ""
		if newest.st_size > MAX_BYTES:
			frappe.throw(_("The delivery is larger than this can take in one fetch."))

		buffer = io.BytesIO()
		client.getfo(f"{folder.rstrip('/')}/{newest.filename}", buffer)
		frappe.db.set_value(
			"Transit Source", doc.name,
			"watermark", frappe.utils.get_datetime(_when(newest.st_mtime)),
			update_modified=False,
		)
		return buffer.getvalue(), newest.filename
	finally:
		transport.close()


def _epoch(value) -> float:
	return frappe.utils.get_datetime(value).timestamp()


def _when(epoch: float):
	from datetime import datetime

	return datetime.fromtimestamp(epoch)


def fetch(source: str) -> dict:
	"""Ask one source for whatever it has. The whole of the scheduled path.

	A source that pushes — Upload, Socket — is not an error here: it has
	nothing to be asked for, and saying so is more useful than refusing.
	"""
	doc = frappe.get_doc("Transit Source", source)
	if doc.status == "Paused":
		return {"fetched": False, "reason": "paused"}

	try:
		if doc.kind == "HTTP":
			content, named = _over_http(doc), ""
		elif doc.kind == "SFTP":
			content, named = _over_sftp(doc)
		else:
			return {"fetched": False, "reason": "pushed"}
	except Exception as failed:
		frappe.db.set_value(
			"Transit Source", source,
			{"status": "Failing", "last_run": now_datetime(),
			 "last_message": str(failed)[:400]},
			update_modified=False,
		)
		frappe.db.commit()
		raise

	if not content:
		frappe.db.set_value(
			"Transit Source", source,
			{"last_run": now_datetime(), "last_message": _("Nothing new.")},
			update_modified=False,
		)
		return {"fetched": False, "reason": "nothing new"}

	return {"fetched": True, **deliver(source, content, label=named)}


@frappe.whitelist(methods=["POST"])
def fetch_now(source: str) -> dict:
	"""The button beside a source. Same path as the schedule, asked for."""
	if not frappe.has_permission("Transit Source", "write", doc=source):
		frappe.throw(_("You cannot run this source."), frappe.PermissionError)
	return fetch(source)


def poll():
	"""Every source that is due. Hourly, from `hooks.py`.

	Hourly and not per-source-schedule for the same reason backups are: a
	frequency is a *setting* and cannot be a cron line, so this wakes every
	hour and decides which sources this hour is one of the slots for.

	Each source is enqueued rather than fetched here. A drop folder that has
	stopped answering would otherwise hold the scheduler for two minutes and
	take every other source's turn with it.
	"""
	from frappe.utils import add_to_date

	now = now_datetime()
	for one in frappe.get_all(
		"Transit Source",
		filters={"status": ("!=", "Paused"), "kind": ("in", ("HTTP", "SFTP"))},
		fields=["name", "every_minutes", "last_run"],
	):
		every = cint(one.every_minutes)
		if not every:
			continue
		if one.last_run and add_to_date(one.last_run, minutes=every) > now:
			continue
		frappe.enqueue(
			"oneapp.onemobility.sources.fetch",
			queue="long",
			job_id=f"transit-source-{one.name}",
			deduplicate=True,
			source=one.name,
		)
