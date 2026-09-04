"""What surrounds a record: its timeline, files, comments, likes.

Comments, the change log, who liked it. All of it is Frappe's own, on every
doctype, and none of it needs a space to ask for it.
"""

import frappe
from frappe import _
from .meta import HIDDEN, _filter_rows
from .resolve import _resolve
from .records import record


TIMELINE_PAGE = 50


@frappe.whitelist(methods=["GET"])
def timeline(space_code: str, screen: str, name: str) -> dict:
	"""A record's comments and its history, newest first."""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		return {"comments": [], "changes": [], "likes": [], "liked": False}

	# Reading the document is the permission check: `get_doc` raises when this
	# user may not, and a timeline is no less private than the record it is on.
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	# Imported here rather than at the top: `notifications` reads screens
	# through this module, so a module-level import either way is a cycle.
	from oneapp.oneapp_core import notifications as follow

	comments = frappe.get_all(
		"Comment",
		filters={"reference_doctype": doctype, "reference_name": name,
		         "comment_type": "Comment"},
		fields=["name", "content", "comment_email", "comment_by", "creation"],
		order_by="creation desc",
		limit_page_length=TIMELINE_PAGE,
	)

	changes = []
	if resolved.get("track_changes"):
		changes = frappe.get_all(
			"Version",
			filters={"ref_doctype": doctype, "docname": name},
			fields=["name", "owner", "creation", "data"],
			order_by="creation desc",
			limit_page_length=TIMELINE_PAGE,
		)
		changes = [_change(row, resolved, _names(changes)) for row in changes]
		changes = [row for row in changes if row["entries"]]

	liked = frappe.parse_json(doc.get("_liked_by") or "[]")

	return {
		"comments": comments,
		# How many there are, not how many came back. The page is capped at 50,
		# so on a record with more than that the count derived from the list
		# stopped moving when a comment was added — the badge said 50 for ever.
		# Frappe keeps the same number on the document itself.
		#
		# It keeps the last hundred and no more, so past that this saturates.
		# The desk's number is this number, and the alternative — a count query
		# per row — is a query per row.
		"comment_count": len(frappe.parse_json(doc.get("_comments") or "[]")),
		"changes": changes,
		"more_comments": len(comments) >= TIMELINE_PAGE,
		"likes": liked,
		"liked": frappe.session.user in liked,
		"can_comment": True,
		# Following, on the same request as the likes and for the same reason:
		# it is the record's social state, the reader is already waiting for
		# this call, and a second round trip to draw one bell is a second round
		# trip. `can_follow` because a doctype whose changes are not tracked has
		# nothing to report, and a control that cannot work should not be drawn.
		"can_follow": follow.followable(doctype),
		"following": follow.is_following(doctype, name),
	}


def _names(rows: list[dict]) -> dict:
	"""Who wrote these versions, by their full names.

	A Version stores `owner`, which is a user id and on this product an email
	address. The timeline showed it raw, so a change read `robin@acme.test` two
	lines under a comment by `Robin Vale` — the same person, named two ways, in
	one column.

	One query for the whole page rather than one per row: a timeline is twenty
	entries and twenty `get_value` calls is twenty round trips for a column of
	names.
	"""
	ids = sorted({row["owner"] for row in rows if row.get("owner")})
	if not ids:
		return {}
	found = frappe.get_all("User", filters={"name": ("in", ids)},
	                       fields=["name", "full_name"])
	return {row["name"]: row["full_name"] or row["name"] for row in found}


def _change(row: dict, resolved: dict, names: dict | None = None) -> dict:
	"""One version, in the words of the screen rather than of the database.

	Frappe stores a Version as raw field names and values. Rendering that as-is
	gives a customer `grand_total: 120.0 → 140.0` for a field their screen calls
	"Total"; the labels are already resolved on the columns, so use them.
	"""
	columns = {c["fieldname"]: c for c in resolved.get("columns") or []}

	try:
		data = frappe.parse_json(row.get("data") or "{}")
	except Exception:
		data = {}

	entries = []
	for fieldname, before, after in (data.get("changed") or []):
		column = columns.get(fieldname)
		if fieldname in HIDDEN or not column:
			# Only what this screen shows. A change to a field the customer
			# cannot see reads as noise about something that does not exist.
			continue
		entries.append({
			"label": column["label"],
			"from": _said(column, before),
			"to": _said(column, after),
		})

	return {
		"name": row["name"],
		"by": (names or {}).get(row["owner"]) or row["owner"],
		# The id as well, because the avatar beside the name is drawn from it
		# and a face keyed on "Robin Vale" is a face that changes when somebody
		# corrects their own name.
		"by_id": row["owner"],
		"on": row["creation"],
		"entries": entries,
	}


