"""A folder on somebody else's server, browsed in the Drive.

A transport authority does not email you a GTFS feed. It puts it on an SFTP
host and tells you the folder, and that is also how half of construction moves
drawings and how every accountant who has ever said "the bank drop" means it.
Before this the answer was one credential form per consumer — OneMobility had
its own host, folder, username and password on `Transit Source`, and knew how
to walk an SFTP directory, and nothing else in the product could see any of it.

So it is one noun instead: a **`Remote Folder`** is a host, a protocol, a
credential and a base path, and once it exists it is a place in the Drive. The
feed reader then names a mount rather than carrying a password.

## Nothing is copied

The rows this returns are not `File` rows and nothing here writes one. A mount
is browsed live: `listing` asks the host what is in the folder, on the request,
and hands back rows in the shape the Drive's own list already draws.

That is the whole design decision, and the alternative — sync the listing into
`File` rows — fails on three counts at once. The rows would be stale between
syncs, which is the one thing a drop folder cannot be. They would count against
the workspace's storage quota, which measures bytes *we* are paying to keep.
And deleting one would be ambiguous in a way no confirmation dialog can fix.

The cost is honest and is paid in one place: there is no cross-mount search, no
favourite on a remote file, and a mount that is down is a folder that says so
rather than a folder that looks empty.

## What a remote row is called

`remote://<mount>/<path>` — the mount's own name, then the path under its base.
It travels everywhere a `File` name does: it is a row's `name`, it is what the
URL carries as `?folder=`, and `r2.download` takes it. Nothing stores one, so
there is no migration the day this changes.

`..` is refused on every path this takes, which is the only thing standing
between a `base_path` and the rest of the host's filesystem.

## Who may open one

`Remote Folder` is a System Manager doctype: it holds a credential, and a
workspace that lets anybody type one has a data exfiltration feature rather
than a file manager. Sharing works anyway and needed no code — a manager can
`DocShare` a mount to a colleague, and `has_permission` then answers yes for
them. The mount is the unit of sharing; a single remote file cannot be shared,
because there is no row to hang a share on.
"""

import io
import os
import posixpath
import socket
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from .kinds import ACTIVE, FOLDER, KIND_FIELD, OPENED_FIELD, STATUS_FIELD, TRASHED_FIELD, kind_of

#: What a remote name starts with. Chosen to look like a URL scheme because
#: that is what it is, and because anything shorter risks colliding with a
#: `File` name — Frappe names a folder `Home/Drawings`, and a prefix a person
#: could type as a folder name would be a prefix that eventually does.
PREFIX = "remote://"

#: The ports each protocol means when nobody says.
PORTS = {"SFTP": 22, "FTP": 21, "FTPS": 21}

PROTOCOLS = tuple(PORTS)

#: How long to wait on a host that has stopped answering. Long enough for an
#: authority's overloaded box, short enough that a browse does not hold a web
#: worker for the rest of the minute.
TIMEOUT = 30

#: The most one read will pull into memory. A remote file is fetched whole —
#: there is no object store to presign and no range request worth the code —
#: so this is the real ceiling on what the Drive can open from a mount.
MAX_BYTES = 256 * 1024 * 1024

#: One page of a directory. A drop folder with nine thousand deliveries in it
#: is a real thing, and the alternative to paging is a request that reads all
#: nine thousand and a browser that draws them.
PAGE = 200


# --------------------------------------------------------------------------- #
# Names
# --------------------------------------------------------------------------- #

def is_remote(name: str) -> bool:
	return (name or "").startswith(PREFIX)


def split(name: str) -> tuple[str, str]:
	"""`remote://drops/2026/june` -> `("drops", "/2026/june")`.

	The mount is everything up to the first slash, which is why a mount name
	may not contain one — `RemoteFolder.validate` refuses it there rather than
	letting this silently take half a name.
	"""
	rest = (name or "")[len(PREFIX):]
	mount, _sep, path = rest.partition("/")
	return mount, safe_path(path)


def idfor(mount: str, path: str = "/") -> str:
	return f"{PREFIX}{mount}{safe_path(path)}"


