"""Every file under one folder, wherever that folder actually lives.

`reading.py` answers "one page of this folder, for a person looking at it".
This answers the other question — "everything under here, for a machine that
is going to read all of it" — and it answers it the same way for a folder in
the Drive and for a folder on somebody else's SFTP host.

That sameness is the whole point. A workspace pointing a feed at a drop folder
and a workspace dragging last year's exports into the Drive are doing one
thing, and a caller that branched on which would be two code paths where the
customer sees one gesture. So a folder is addressed by a single string:

    `a File.name`          a folder in the Drive — uploaded, synced, made here
    `remote://mount/path`  a folder on a mounted host — SFTP, FTP, SMB, WebDAV

and `entries` returns the same shape for both.

Three things this deliberately does not do.

**It does not read the bytes.** A drop folder with nine thousand deliveries in
it is a real thing, and a walk that fetched each one to describe it would pull
a hundred gigabytes through a worker to answer a question about names. `read`
is separate, and a caller that only wants the new ones calls it for those.

**It does not recurse for ever.** `DEPTH` is four, which covers every layout
anybody actually uses — `2026/06/`, `incoming/bvg/`, a GTFS folder inside a
dated one — and refuses the symlink loop and the mounted root that would
otherwise be a walk nobody can stop.

**It does not sort by name.** Oldest first, by the time the host says the file
was written, because a caller working through a backlog has to apply the
deliveries in the order they were made. A supplier whose script names files
`export_1.dat` … `export_10.dat` sorts wrong by name and right by clock.
"""

import posixpath

import frappe
from frappe.utils import cint, get_datetime

from . import remote
from .kinds import ACTIVE, STATUS_FIELD

#: How far down. Four levels covers a dated tree (`2026/06/12/`) with a feed
#: folder at the bottom, and stops a mount rooted at `/` from being a walk of
#: somebody's whole server.
DEPTH = 4

#: The most entries one walk will describe. Past this the answer is truncated
#: and says so, because a caller that silently saw the first two thousand of
#: nine thousand files is a caller quietly skipping deliveries.
CAP = 2000


class Entry:
	"""One file or folder under the walked root.

	`key` is what `read` takes and what a caller stores to remember that this
	one has been seen: a `File.name` in the Drive, a `remote://` id on a
	mount. `path` is relative to the root and is what a person recognises —
	`2026/06/bvg_export.zip` — so it is what goes on screen and in a log.
	"""

	__slots__ = ("key", "path", "name", "size", "modified", "is_folder")

	def __init__(self, key: str, path: str, name: str, size: int,
	             modified: float, is_folder: bool = False):
		self.key = key
		self.path = path
		self.name = name
		self.size = cint(size)
		self.modified = float(modified or 0)
		self.is_folder = bool(is_folder)

	def __repr__(self) -> str:
		return f"<Entry {self.path}{'/' if self.is_folder else ''} {self.size}B>"

	def as_dict(self) -> dict:
		return {
			"key": self.key,
			"path": self.path,
			"name": self.name,
			"size": self.size,
			"modified": self.modified,
			"is_folder": self.is_folder,
		}


def is_folder_key(folder: str) -> bool:
	"""Whether this names a folder at all, without asking the host.

	Cheap on purpose: called to validate a form field, where reaching an SFTP
	box to find out would make a save take thirty seconds.
	"""
	if not folder:
		return False
	if remote.is_remote(folder):
		return True
	return bool(frappe.db.get_value("File", folder, "is_folder"))


def label(folder: str) -> str:
	"""What to call this folder on screen."""
	if not folder:
		return ""
	if remote.is_remote(folder):
		mount, path = remote.split(folder)
		return f"{mount}{path}" if path != "/" else mount
	return frappe.db.get_value("File", folder, "file_name") or folder


def entries(folder: str, depth: int = DEPTH, cap: int = CAP,
            folders: bool = False) -> list[Entry]:
	"""Everything under `folder`, oldest first.

	Folders are walked into and left out of the answer unless `folders` is
	set — a caller reading deliveries wants files, and a caller deciding
	whether a *directory* is itself one feed (a GTFS export unzipped) wants
	the level it is looking at.
	"""
	if not folder:
		return []

	found: list[Entry] = []
	queue: list[tuple[str, str, int]] = [(folder, "", 0)]

	while queue and len(found) < cap:
		here, prefix, deep = queue.pop(0)
		for one in _level(here, prefix):
			if one.is_folder:
				if folders:
					found.append(one)
				if deep + 1 < depth:
					queue.append((one.key, one.path, deep + 1))
				continue
			found.append(one)
			if len(found) >= cap:
				break

	found.sort(key=lambda one: (one.modified, one.path))
	return found


def _level(folder: str, prefix: str) -> list[Entry]:
	"""One directory, not recursed. The only place the two worlds differ."""
	if remote.is_remote(folder):
		return _remote_level(folder, prefix)
	return _drive_level(folder, prefix)


def _drive_level(folder: str, prefix: str) -> list[Entry]:
	"""A folder in the Drive.

	`get_all` rather than a hand-written query, so a person who may not read
	half of this folder walks the half they may — the permission is the
	framework's and is not re-implemented here.
	"""
	rows = frappe.get_all(
		"File",
		filters={"folder": folder, STATUS_FIELD: ("in", (ACTIVE, "", None))},
		fields=["name", "file_name", "is_folder", "file_size", "modified"],
		limit_page_length=CAP,
	)
	out = []
	for row in rows:
		if not row.file_name:
			continue
		out.append(Entry(
			key=row.name,
			path=posixpath.join(prefix, row.file_name) if prefix else row.file_name,
			name=row.file_name,
			size=row.file_size,
			modified=get_datetime(row.modified).timestamp() if row.modified else 0,
			is_folder=bool(row.is_folder),
		))
	return out


def _remote_level(folder: str, prefix: str) -> list[Entry]:
	"""A folder on a mounted host.

	One connection per directory, which is what `remote.connect` is shaped
	for and is why a deep walk over a slow host is slow: there is no protocol
	here that lists a tree in one call.
	"""
	mount, path = remote.split(folder)
	listed = remote.listdir(folder)

	out = []
	for one in listed:
		name = one["name"]
		full = posixpath.join(path, name) if path != "/" else "/" + name
		out.append(Entry(
			key=remote.idfor(mount, full),
			path=posixpath.join(prefix, name) if prefix else name,
			name=name,
			size=one.get("size"),
			modified=one.get("mtime") or 0,
			is_folder=bool(one["is_dir"]),
		))
	return out


def read(key: str) -> bytes:
	"""The bytes of one entry, from whichever side it is on."""
	if remote.is_remote(key):
		content, _named = remote.fetch(key)
		return content

	doc = frappe.get_doc("File", key)
	doc.check_permission("read")
	content = doc.get_content()
	if isinstance(content, str):
		content = content.encode("utf-8")
	return content or b""


@frappe.whitelist(methods=["GET"])
def preview(folder: str, limit: int = 40) -> dict:
	"""What a walk of this folder would find, for a form to show before saving.

	The reason a source's folder field is worth a picker rather than a text
	box: somebody typing a path wants to know they typed the right one, and
	"nothing here" is the answer they need *before* they wait an hour for a
	poll to say it.
	"""
	if not folder:
		return {"folder": "", "label": "", "files": [], "more": False}

	found = entries(folder, cap=cint(limit) + 1)
	return {
		"folder": folder,
		"label": label(folder),
		"files": [one.as_dict() for one in found[: cint(limit)]],
		"more": len(found) > cint(limit),
	}
