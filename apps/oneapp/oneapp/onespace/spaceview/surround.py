"""What surrounds a record: its timeline, files, comments, likes.

Comments, the change log, who liked it. All of it is Frappe's own, on every
doctype, and none of it needs a space to ask for it.

**And the timeline is everything at once.** `docs/ONECRM.md` stage 3: it held a
comment, a field change and the creation, so "what happened on this deal" meant
reading the Activity tab, then the Mail tab, then the Files tab and merging
them by eye — and a call had nowhere to be at all. Frappe CRM merges seven
kinds into one column and it is the best thing in that app.

So the sources are a **registry**: each one is a function that turns a record
into typed entries, and `SOURCES` is the list. A kind that does not apply
answers nothing — mail on a doctype nobody has written about, files on a record
with no attachments — and a kind that does not exist yet is one line when it
does. That is the whole reason this is a list rather than four queries in a
row: `One Call` joins it in stage 5 without this function changing.

Every source reads on the **reader's** behalf. A record is not a key that
unlocks the mail about it — `spaceview/mail.py` is emphatic about why — so a
timeline entry can only be one this person could have found anyway.
"""

import frappe
from frappe import _
from .meta import HIDDEN, _filter_rows
from .resolve import _resolve
from .records import record


TIMELINE_PAGE = 50

#: How many entries the merged column carries, across every kind.
#:
#: Each source is capped at `TIMELINE_PAGE` of its own, so a record with four
#: hundred emails does not crowd out its four comments; the merge then takes
#: the newest of what came back. Both caps matter: the first keeps one loud
#: kind from filling the page, the second keeps the page a page.
TIMELINE_ENTRIES = 120


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
	from oneapp.onespace import notifications as follow

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
		# One column, newest first — see the module docstring. The two lists
		# below it are the same rows in their own shapes, kept because the
		# comment composer and the unsaved-changes banner read them directly
		# and neither wants to filter a merged list to find its half.
		"entries": _entries(doctype, name, resolved, comments, changes, doc),
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


# --------------------------------------------------------------------------- #
# One column, out of every kind of thing that happens to a record
#
# A source is `(doctype, name, resolved) -> [entry]`, and an entry is a dict
# with a `kind`, a `key`, an `on` and a `by`. Everything else is the kind's
# own and the browser draws it — which is what makes adding one a line here
# and a branch there rather than a change to the merge.
#
# Ordered by how loud each is rather than by importance: the two that are
# already in hand cost nothing, and the two that query come last so a record
# with neither pays for neither.
# --------------------------------------------------------------------------- #

def _entries(doctype, name, resolved, comments, changes, doc) -> list[dict]:
	"""Everything that has happened to this record, newest first."""
	entries = [
		*_said_entries(comments),
		*_change_entries(changes),
		*_creation_entry(doc, resolved),
	]
	entries += _gather(doctype, name, resolved)
	entries += _inherited_entries(doc, resolved)
	entries.sort(key=lambda one: str(one.get("on") or ""), reverse=True)
	return entries[:TIMELINE_ENTRIES]


def _gather(doctype: str, name: str, resolved: dict) -> list[dict]:
	"""Every registered source, run against one record."""
	found = []
	for source in SOURCES:
		try:
			found += source(doctype, name, resolved) or []
		except Exception:
			# A source that cannot answer must not take the column with it: a
			# timeline missing its mail is worth more than a record that will
			# not open. `onemail` is the one that can be absent — a bench
			# without it, a doctype nothing is linked to — and the rest are
			# reads that a permission can refuse.
			frappe.clear_last_message()
	return found


def _said_entries(comments) -> list[dict]:
	"""What people said about it."""
	return [{
		"kind": "comment",
		"key": f"comment:{one['name']}",
		"on": one.get("creation"),
		"by": one.get("comment_by") or one.get("comment_email"),
		"by_id": one.get("comment_email"),
		"content": one.get("content"),
	} for one in comments]