def safe_path(path: str) -> str:
	"""A path under the mount's base, with no way out of it.

	`..` is rejected rather than resolved, deliberately. Resolving is the
	version that looks correct and is not: `posixpath.normpath` on a path with
	a symlink in the middle of it gives an answer the server disagrees with,
	and a mount's whole security boundary is that the base path holds.
	"""
	path = "/" + (path or "").strip().strip("/")
	for part in path.split("/"):
		if part in ("..", "."):
			frappe.throw(_("That is not a path inside this folder."))
	return path.rstrip("/") or "/"


def deny(name: str, what: str = "") -> None:
	"""Refuse a mutation aimed at a mounted host.

	Every write in `writing.py` and `sharing.py` goes through a `File` row, and
	a `remote://` name has none — so without this the reader gets Frappe's
	"File remote://drops/june not found", which reads as a bug in the Drive
	rather than as the rule it is. Called on the argument rather than inside
	`_mine`, because the folder a move *targets* is one of the ways in.
	"""
	if is_remote(name):
		frappe.throw(what or _("That folder is on another server. Copy the file "
		                       "into the Drive first."))


def _join(base: str, path: str) -> str:
	"""The absolute path on the host: the mount's base plus the path under it."""
	return posixpath.normpath(posixpath.join("/" + (base or "").strip("/"), path.lstrip("/")))


# --------------------------------------------------------------------------- #
# The mount
# --------------------------------------------------------------------------- #

def mount_doc(mount: str, write: bool = False):
	"""One mount, if this person may have it.

	`check_permission` and not a role test: a manager who has shared the mount
	with a colleague has said that colleague may browse it, and the framework
	already knows.
	"""
	doc = frappe.get_doc("Remote Folder", mount)
	doc.check_permission("write" if write else "read")
	return doc


@contextmanager
def connect(doc):
	"""An open connection to one mount, closed whatever happens.

	Per call rather than pooled. A pool across requests would be a socket held
	open by a gunicorn worker that may not serve this workspace again for an
	hour, and the handshake is tens of milliseconds against a fetch measured in
	seconds.
	"""
	if doc.status == "Paused":
		frappe.throw(_("{0} is paused.").format(doc.name))

	port = cint(doc.port) or PORTS.get(doc.protocol, 22)
	if doc.protocol == "SFTP":
		client = _Sftp(doc, port)
	else:
		client = _Ftp(doc, port, secure=doc.protocol == "FTPS")
	try:
		yield client
	finally:
		client.close()


class _Sftp:
	"""paramiko, over a socket this opens so the timeout is ours.

	`paramiko.Transport((host, port))` builds its own socket with no timeout,
	which is how a host that accepts a connection and then says nothing holds a
	worker until the proxy gives up on it.
	"""

	def __init__(self, doc, port: int):
		try:
			import paramiko
		except ImportError:
			frappe.throw(_("SFTP needs paramiko, which is not installed on this site."))

		sock = socket.create_connection((doc.host, port), timeout=TIMEOUT)
		self.transport = paramiko.Transport(sock)
		self.transport.banner_timeout = TIMEOUT
		key = doc.get_password("private_key", raise_exception=False)
		if key:
			self.transport.connect(
				username=doc.username, pkey=_private_key(paramiko, key,
				                                         doc.get_password("secret", raise_exception=False))
			)
		else:
			self.transport.connect(
				username=doc.username,
				password=doc.get_password("secret", raise_exception=False),
			)
		self.client = paramiko.SFTPClient.from_transport(self.transport)

	def listdir(self, path: str) -> list[dict]:
		import stat as stats

		found = []
		for one in self.client.listdir_attr(path):
			found.append({
				"name": one.filename,
				"is_dir": stats.S_ISDIR(one.st_mode or 0),
				"size": one.st_size or 0,
				"mtime": one.st_mtime or 0,
			})
		return found

	def read(self, path: str, limit: int) -> bytes:
		buffer = io.BytesIO()
		self.client.getfo(path, buffer)
		if buffer.tell() > limit:
			frappe.throw(_("That file is larger than this can open in one go."))
		return buffer.getvalue()

	def size(self, path: str) -> int:
		return self.client.stat(path).st_size or 0

	def close(self):
		try:
			self.transport.close()
		except Exception:
			pass


