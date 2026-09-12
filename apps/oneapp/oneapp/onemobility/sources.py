"""The three doors data comes in through, and the one pipeline behind them.

README §5 is the argument; this is it in code. A **source** says where data
arrives, and every kind ends at the same two steps — record a `Transit Feed`,
then normalise it onto the model. Only the fetch differs:

    Folder   a folder in Files. Upload into it, or connect it to an SFTP, FTP,
             SMB or WebDAV host first. Every file under it is read.
    HTTP     a URL, asked for on a schedule. A GET and a byte range.
    Stream   the source pushes to us, or we hold a connection open. Its doors
             are `live.report` and `streaming.py` rather than anything here.

**A source is a folder, and that is the whole of the configuration.** It used
to be four kinds and two fields: `Upload` for a file somebody dragged in,
`Folder` for a mount and a path inside it, and a `format` dropdown naming a
specification. All three were asking the customer to do work the machine can
do. An upload has somewhere to land now — a Drive folder — and a Drive folder
and a mounted drop folder are addressed the same way (`onestorage/walk.py`),
so there is one kind, one field, and nothing to pick wrong.

Four rules the whole module turns on:

* **The delivery says what it is.** Nothing declares a format; `sniff.py`
  opens the bytes and decides from what is inside them, and what had to be
  forgiven — a gzip wrapper, a feed one folder down, a missing core file — is
  written on the feed where a customer will read it. The one exception is a
  stream, which has to name its dialect because the handshake differs per
  protocol and there is nothing to open until it has already been spoken.

* **A folder is read whole, not newest-first.** The old door took the newest
  file on each poll and moved a watermark past it, which quietly lost every
  delivery that arrived out of order and every backlog a new source was
  pointed at. Now the folder is walked, each file is a delivery of its own,
  and *what has already been taken is written on the feeds* — one per file,
  by path, size and the host's own clock. A late arrival is still taken; a
  re-drop under the same name is taken again because a number moved.

  A directory that is *itself* one feed is the exception `sniff.group`
  exists for: an unzipped GTFS export is `agency.txt` and eight siblings, and
  reading each of those as a delivery would refuse nine files instead of
  loading one.


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

from . import sniff

#: The largest delivery this will take in one fetch. A GTFS feed for a large
#: German operator is tens of megabytes; a gigabyte is a misconfiguration or a
#: redirect to something that is not a feed, and pulling it into memory to find
#: out is how a worker dies.
MAX_BYTES = 256 * 1024 * 1024

#: How long to wait on a host that has stopped answering. Long enough for a
#: slow authority, short enough that a scheduled poll does not sit on a worker
#: for the rest of the hour.
TIMEOUT = 120

#: The most deliveries one fetch will take. A folder pointed at four years of
#: nightly drops is fourteen hundred files, and reading all of them in one job
#: is a worker gone for the afternoon. Oldest first, so successive polls walk
#: forward through a backlog and the newest data is never the thing waiting.
BATCH = 25

#: Which formats have a normaliser, and which module is it. A format not in
#: here is still *recognised* — the feed says what it is and says there is no
#: reader — which is the difference between "not supported yet" and a parse
#: error nobody can act on.
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


def deliver(source: str, content: bytes, label: str = "", file_url: str = "",
            origin: str = "", size: int = 0, stamp: float = 0.0) -> dict:
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
			# Written before anything is parsed, and before the row can be
			# refused, because this is also the ledger: a delivery that failed
			# to load must not be offered again on the next poll as though it
			# had never been seen.
			"origin": origin[:140],
			"origin_size": cint(size),
			"origin_stamp": _when(stamp) if stamp else None,
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

	# What the delivery actually is. Nothing is consulted but the bytes: a
	# customer choosing from a dropdown was being asked a question about a
	# specification they may never have read, and the file can answer it.
	guess = sniff.identify(content, origin or label or file_url)
	fmt = guess.format
	feed.db_set("format", fmt or "", update_modified=False)
	if guess.notes:
		# On the feed rather than only in a log: the customer reading "read as
		# VDV 452, and the feed was inside a folder" is the one who can act on
		# it, and they are not reading the error log.
		feed.db_set("notes", " ".join(guess.notes)[:400], update_modified=False)

	if fmt not in LOADERS:
		_refuse(feed, _("{0} is not a format this can read yet.{1}").format(
			fmt or _("This delivery"),
			" " + " ".join(guess.notes) if guess.notes else "",
		))
		return {"feed": feed.name, "loaded": False, "detected": guess.as_dict()}

	reader = frappe.get_attr(f"oneapp.onemobility.{LOADERS[fmt]}.load")

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
	return {"feed": feed.name, "loaded": True, "detected": guess.as_dict(), **counts}


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


def folder_key(doc) -> str:
	"""The one address `onestorage.walk` takes, from the two fields a person fills.

	The form asks which kind of folder and then which one, because both are
	rows and both deserve the framework's own picker. Everything past the form
	wants a single string — `walk` reads a Drive folder and a mounted one the
	same way — so the composition happens here, once, and no reader below ever
	learns there were two fields.
	"""
	from oneapp.onestorage import remote

	if not doc.folder:
		frappe.throw(_("This source needs a folder. Pick one in Files."))
	if doc.folder_type == "Remote Folder":
		return remote.idfor(doc.folder, doc.subfolder or "/")
	return doc.folder


class Delivery:
	"""One thing to read: its bytes, what to call it, and where it came from."""

	__slots__ = ("label", "content", "origin", "size", "stamp")

	def __init__(self, label, content, origin, size, stamp):
		self.label = label
		self.content = content
		self.origin = origin
		self.size = size
		self.stamp = stamp


def _taken(source: str) -> set[tuple]:
	"""Everything this source has already taken, by file rather than by clock.

	The ledger, and it lives on the feeds because the feeds are the thing a
	customer already reads. Three parts and each earns its place: the **path**
	because that is what a file is, the **size** and the **written time**
	because a supplier who corrects an export re-drops it under exactly the
	same name and that is a new delivery, not a duplicate.

	One query per fetch rather than one per file. A source with four years of
	nightly drops has fourteen hundred feeds, which is a set of fourteen
	hundred tuples and nothing worth paging.
	"""
	rows = frappe.get_all(
		"Transit Feed",
		filters={"source": source, "origin": ("!=", "")},
		fields=["origin", "origin_size", "origin_stamp"],
		limit_page_length=0,
	)
	return {
		(row.origin, cint(row.origin_size), _epoch(row.origin_stamp) if row.origin_stamp else 0.0)
		for row in rows
	}


def _over_folder(doc) -> list[Delivery]:
	"""Every file under the folder that has not been read yet.

	The folder may be in the Drive or on somebody else's host, and this does
	not know which: `onestorage.walk` addresses both the same way, which is
	the whole reason a person uploading a file and an authority dropping one
	over SFTP now configure the same single field.

	A directory that is itself one feed is packed back into a zip before it
	goes any further — `sniff.group` decides, `sniff.pack` does it — so every
	reader below still takes bytes and none of them has to learn what a
	directory is.
	"""
	from oneapp.onestorage import walk

	found = walk.entries(folder_key(doc))
	if not found:
		return []

	byname = {one.path: one for one in found}
	sets = sniff.group(list(byname))
	# A member of a set is not a delivery on its own; the set is.
	spoken = {member for held in sets.values() for member in held}

	already = _taken(doc.name)
	out: list[Delivery] = []

	for here, held in sorted(sets.items()):
		newest = max(byname[one].modified for one in held)
		whole = sum(byname[one].size for one in held)
		origin = (here + "/") if here else "/"
		if (origin, whole, newest) in already:
			continue
		members = [(one, walk.read(byname[one].key)) for one in held]
		out.append(Delivery(
			label=here.rsplit("/", 1)[-1] or walk.label(doc.folder),
			content=sniff.pack(members),
			origin=origin, size=whole, stamp=newest,
		))
		if len(out) >= BATCH:
			return out

	for one in found:
		if one.path in spoken:
			continue
		if (one.path, one.size, one.modified) in already:
			continue
		if not one.size:
			continue
		if one.size > MAX_BYTES:
			continue
		out.append(Delivery(
			label=one.name, content=walk.read(one.key),
			origin=one.path, size=one.size, stamp=one.modified,
		))
		if len(out) >= BATCH:
			break

	return out


def _epoch(value) -> float:
	return frappe.utils.get_datetime(value).timestamp()


def _when(epoch: float):
	from datetime import datetime

	return datetime.fromtimestamp(epoch)


def fetch(source: str) -> dict:
	"""Ask one source for whatever it has. The whole of the scheduled path.

	A source that pushes — a Stream — is not an error here: it has
	nothing to be asked for, and saying so is more useful than refusing.
	"""
	doc = frappe.get_doc("Transit Source", source)
	if doc.status == "Paused":
		return {"fetched": False, "reason": "paused"}

	try:
		if doc.kind == "HTTP":
			got = [Delivery(label="", content=_over_http(doc), origin="",
			                size=0, stamp=0.0)]
		elif doc.kind == "Folder":
			got = _over_folder(doc)
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

	got = [one for one in got if one.content]
	if not got:
		frappe.db.set_value(
			"Transit Source", source,
			{"last_run": now_datetime(), "last_message": _("Nothing new.")},
			update_modified=False,
		)
		return {"fetched": False, "reason": "nothing new"}

	# Each on its own, and committed as it goes: a folder of forty deliveries
	# where the eleventh is corrupt should leave ten loaded and one refused,
	# not roll the lot back. `deliver` refuses rather than throws for anything
	# it can name; what escapes it is a reader failing, and that one file is
	# allowed to fail without taking the other thirty-nine with it.
	done = []
	for one in got:
		try:
			done.append(deliver(source, one.content, label=one.label,
			                    origin=one.origin, size=one.size, stamp=one.stamp))
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title="Transit delivery failed",
			                 message=frappe.get_traceback())
		else:
			frappe.db.commit()

	return {
		"fetched": True,
		"deliveries": len(done),
		"loaded": sum(1 for one in done if one.get("loaded")),
		**(done[-1] if done else {}),
	}


@frappe.whitelist(methods=["POST"])
def load_feed(source: str, file_url: str = "", label: str = "") -> dict:
	"""Take a delivery from an upload and read it. The Upload door.

	Lived in `gtfs.py` until detection arrived, which made the name a lie: this
	is the door every format comes through when somebody drops a file on the
	screen, and `sniff.py` is what decides which reader sees it. The other
	three doors fetch differently and arrive at the same `deliver`.

	Reached from the Sources screen's own button, which is an action declaring
	`upload` — `spaceview/actions.py` for what that means and `spaceview/run.py`
	for the one extra argument it is allowed to carry.
	"""
	if not frappe.has_permission("Transit Feed", "create"):
		frappe.throw(_("You cannot load a feed."), frappe.PermissionError)
	if not frappe.has_permission("Transit Source", "write", doc=source):
		frappe.throw(_("You cannot deliver to this source."), frappe.PermissionError)

	content = _bytes_of(file_url)
	if not content:
		frappe.throw(_("That file is empty, or it is not here any more."))
	return deliver(source, content, label=label, file_url=file_url)


def _bytes_of(file_url: str) -> bytes | None:
	"""The bytes behind a `File`, wherever that file actually lives.

	`get_content` rather than a path read, because a workspace's files are in
	R2 and the override is what knows how to reach them — `onestorage/r2.py`.
	"""
	if not file_url:
		return None
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		return None
	return frappe.get_doc("File", name).get_content()


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
		filters={"status": ("!=", "Paused"), "kind": ("in", ("HTTP", "Folder"))},
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