# The fieldtypes whose value is markup rather than words. A Version keeps what
# was stored, so a Text Editor's history is a line of `<p>` tags — which is
# what the record used to show on its timeline, tags and all.
MARKUP_TYPES = ("Text Editor", "HTML Editor", "Markdown Editor", "HTML", "Code")


def _said(column: dict, value) -> str:
	"""One side of a change, as a person reads it.

	Only the markup fieldtypes are stripped, and deliberately: a Data field
	holding `a < b` is a Data field holding `a < b`, and running every value
	through an HTML stripper to tidy one fieldtype is how that becomes `a `.
	"""
	if value is None:
		return ""
	if column.get("fieldtype") not in MARKUP_TYPES:
		return value
	return frappe.utils.strip_html(str(value)).strip()


# What a File row carries that is worth showing. `file_size` in bytes, because
# the browser knows how to say "1.2 MB" in the reader's own locale and the
# server does not know what that is.
FILE_FIELDS = ("name", "file_name", "file_url", "file_size", "is_private", "creation", "owner")


def _attachable(space_code: str, screen: str, name: str) -> str:
	"""The doctype of a record this screen may open, or a refusal.

	Reading the document is the permission check, the same one the timeline
	makes: `get_doc` raises when this user may not, and what is attached to a
	record is no less private than the record.
	"""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("This screen has no records to attach anything to."))
	frappe.get_doc(doctype, name).check_permission("read")
	return doctype


@frappe.whitelist(methods=["GET"])
def attachments(space_code: str, screen: str, name: str,
                fieldname: str | None = None) -> dict:
	"""Everything filed against one record.

	Frappe's own File rows, which is what the desk's sidebar lists and what an
	Attach field points at — so a file uploaded through a field and a file
	dropped on the record are one list rather than two.

	`fieldname` narrows the list to one Attachment Gallery's share of them.
	That fieldtype holds no value: Frappe's own control renders the record's
	attachments and narrows them by `link_filters` on the docfield, so a
	doctype with two galleries filters each to the files it wants. Reading the
	filter off the docfield rather than taking one from the caller is the
	point — a client that could send its own filter could read any File row on
	the site.
	"""
	doctype = _attachable(space_code, screen, name)
	filters = {"attached_to_doctype": doctype, "attached_to_name": name}
	filters.update(_gallery_filters(space_code, screen, fieldname))

	found = frappe.get_all(
		"File",
		filters=filters,
		fields=list(FILE_FIELDS),
		order_by="creation desc",
	)
	return {"files": found, "doctype": doctype}


def _gallery_filters(space_code: str, screen: str, fieldname: str | None) -> dict:
	"""What one Attachment Gallery narrows the record's attachments to.

	The docfield's own `link_filters`, read by `_filter_rows` — so a row naming
	anything but File is refused, exactly as
	`frappe.desk.form.load.get_filtered_attachments` refuses one.

	A field that is not a gallery, or one with no filters, narrows nothing.
	Silently: a doctype that renamed a field should show all its attachments
	rather than fail to open.
	"""
	if not fieldname:
		return {}

	resolved = _resolve(space_code, screen)
	offered = resolved.get("all_columns") or resolved.get("columns") or []
	column = next((c for c in offered if c["fieldname"] == fieldname), None)
	if not column or column["fieldtype"] != "Attachment Gallery":
		return {}

	return {
		fieldname: [operator, value]
		for _dt, fieldname, operator, value
		in _filter_rows(column.get("link_filters"), "File")
	}