def _private_key(paramiko, text: str, passphrase: str | None):
	"""A PEM, whichever of the four kinds it is.

	paramiko will not tell you which class parses a key, so the only way to
	find out is to try them — and the order matters only in that Ed25519 and
	ECDSA are what a host set up this decade will have issued.
	"""
	last = None
	for kind in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey, paramiko.DSSKey):
		try:
			return kind.from_private_key(io.StringIO(text), password=passphrase or None)
		except Exception as failed:
			last = failed
	frappe.throw(_("That private key could not be read: {0}").format(last))


class _Ftp:
	"""ftplib, with MLSD where the host has it and LIST where it does not.

	MLSD is the one that answers "is this a directory" without parsing a line
	meant for a human. Plenty of authority FTP servers predate it, so the
	fallback is NLST plus a `SIZE` probe — a directory is what `SIZE` refuses,
	which is ugly and is what every FTP client does.
	"""

	def __init__(self, doc, port: int, secure: bool):
		from ftplib import FTP, FTP_TLS

		self.ftp = FTP_TLS(timeout=TIMEOUT) if secure else FTP(timeout=TIMEOUT)
		self.ftp.connect(doc.host, port, timeout=TIMEOUT)
		self.ftp.login(
			user=doc.username or "anonymous",
			passwd=doc.get_password("secret", raise_exception=False) or "",
		)
		if secure:
			self.ftp.prot_p()
		self.ftp.set_pasv(True)

	def listdir(self, path: str) -> list[dict]:
		try:
			return [
				{
					"name": name,
					"is_dir": facts.get("type") in ("dir", "cdir", "pdir"),
					"size": cint(facts.get("size")),
					"mtime": _mlsd_time(facts.get("modify")),
				}
				for name, facts in self.ftp.mlsd(path)
				if name not in (".", "..") and facts.get("type") not in ("cdir", "pdir")
			]
		except Exception:
			return self._by_probe(path)

	def _by_probe(self, path: str) -> list[dict]:
		found = []
		for name in self.ftp.nlst(path):
			leaf = name.rsplit("/", 1)[-1]
			if leaf in (".", ".."):
				continue
			full = posixpath.join(path, leaf)
			try:
				# `SIZE` in binary mode is the portable "is this a file".
				self.ftp.voidcmd("TYPE I")
				size = self.ftp.size(full) or 0
				is_dir = False
			except Exception:
				size, is_dir = 0, True
			found.append({"name": leaf, "is_dir": is_dir, "size": size, "mtime": 0})
		return found

	def read(self, path: str, limit: int) -> bytes:
		buffer = io.BytesIO()

		def take(chunk):
			buffer.write(chunk)
			if buffer.tell() > limit:
				raise ValueError("too big")

		try:
			self.ftp.retrbinary(f"RETR {path}", take, blocksize=64 * 1024)
		except ValueError:
			frappe.throw(_("That file is larger than this can open in one go."))
		return buffer.getvalue()

	def size(self, path: str) -> int:
		self.ftp.voidcmd("TYPE I")
		return self.ftp.size(path) or 0

	def close(self):
		try:
			self.ftp.quit()
		except Exception:
			try:
				self.ftp.close()
			except Exception:
				pass


def _mlsd_time(stamp: str | None) -> float:
	"""`20260612153000` -> an epoch. MLSD's timestamps are UTC by the RFC."""
	from datetime import datetime, timezone

	if not stamp:
		return 0
	try:
		return datetime.strptime(stamp[:14], "%Y%m%d%H%M%S").replace(
			tzinfo=timezone.utc
		).timestamp()
	except ValueError:
		return 0


# --------------------------------------------------------------------------- #
# Rows in the Drive's shape
# --------------------------------------------------------------------------- #