def _change_entries(changes) -> list[dict]:
	"""What changed on it, already resolved into the screen's own words."""
	return [{
		"kind": "change",
		"key": f"change:{one['name']}",
		"on": one.get("on"),
		"by": one.get("by"),
		"by_id": one.get("by_id"),
		"entries": one.get("entries") or [],
	} for one in changes]


def _creation_entry(doc, resolved: dict) -> list[dict]:
	"""Where it started — the one entry no log holds.

	A Version records a change and there was nothing before the first one, so
	this is read off the record itself. It was synthesised in the browser and
	moved here with the rest: one column assembled in one place is the point.

	It says *converted* rather than *created* where the screen names a field
	this record came from and that field is filled, because those are two
	different events and a deal that says "created this" above six weeks of
	somebody else's email is a deal lying about its own history.
	"""
	if not doc.get("creation"):
		return []
	came_from = _came_from(doc, resolved)
	return [{
		"kind": "created",
		"key": "created",
		"on": doc.get("creation"),
		"by": doc.get("owner"),
		"by_id": doc.get("owner"),
		"converted": bool(came_from),
		# What it was called, not what it is keyed by: "converted zzBrightwater
		# Hotels into this" is a sentence, and `CRM-LEAD-2026-00010` is the
		# database's answer to a question nobody asked.
		"from_label": _named(*came_from) if came_from else "",
	}]


def _named(doctype: str, name: str) -> str:
	"""One record's title, cheaply."""
	meta = frappe.get_meta(doctype)
	title = getattr(meta, "title_field", "") or ""
	if not title or title == "name" or not meta.get_field(title):
		return name
	return str(frappe.get_cached_value(doctype, name, title) or name)


def _came_from(doc, resolved: dict):
	"""The record this one was made from, as `(doctype, name)`.

	`view_settings.timeline.inherits` names the field — `views._timeline` — and
	it is usually a Dynamic Link, because the interesting case is a deal that
	may have come from a Lead, a Customer or a Prospect. A plain Link works
	too and its target is the field's own `options`.
	"""
	field = ((resolved.get("view_settings") or {}).get("timeline") or {}).get("inherits")
	if not field:
		return None
	name = doc.get(field)
	if not name:
		return None

	column = next((one for one in resolved.get("all_columns") or []
	               if one.get("fieldname") == field), None)
	if not column:
		return None
	if column.get("fieldtype") == "Dynamic Link":
		doctype = doc.get(column.get("options") or "")
	else:
		doctype = column.get("options") or ""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return None
	return (doctype, name)


def _inherited_entries(doc, resolved: dict) -> list[dict]:
	"""The history of the record this one came from.

	`docs/ONECRM.md` stage 4. A deal converted from a lead did not exist before
	the conversion, so its column began the day somebody pressed a button and
	the six weeks of email that got it there sat on a record nobody opens
	again. The lead's entries are prepended, marked, and that is the whole of
	it.

	**One hop.** A lead that itself came from something does not drag a third
	history in: two is a history and three is an ancestry, and the cost is a
	query per hop on every record opening.

	**And the reader's permission on the far end decides.** A person may hold
	the deal and not the lead — a rep given one customer's pipeline — and the
	answer there is a shorter column, not a refusal and not a disclosure.
	"""
	came_from = _came_from(doc, resolved)
	if not came_from:
		return []
	doctype, name = came_from

	if not frappe.has_permission(doctype, "read", doc=name):
		return []

	try:
		other = frappe.get_doc(doctype, name)
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return []

	# The far record's own screen, so its mail and its files are read under the
	# same rules they are read under there. Nothing of *ours* — a screen this
	# reader cannot reach is one whose entries they should not be shown.
	far = _screen_for(doctype)
	if far is None:
		return []

	comments = frappe.get_all(
		"Comment",
		filters={"reference_doctype": doctype, "reference_name": name,
		         "comment_type": "Comment"},
		fields=["name", "content", "comment_email", "comment_by", "creation"],
		order_by="creation desc",
		limit_page_length=TIMELINE_PAGE,
	)
	entries = [
		*_said_entries(comments),
		*_creation_entry(other, far),
		*_gather(doctype, name, far),
	]
	# Marked, because "who said this and when" is not enough when the answer is
	# on a different record: the column has to say that this half is the lead's.
	label = _title_of(other, doctype)
	for one in entries:
		one["key"] = f"was:{one['key']}"
		one["about"] = label
		one["about_doctype"] = doctype
		one["about_name"] = name
	return entries