@frappe.whitelist(methods=["POST"])
def remove_attachment(space_code: str, screen: str, name: str, file: str) -> dict:
	"""Take one file off a record.

	Writing the record is the permission: removing what is filed against
	something is a change to it, even though the row being deleted is a File.
	And the file has to be attached to *this* record — a File name arriving in
	the payload is a File name somebody sent.
	"""
	doctype = _attachable(space_code, screen, name)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")

	attached = frappe.db.get_value(
		"File", file, ["attached_to_doctype", "attached_to_name"], as_dict=True
	)
	if not attached or (attached.attached_to_doctype, attached.attached_to_name) != (doctype, name):
		frappe.throw(_("That file is not on this record."), frappe.PermissionError)

	frappe.delete_doc("File", file)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def comment(space_code: str, screen: str, name: str, content: str) -> dict:
	"""Add a comment to a record, through the screen that may reach it."""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("There is nothing to comment on here."))

	content = (content or "").strip()
	if not content:
		frappe.throw(_("A comment needs something in it."))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	added = frappe.get_doc({
		"doctype": "Comment",
		"comment_type": "Comment",
		"reference_doctype": doctype,
		"reference_name": name,
		"content": content[:5000],
		"comment_email": frappe.session.user,
		"comment_by": frappe.utils.get_fullname(frappe.session.user),
	}).insert(ignore_permissions=True)

	return {"name": added.name}


@frappe.whitelist(methods=["POST"])
def toggle_like(space_code: str, screen: str, name: str) -> dict:
	"""Frappe keeps likes in `_liked_by` on the document itself."""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("There is nothing to like here."))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	from frappe.desk.like import toggle_like as frappe_toggle

	liked = frappe.parse_json(doc.get("_liked_by") or "[]")
	frappe_toggle(doctype, name, add="No" if frappe.session.user in liked else "Yes")

	# Re-read rather than assume: the like is written by Frappe, and reporting
	# the state we intended rather than the state that exists is how a toggle
	# ends up out of step with its own icon.
	after = frappe.parse_json(
		frappe.db.get_value(doctype, name, "_liked_by") or "[]")
	return {"liked": frappe.session.user in after, "likes": after}


@frappe.whitelist(methods=["POST"])
def rename(space_code: str, screen: str, name: str, new_name: str) -> dict:
	"""Give this record a different id.

	Through `frappe.rename_doc`, which is not a nicety: an id is a foreign key
	in every Link field pointing at it, in `_assign`, in every Comment, File,
	ToDo, Version and Document Follow row that references it, and in the child
	tables it parents. The framework's own rename updates all of them in one
	transaction. An `UPDATE ... SET name` would leave a workspace full of links
	to a record that no longer exists.

	Renaming the *title* is not this: the title is an ordinary field on the
	form, and changing it is a save. This changes the id, which is why it is
	behind `allow_rename` and lives beside the id rather than beside the title.
	"""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("There is nothing to rename here."))

	wanted = (new_name or "").strip()
	if not wanted:
		frappe.throw(_("A record needs an id."))
	if wanted == name:
		return {"name": name}

	# The screen's own reach, not `get_doc`: a record this screen would not
	# list is not a record this screen may rename. `record()` already applies
	# the filters and User Permissions, so an empty answer is a refusal.
	if not record(space_code, screen, name):
		frappe.throw(_("There is nothing to rename here."))

	# `allow_rename` is re-read here rather than trusted from the spec the
	# browser was sent: a flag that decides whether a button is drawn and a
	# flag that decides whether a write happens have to be the same flag, read
	# at the same moment.
	frappe.get_doc(doctype, name).check_permission("write")

	from frappe.model.rename_doc import update_document_title

	# `enqueue=False`: the reader is looking at the record and the URL has to
	# change to the new id when this answers. Frappe enqueues for the desk
	# because a rename of something with thousands of links is slow — that is
	# a real limit and it belongs in the copy beside the control rather than in
	# a background job whose result nobody is watching for.
	return {
		"name": update_document_title(
			doctype=doctype, docname=name, name=wanted, enqueue=False
		)
	}


@frappe.whitelist(methods=["POST"])
def toggle_follow(space_code: str, screen: str, name: str) -> dict:
	"""Follow this record, or stop.

	The store is Frappe's `Document Follow`; the delivery is ours, because the
	framework only ever built a digest email. See `oneapp_core.notifications`.
	"""
	from oneapp.oneapp_core import notifications as follow

	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("There is nothing to follow here."))

	if not follow.followable(doctype):
		frappe.throw(_("This kind of record does not report its changes."))

	# Reading the document is the permission: being told when something changes
	# is exactly as private as being able to look at it.
	frappe.get_doc(doctype, name).check_permission("read")

	wanted = not follow.is_following(doctype, name)
	return {"following": follow.set_following(doctype, name, wanted)}
