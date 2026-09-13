"""What a share is scoped *to*, when it is not a folder.

`Drive Access.folder` was a `Link` to a `File`, and `dav.py` resolved a share
by walking down from it. That made every place in the rail unmountable, because
every one of them is a `where` clause rather than a folder — Recents,
Favourites, Templates, and crucially *a record's attachments* and *a doctype's
attachments*. The one thing people ask to mount was the one thing the share
model could not name.

So a scope is a string with a kind in front of it:

    folder:Home/Drawings            what a `folder` link used to mean
    doctype:Quotation               every file attached to any quotation
    document:Quotation/QTN-0001     one record's files
    place:favourites                a rail place

and the tree under it is assembled from `query.py`'s own filters at the moment
it is asked for. Nothing is created, so there is nothing to keep in step: a
mounted `doctype:Quotation` grows a `QTN-0001/` directory the instant a file is
attached to that quotation and loses it when the last one goes.

## Why not a real folder per record

Asked and answered in `docs/UNIFICATION.md` §E1. A folder per record is a
`File` row per record — four thousand quotations is four thousand rows, created
eagerly or on first attach — and it puts renaming a record in the business of
moving a folder and deleting one in the business of a cascade. It also breaks
the sentence the whole module rests on, which `query.py` states: *there is no
second store behind any of them*.

## What a node is

Resolving a path under a scope answers with a `Node`, which is one of three
things:

* a **file** — a real `File` row, which is what `GET`, `PUT` and `DELETE` act on
* a **folder** — a real `File` row that is a folder
* a **virtual** directory — no row at all, listed from a query

A virtual directory knows what it is *about*: a doctype, or one record. That is
what makes a write into it meaningful — dropping a PDF into `QTN-0001/` is an
attachment on that quotation, and the permission checked is the record's.
"""

from dataclasses import dataclass, field as dataclass_field

import frappe
from frappe import _

from .kinds import ACTIVE, STATUS_FIELD
from .query import PLACES, RECORD, ROOT, _place_filters

#: The kinds a scope string may carry, in the order they were added. `folder`
#: is first because it is what every existing row means.
FOLDER = "folder"
DOCTYPE = "doctype"
DOCUMENT = "document"
PLACE = "place"

KINDS = (FOLDER, DOCTYPE, DOCUMENT, PLACE)

#: The fields every listing reads. One tuple, because a row that came back
#: without `is_folder` is a file the client will not walk into.
FIELDS = ("name", "file_name", "is_folder", "file_size", "modified", "creation")


@dataclass
class Node:
	"""One thing at a path: a file, a folder, or a directory that is a query.

	`row` is the `File` this is, where there is one. `about` is the record a
	virtual directory stands for, as `(doctype, docname)` — which is what a
	`PUT` into it attaches to. `doctype` is set on the directory *above* those,
	the one that lists a doctype's records.
	"""

	label: str
	is_folder: bool
	row: dict | None = None
	about: tuple[str, str] | None = None
	doctype: str = ""
	#: Set on a virtual directory so a listing does not have to ask twice.
	filters: dict = dataclass_field(default_factory=dict)

	@property
	def virtual(self) -> bool:
		return self.row is None


def parse(scope: str) -> tuple[str, str]:
	"""`"doctype:Quotation"` → `("doctype", "Quotation")`.

	A string with no kind in front of it is a folder, which is what every row
	written before this module said. That is the whole of the migration: the
	old `folder` value is a valid scope as it stands.
	"""
	text = (scope or "").strip()
	if not text:
		return FOLDER, ""
	kind, _, rest = text.partition(":")
	if kind not in KINDS:
		return FOLDER, text
	return kind, rest.strip()


def label(scope: str) -> str:
	"""What the scope is called, for a mount that has no label of its own."""
	kind, value = parse(scope)
	if kind == FOLDER:
		return (value or ROOT).split("/")[-1]
	if kind == DOCTYPE:
		return value
	if kind == DOCUMENT:
		return value.split("/")[-1]
	return value.title()


def validate(scope: str) -> None:
	"""Refuse a scope nothing can resolve, at the moment it is written.

	A key whose scope is a typo is a mount that answers 404 to everything, and
	the person who made it finds out in Finder rather than here.
	"""
	kind, value = parse(scope)
	if kind == FOLDER:
		if value and not frappe.db.exists("File", {"name": value, "is_folder": 1}):
			frappe.throw(_("There is no folder called {0}.").format(value))
	elif kind == DOCTYPE:
		if not value or not frappe.db.exists("DocType", value):
			frappe.throw(_("There is nothing called {0} to share.").format(value or "—"))
	elif kind == DOCUMENT:
		doctype, _sep, docname = value.partition("/")
		if not doctype or not docname or not frappe.db.exists(doctype, docname):
			frappe.throw(_("There is no record at {0}.").format(value or "—"))
	elif kind == PLACE:
		if value not in PLACES or value == RECORD:
			frappe.throw(_("There is no place called {0}.").format(value or "—"))