def _screen_for(doctype: str) -> dict | None:
	"""A resolved screen over this doctype that the reader may open.

	The entries of the record on the other end are read through its *own*
	screen's rules rather than through the one the reader happens to be
	standing on: a Version rendered against the wrong screen's columns is a
	change log in somebody else's words, and a field the far screen hides is
	one this reader was not meant to see change.

	The first that resolves wins, and a doctype with no screen this reader may
	open answers nothing — which is the same sentence the permission check
	above makes, one level out.
	"""
	from oneapp.onespace import sync
	from .resolve import visible

	for space in visible(sync.state().get("spaces") or []):
		for screen in space.get("screens") or []:
			if (screen.get("document_type") or "").strip() != doctype:
				continue
			if screen.get("component"):
				continue
			try:
				return _resolve(space["space_code"], screen["screen"])
			except Exception:
				frappe.clear_last_message()
	return None


def _title_of(doc, doctype: str) -> str:
	"""What to call the record on the other end, in one line."""
	meta = frappe.get_meta(doctype)
	title = getattr(meta, "title_field", "") or ""
	said = (doc.get(title) if title and title != "name" else "") or doc.get("name")
	return str(said or "")


def _mail_entries(doctype: str, name: str, resolved: dict) -> list[dict]:
	"""The mail about it that this reader may see.

	Through `spaceview/mail.py`'s own reader rather than a query of its own,
	which is the only way this can be true: a link is not a grant, and the
	scoping that makes that so lives there.
	"""
	from oneapp.onespace.spaceview import mail

	names = mail._linked(doctype, name)
	if not names:
		return []

	rows = frappe.get_list(
		"Communication",
		filters={"name": ["in", names]},
		fields=["name", "subject", "sender", "sender_full_name",
		        "communication_date", "sent_or_received", "has_attachment"],
		order_by="communication_date desc",
		limit_page_length=TIMELINE_PAGE,
	)
	return [{
		"kind": "mail",
		"key": f"mail:{one['name']}",
		"on": one.get("communication_date"),
		"by": one.get("sender_full_name") or one.get("sender"),
		"by_id": one.get("sender"),
		"subject": one.get("subject") or "",
		"way": one.get("sent_or_received") or "",
		"attached": bool(one.get("has_attachment")),
		"message": one["name"],
	} for one in rows]


def _file_entries(doctype: str, name: str, resolved: dict) -> list[dict]:
	"""What was attached to it, and by whom.

	`get_list`, so a file this reader may not see is a file they are not told
	about — the same rule the gallery follows, because it is the same rows.
	"""
	rows = frappe.get_list(
		"File",
		filters={"attached_to_doctype": doctype, "attached_to_name": name},
		fields=["name", "file_name", "file_url", "owner", "creation",
		        "is_private"],
		order_by="creation desc",
		limit_page_length=TIMELINE_PAGE,
	)
	if not rows:
		return []
	names = _names([{"owner": one.get("owner")} for one in rows])
	return [{
		"kind": "file",
		"key": f"file:{one['name']}",
		"on": one.get("creation"),
		"by": names.get(one.get("owner")) or one.get("owner"),
		"by_id": one.get("owner"),
		"title": one.get("file_name") or "",
		"url": one.get("file_url") or "",
		"private": bool(one.get("is_private")),
	} for one in rows]