def _row(mount: str, path: str, entry: dict) -> dict:
	"""One remote entry, as the row the Drive's list already draws.

	Every field the list reads, and no other: a row that is missing one is a
	column that renders `undefined`, and a row carrying an extra is a promise
	the next surface will try to act on. `owner` is empty rather than the
	reader — nobody here owns this file, and saying somebody does is how a
	details pane grows an avatar for a person who has never seen it.
	"""
	full = posixpath.join(path, entry["name"]) if path != "/" else "/" + entry["name"]
	when = _stamp(entry.get("mtime") or 0)
	return {
		"name": idfor(mount, full),
		"file_name": entry["name"],
		"file_url": "",
		"is_folder": 1 if entry["is_dir"] else 0,
		"folder": idfor(mount, path),
		"file_size": 0 if entry["is_dir"] else cint(entry.get("size")),
		"is_private": 1,
		"owner": "",
		"modified": when,
		"creation": when,
		"attached_to_doctype": None,
		"attached_to_name": None,
		KIND_FIELD: FOLDER if entry["is_dir"] else kind_of(entry["name"]),
		STATUS_FIELD: ACTIVE,
		TRASHED_FIELD: None,
		OPENED_FIELD: None,
		# Nothing on a mount can be favourited, shared or commented on: there
		# is no row to hang any of that off. The list reads these three, so
		# they are answered here rather than left for it to guess.
		"liked": False,
		"owner_person": {},
		"folder_label": path.rsplit("/", 1)[-1] or mount,
		# What tells every surface this row is not ours. `FileSurface` hides
		# the share and favourite controls on it, and `writing` refuses it.
		"remote": mount,
	}


def _stamp(epoch: float):
	from datetime import datetime

	if not epoch:
		return None
	try:
		return datetime.fromtimestamp(epoch)
	except (OverflowError, OSError, ValueError):
		return None


def listing(folder: str, search: str = "", start: int = 0, limit: int = PAGE,
            sort: str = "", descending: bool = False) -> dict:
	"""One page of one remote folder, in `reading.listing`'s own shape.

	Sorted and paged here rather than by the host, because neither protocol
	offers either: MLSD answers with a directory and SFTP with a list, and the
	client is where every FTP client has always done this.
	"""
	mount, path = split(folder)
	doc = mount_doc(mount)

	# Before the try, and this is the whole reason it is not inside it: a
	# paused mount is not a failing one, and routing it through `_failing`
	# rewrote the operator's own pause as Failing — so clicking a mount you had
	# just paused silently threw the pause away.
	if doc.status == "Paused":
		frappe.throw(_("{0} is paused.").format(doc.folder_name))

	try:
		with connect(doc) as client:
			entries = client.listdir(_join(doc.base_path, path))
	except Exception as failed:
		_failing(doc, failed)
		frappe.throw(_("{0} did not answer: {1}").format(doc.name, str(failed)[:200]))

	_connected(doc)

	rows = [_row(mount, path, one) for one in entries if not one["name"].startswith(".")]
	if search:
		needle = search.lower()
		rows = [one for one in rows if needle in one["file_name"].lower()]

	rows.sort(key=_order(sort), reverse=bool(descending))
	start, limit = max(0, cint(start)), max(1, min(cint(limit) or PAGE, PAGE))
	page = rows[start:start + limit + 1]
	more = len(page) > limit

	return {
		"files": page[:limit],
		"more": more,
		"place": "home",
		"folder": folder,
		"path": crumbs(folder),
		# A mount is read-only in the Drive whatever the host would allow. What
		# the Drive can do to a remote file is open it and copy it here; the
		# rest of the toolbar is about rows we own.
		"can_write": False,
		"sort": sort or "",
		"descending": bool(descending),
		"attached_to": None,
		"remote": {"mount": mount, "label": doc.folder_name, "host": doc.host,
		           "protocol": doc.protocol},
	}


def _order(sort: str):
	"""Folders first, then the chosen key — the same rule `query.ordering` keeps.

	A remote listing that mixed them would be the one list in the product that
	did, which reads as a bug in the Drive rather than as a property of FTP.
	"""
	if sort == "size":
		return lambda one: (not one["is_folder"], one["file_size"])
	if sort == "modified":
		return lambda one: (not one["is_folder"], one["modified"] or _stamp(0) or 0)
	if sort == "kind":
		return lambda one: (not one["is_folder"], one[KIND_FIELD])
	return lambda one: (not one["is_folder"], one["file_name"].lower())


def crumbs(name: str) -> list[dict]:
	"""The trail into a mount, the mount itself first.

	Built from the path rather than walked, which is the one thing a remote
	folder is easier at than a `File`: the parent of `/2026/june` is `/2026`
	and nothing has to be read to know it.
	"""
	mount, path = split(name)
	trail = [{"name": idfor(mount, "/"), "label": mount}]
	walked = ""
	for part in path.strip("/").split("/"):
		if not part:
			continue
		walked = f"{walked}/{part}"
		trail.append({"name": idfor(mount, walked), "label": part})
	return trail