def root(scope: str) -> Node:
	"""The top of the tree a scope opens onto."""
	kind, value = parse(scope)

	if kind == FOLDER:
		row = frappe.db.get_value("File", value or ROOT, list(FIELDS), as_dict=True)
		if not row:
			return None
		return Node(label=row.file_name or ROOT, is_folder=True, row=row)

	if kind == DOCTYPE:
		return Node(label=value, is_folder=True, doctype=value)

	if kind == DOCUMENT:
		doctype, _sep, docname = value.partition("/")
		return Node(label=docname, is_folder=True, about=(doctype, docname))

	filters, _or = _place_filters(value)
	return Node(label=value.title(), is_folder=True, filters=filters)


def children(node: Node) -> list[Node]:
	"""What is inside one node, as nodes.

	Three shapes, and each is one query:

	* a doctype directory lists the *records* that have a file attached, as
	  virtual directories named for the record
	* a record directory lists that record's files
	* a real folder lists what is in it, and a place lists what it matches

	`get_list` throughout, never `get_all`: a key acts as the person who made
	it, and this is the query that applies that. A scope over a doctype the
	owner cannot read is an empty directory rather than an error, which is the
	right answer — the share is not secret, its contents are.
	"""
	if node.doctype:
		return _records_of(node.doctype)
	if node.about:
		doctype, docname = node.about
		return _files_of(node, {"attached_to_doctype": doctype,
		                        "attached_to_name": docname})
	if node.row:
		return _files_of(node, {"folder": node.row["name"]})
	return _files_of(node, dict(node.filters))


def _records_of(doctype: str) -> list[Node]:
	"""One virtual directory per record that has a file on it.

	Distinct over the attachment rows rather than over the doctype's own table:
	a directory per quotation would be four thousand empty directories, and the
	thing being mounted is the files.
	"""
	rows = frappe.get_list(
		"File",
		filters={"attached_to_doctype": doctype,
		         STATUS_FIELD: ["in", [ACTIVE, "", None]]},
		fields=["attached_to_name"],
		group_by="attached_to_name",
		order_by="attached_to_name asc",
		limit_page_length=0,
	)
	found = []
	for row in rows:
		docname = row.get("attached_to_name")
		if not docname:
			continue
		found.append(Node(label=docname, is_folder=True, about=(doctype, docname)))
	return found


def _files_of(node: Node, filters: dict) -> list[Node]:
	filters.setdefault(STATUS_FIELD, ["in", [ACTIVE, "", None]])
	# The drive's root is a file row like any other and listing it inside
	# itself is a loop back to where you already are.
	filters.setdefault("name", ["!=", ROOT])
	rows = frappe.get_list(
		"File",
		filters=filters,
		fields=list(FIELDS),
		order_by="is_folder desc, file_name asc",
		limit_page_length=0,
	)
	return [
		Node(label=row.file_name, is_folder=bool(row.is_folder), row=row)
		for row in rows
		if row.file_name
	]


def step(node: Node, segment: str) -> Node | None:
	"""One segment down from a node, or `None` where there is nothing there.

	By label and not by id, the same way `dav.py` has always walked: a client's
	path is names all the way down, and Frappe's `Home/Drawings` id comes apart
	the moment anything is renamed.
	"""
	if not node.is_folder:
		return None
	for child in children(node):
		if child.label == segment:
			return child
	return None


def walk(scope: str, parts: list[str]) -> tuple[Node | None, Node | None, str]:
	"""Resolve a whole path.

	Answers `(node, None, "")` for something that is there, and
	`(None, parent, leaf)` when everything but the last segment is — which is
	what `PUT` and `MKCOL` need in order to make one.
	"""
	at = root(scope)
	if at is None:
		return None, None, ""
	for index, segment in enumerate(parts):
		nxt = step(at, segment)
		if nxt is None:
			if index == len(parts) - 1:
				return None, at, segment
			return None, None, ""
		at = nxt
	return at, None, ""


def writable_into(node: Node) -> tuple[str, str, str]:
	"""Where a file written into this directory goes.

	Returns `(folder, attached_to_doctype, attached_to_name)`, of which at most
	one half is filled: a real folder takes a `folder`, a record's directory
	takes the attachment triple, and a doctype's directory takes neither —
	there is no record to attach to, so writing there is refused rather than
	guessed at.
	"""
	if node.about:
		return "", node.about[0], node.about[1]
	if node.row:
		return node.row["name"], "", ""
	return "", "", ""