#: The sources, in the order they are asked.
#:
#: A list rather than four calls, because the point of stage 3 is that the
#: fifth is one line. Registered here rather than by a hook: these are the
#: framework's own nouns on every doctype, and a hook would be an extension
#: point for something no app has asked for.
SOURCES = (_mail_entries, _file_entries)


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
                fieldname: str | None = None,
                start: int = 0, limit: int = 0, folder: str = "") -> dict:
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

	# The record's *room* rather than everything attached to it — `DRIVE.md`
	# §13. A record may have folders of its own now, and they are attachments
	# too, so a flat list would show a folder beside the files that are inside
	# it. `folder is not set` is the top; anything else is one of its folders,
	# whose id begins with the room's own address.
	#
	# A gallery is the one caller that still wants everything: an Attachment
	# Gallery draws the record's images, and a photograph filed in a subfolder
	# is still one of them.
	if not fieldname:
		filters["folder"] = folder or ["is", "not set"]

	# Not what is in the bin, and through the Drive's own `_visible()` rather
	# than a second spelling of it — a file predating the status field has no
	# status at all, so `!= Trashed` would hide every one of them.
	#
	# This list did not exclude the bin, so binning a file from the record's
	# Files tab left the row exactly where it was and pressing the verb again
	# did nothing visible a second time. The bin is thirty days of reversible,
	# not a second place the same file is.
	from oneapp.onestorage.query import _visible

	filters.update(_visible())

	# The Drive's fields and the Drive's shaping, because a record's Files tab
	# is the Drive filtered to one record — see `docs/DRIVE.md`. Two lists that
	# looked alike would be two places to add a column to, and the tab would be
	# the one that never got it.
	from oneapp.onestorage import reading

	# One page at a time, the same way every other file list reads — see
	# `shared/lib/list/files.js`. A record with three hundred attachments used
	# to send all three hundred to draw the first screenful of them.
	#
	# `limit` of zero still means all of them: the Attachment Gallery and the
	# record panel's count both want the whole set, and neither draws a list
	# somebody scrolls.
	limit = max(0, int(limit or 0))
	start = max(0, int(start or 0))
	found = frappe.get_all(
		"File",
		filters=filters,
		fields=sorted(set(FILE_FIELDS) | set(reading.FIELDS)),
		order_by="creation desc",
		limit_start=start,
		limit_page_length=(limit + 1) if limit else 0,
	)
	more = bool(limit) and len(found) > limit
	if more:
		found = found[:limit]
	reading._shape(found)
	# How many there are, not how many were sent. The record panel's
	# Attachments row says a number and a paged list can only see its own
	# page, so the count is asked for rather than inferred — one `count` over
	# filters the query above just used, and only when a page was asked for.
	total = frappe.db.count("File", filters) if limit else len(found)
	return {
		"files": found, "more": more, "total": total, "doctype": doctype,
		# Where in the room this is, so the tab can draw a way back up. Built
		# rather than walked, the same way the Drive builds it: a room folder's
		# id *is* its path — `onestorage/file.py` names the top of one after
		# the record.
		"folder": folder,
		"path": _room_path(doctype, name, folder),
	}


def _room_path(doctype: str, name: str, folder: str) -> list[dict]:
	"""`Drawings / Revisions`, from the folder's own id.

	The two levels the Drive draws above these — the doctype and the record —
	are not here on purpose: this tab is already inside one record, and a
	breadcrumb that began by naming the record you are looking at would be
	telling you where you are from a standing start.
	"""
	room = f"{doctype}/{name}/"
	if not folder or not folder.startswith(room):
		return []
	parts = folder[len(room):].split("/")
	return [
		{"name": room + "/".join(parts[:depth + 1]), "label": one}
		for depth, one in enumerate(parts)
	]


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
	framework only ever built a digest email. See `onespace.notifications`.
	"""
	from oneapp.onespace import notifications as follow

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