def details(name: str) -> dict:
	"""One remote file, for the details pane.

	The size is asked for again rather than taken from the listing: the pane is
	opened from a list that may be minutes old, and "this is what is on the
	host now" is the only thing a mount can honestly say.
	"""
	mount, path = split(name)
	doc = mount_doc(mount)
	leaf = path.rsplit("/", 1)[-1]

	with connect(doc) as client:
		try:
			size = client.size(_join(doc.base_path, path))
			is_dir = False
		except Exception:
			size, is_dir = 0, True

	row = _row(mount, path.rsplit("/", 1)[0] or "/",
	           {"name": leaf, "is_dir": is_dir, "size": size, "mtime": 0})
	row["path"] = crumbs(name)[:-1]
	return row


# --------------------------------------------------------------------------- #
# Bytes
# --------------------------------------------------------------------------- #

def fetch(name: str) -> tuple[bytes, str]:
	"""The bytes of one remote file, and what it is called."""
	mount, path = split(name)
	doc = mount_doc(mount)
	with connect(doc) as client:
		content = client.read(_join(doc.base_path, path), MAX_BYTES)
	return content, path.rsplit("/", 1)[-1]


def newest(mount: str, path: str = "/", since: float = 0) -> tuple[bytes, str, float]:
	"""The newest file in a folder, if it is newer than `since`.

	The feed reader's whole question, and the reason this is a shared module
	rather than two: `onemobility.sources` used to open its own SFTP connection
	to ask exactly this, with its own copy of the host, the folder and the
	password. Returns empty bytes when there is nothing new, which is a poll
	that found nothing rather than a failure.
	"""
	doc = mount_doc(mount)
	with connect(doc) as client:
		base = _join(doc.base_path, safe_path(path))
		files = [one for one in client.listdir(base) if not one["is_dir"] and one["size"]]
		if not files:
			return b"", "", 0.0
		pick = max(files, key=lambda one: one["mtime"])
		if since and pick["mtime"] <= since:
			return b"", "", 0.0
		if pick["size"] > MAX_BYTES:
			frappe.throw(_("The delivery is larger than this can take in one fetch."))
		content = client.read(posixpath.join(base, pick["name"]), MAX_BYTES)
	return content, pick["name"], float(pick["mtime"] or 0)


# --------------------------------------------------------------------------- #
# State, written where somebody will read it
# --------------------------------------------------------------------------- #

def _connected(doc):
	if doc.status == "Connected" and doc.last_checked:
		# Every browse would otherwise be a write, and a mount somebody is
		# clicking through is one write per folder for no new information.
		return
	frappe.db.set_value("Remote Folder", doc.name, {
		"status": "Connected", "last_checked": now_datetime(), "last_message": "",
	}, update_modified=False)
	frappe.local.flags.commit = True


def _failing(doc, failed: Exception):
	# A paused mount keeps its status. The message is still worth writing —
	# "this is what it said when somebody last tried" — but a pause is a
	# decision and a failure is a symptom, and the symptom must not overwrite
	# the decision.
	if doc.status == "Paused":
		frappe.db.set_value("Remote Folder", doc.name, "last_message",
		                    str(failed)[:400], update_modified=False)
		frappe.db.commit()
		return

	frappe.db.set_value("Remote Folder", doc.name, {
		"status": "Failing", "last_checked": now_datetime(),
		"last_message": str(failed)[:400],
	}, update_modified=False)
	frappe.db.commit()


# --------------------------------------------------------------------------- #
# The endpoints
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def mounts() -> list[dict]:
	"""Every mount this person may browse, for the rail.

	`get_list`, so a mount a manager shared with a colleague is in the
	colleague's rail and nothing else is.
	"""
	return frappe.get_list(
		"Remote Folder",
		fields=["name", "folder_name", "protocol", "host", "status", "last_message"],
		order_by="folder_name asc",
		limit_page_length=0,
	)


@frappe.whitelist(methods=["POST"])
def connect_folder(folder_name: str, protocol: str, host: str, port: int = 0,
                   username: str = "", secret: str = "", private_key: str = "",
                   base_path: str = "/") -> dict:
	"""Make a mount, and prove it works before saying it does.

	The check is the point. A credential form that saves whatever you typed and
	fails silently at three in the morning is the form every FTP integration
	has, and the reason "is the feed running" is a question nobody can answer.
	Here the connection is opened, the base path is listed, and a mount that
	cannot do both is not created at all.
	"""
	if protocol not in PROTOCOLS:
		frappe.throw(_("That is not a protocol this can speak."))

	doc = frappe.get_doc({
		"doctype": "Remote Folder",
		"folder_name": (folder_name or "").strip(),
		"protocol": protocol,
		"host": (host or "").strip(),
		"port": cint(port),
		"username": username,
		"secret": secret,
		"private_key": private_key,
		"base_path": base_path or "/",
		"status": "Connected",
	})
	doc.insert()

	try:
		with connect(doc) as client:
			client.listdir(_join(doc.base_path, "/"))
	except Exception as failed:
		# Rolled back rather than kept as Failing: nothing has ever browsed
		# this mount, so there is nothing to preserve and a half-made one in
		# the rail is worse than the error.
		doc.delete(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("That did not connect: {0}").format(str(failed)[:200]))

	_connected(doc)
	return {"ok": True, "name": doc.name, "label": doc.folder_name,
	        "folder": idfor(doc.name, "/")}


@frappe.whitelist(methods=["POST"])
def check_remote(mount: str) -> dict:
	"""Try the connection now, and say so on the mount. The Recheck button."""
	doc = mount_doc(mount)
	try:
		with connect(doc) as client:
			found = client.listdir(_join(doc.base_path, "/"))
	except Exception as failed:
		_failing(doc, failed)
		return {"ok": False, "message": str(failed)[:400]}

	frappe.db.set_value("Remote Folder", doc.name, {
		"status": "Connected", "last_checked": now_datetime(), "last_message": "",
	}, update_modified=False)
	frappe.db.commit()
	return {"ok": True, "entries": len(found)}


@frappe.whitelist(methods=["POST"])
def set_paused(mount: str, paused: str | int = 1) -> dict:
	"""Stop reading a mount, or start again.

	Here rather than only on the doctype form because the moment you want it
	is the moment the host is misbehaving — an authority rotating a key at
	nine on a Monday — and the person looking at the red dot should not have
	to be taught where the desk is. Pausing stops the feeds too: `connect`
	refuses a paused mount whoever is asking.
	"""
	doc = mount_doc(mount, write=True)
	on = bool(frappe.utils.sbool(paused))
	frappe.db.set_value("Remote Folder", doc.name, {
		"status": "Paused" if on else "Connected",
		"last_message": _("Paused by hand.") if on else "",
	}, update_modified=False)
	frappe.db.commit()
	return {"ok": True, "paused": on}


@frappe.whitelist(methods=["POST"])
def disconnect(mount: str) -> dict:
	"""Forget a mount and its credential. Nothing on the host is touched.

	Refused while something reads it, in those words. Frappe's own link check
	would refuse it too and name a doctype and an id — which is true and is
	not what somebody deciding whether to disconnect a drop folder needs to
	read.
	"""
	doc = mount_doc(mount, write=True)
	readers = frappe.get_all(
		"Transit Source", filters={"remote_folder": doc.name}, pluck="name", limit=5
	)
	if readers:
		frappe.throw(_("{0} is read by {1}. Point those somewhere else first.").format(
			doc.folder_name, ", ".join(readers)
		))

	doc.delete()
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def copy_here(name: str, folder: str = "") -> dict:
	"""Bring one remote file into the Drive, as a real `File`.

	The one write this module has, and the seam between the two halves: before
	it the file is somebody else's and weighs nothing here; after it, it is a
	row this workspace owns, counts, versions and can share. A copy and never a
	move — a drop folder is the authority's and emptying it is not ours to do.
	"""
	if folder and is_remote(folder):
		frappe.throw(_("Files can only be copied into the Drive, not onto a host."))

	content, leaf = fetch(name)
	if not content:
		frappe.throw(_("There is nothing at that path."))

	doc = frappe.get_doc({
		"doctype": "File",
		"file_name": leaf,
		"is_private": 1,
		"folder": folder or "Home",
		"content": content,
	}).insert()
	return {"ok": True, "name": doc.name, "label": doc.file_name,
	        "size": len(content)}
