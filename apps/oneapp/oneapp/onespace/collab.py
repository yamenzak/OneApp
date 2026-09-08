"""Tags and sharing — the two things people do to a record about other people.

Both are Frappe's, and both are worth using rather than inventing, for the same
reason the notification feed was: the storage, the permission rule and the
bookkeeping already exist and are load-bearing elsewhere in the framework.

**Tags** are two things at once, and the pair is the whole design:

  * `_user_tags`, a comma-joined `Data` column added to the doctype's own table
    on demand. It is on the row, so a tag is filterable and sortable with the
    same machinery as any other column and costs no join.
  * a `Tag Link` row per (tag, document), which is what makes "everything
    tagged urgent" answerable across doctypes, and a `Tag` master so a tag can
    be picked rather than retyped.

Frappe keeps them in step in `DocTags.update`; so do we, by going through it.

**Sharing** is `DocShare`: one row per (document, person or everyone) carrying
read / write / submit / share. The part that matters is what reads it —
`frappe.model.db_query` folds shares into the permission condition of every
`get_list`, so a shared record becomes visible to the person it was shared with
with nothing else written anywhere. That is the whole feature, and it is why
writing our own share table would have meant reimplementing list permissions.

What is ours, in both cases, is the gate. The framework's own doctypes grant
`DocShare` and `Tag Link` to System Manager and to `All` respectively, and our
members are Website Users by design — so the writes here are
`ignore_permissions` behind a check on the *document*, which is the permission
that actually decides. The same shape `spaceview.toggle_like`, `assign` and
`notifications.set_following` use.
"""

import frappe
from frappe import _

# How many tags one picker offers, and how many one record may carry. Frappe
# bounds neither; `_user_tags` is a `Data` column, so a record with a hundred
# tags is a row that silently truncates at 140 characters and a list cell that
# is a wall.
TAG_PAGE = 20
TAGS_PER_RECORD = 12

# What a tag may be. Frappe names the `Tag` document after the tag itself, so a
# tag with a comma in it would split `_user_tags` into two, and one with a
# newline would arrive back as something nobody typed.
TAG_MAX = 40


# --------------------------------------------------------------------------- #
# Tags
# --------------------------------------------------------------------------- #

def has_tags_column(doctype: str) -> bool:
	"""Whether this doctype's table has `_user_tags` yet.

	It is added on demand — Frappe creates it the first time something on that
	doctype is tagged — so a screen over a doctype nobody has ever tagged has
	no column to offer and no column to filter on. Asked rather than assumed,
	because filtering on a column that is not there is a SQL error rather than
	an empty list.
	"""
	try:
		return bool(frappe.db.has_column(doctype, "_user_tags"))
	except Exception:
		return False


def ensure_tags_column(doctype: str) -> None:
	"""Make sure it exists. Frappe's own, and a no-op when it already does."""
	from frappe.desk.doctype.tag.tag import check_user_tags

	check_user_tags(doctype)


def parse(value) -> list[str]:
	"""`_user_tags` as a list.

	Frappe joins with commas and leaves a leading one behind on the first tag,
	so this is the reader for a column written by three different versions of
	the same function.
	"""
	return [one.strip() for one in str(value or "").split(",") if one.strip()]


def tags_of(doctype: str, name: str) -> list[str]:
	if not has_tags_column(doctype):
		return []
	return parse(frappe.db.get_value(doctype, name, "_user_tags", ignore=True))


def clean(tag: str) -> str:
	"""One tag, as it will be stored.

	A comma would split it in two on the way back out of `_user_tags`, and a
	newline would make a `Tag` document nobody can name. Trimmed and bounded
	rather than rejected: somebody pasting a phrase with a comma in it meant a
	tag, not an error message.
	"""
	tag = " ".join(str(tag or "").replace(",", " ").split())
	return tag[:TAG_MAX]


def set_tag(doctype: str, name: str, tag: str, on=True) -> list[str]:
	"""Add or remove one tag, through Frappe's own `DocTags`.

	Through it and not around it: `DocTags.update` writes `_user_tags` on the
	row *and* reconciles the `Tag Link` rows, and a tag written to one and not
	the other is a tag that filters here and cannot be found anywhere else.
	"""
	tag = clean(tag)
	if not tag:
		frappe.throw(_("A tag needs a name."))

	held = tags_of(doctype, name)
	if on and tag not in held and len(held) >= TAGS_PER_RECORD:
		frappe.throw(
			_("A record can carry {0} tags. Take one off first.").format(TAGS_PER_RECORD)
		)

	from frappe.desk.doctype.tag.tag import DocTags

	# `DocTags.update` calls `doc.check_permission("write")` on its way to the
	# Tag Links, so the permission is Frappe's own and is checked against the
	# document rather than against the tag.
	if on:
		DocTags(doctype).add(name, tag)
	else:
		DocTags(doctype).remove(name, tag)

	return tags_of(doctype, name)


def tag_options(query: str = "", exclude=()) -> list[str]:
	"""Tags to pick from: the workspace's own, matching what has been typed.

	The `Tag` master rather than the tags on this doctype. A tag is a word the
	workspace uses, not a property of one kind of record — "urgent" means the
	same thing on an invoice and on a task, and offering it only where it has
	already been used is how a vocabulary turns into three spellings of it.
	"""
	skip = {one.lower() for one in exclude if one}
	filters = [["name", "like", f"%{clean(query)}%"]] if query else []

	return [
		row
		for row in frappe.get_all(
			"Tag", filters=filters, pluck="name",
			order_by="name asc", limit_page_length=TAG_PAGE + len(skip),
		)
		if row.lower() not in skip
	][:TAG_PAGE]


# --------------------------------------------------------------------------- #
# Sharing
#
# Three levels rather than Frappe's four checkboxes. `read`, `write` and
# `share` are questions a person can answer about a colleague; `submit` is a
# question about a document's state that only means anything on a submittable
# doctype, and putting it in the same list makes the other three harder to
# read. It stays available to `frappe.share` and is not offered here.
# --------------------------------------------------------------------------- #

LEVELS = {
	# in order of how much they give away, which is the order they are offered
	"read": {"read": 1, "write": 0, "share": 0},
	"write": {"read": 1, "write": 1, "share": 0},
	"share": {"read": 1, "write": 1, "share": 1},
}

# How many people one record may be shared with before the answer is a role.
# Not a technical bound: a list of forty faces on a record is a permission model
# nobody can audit, and the workspace has roles for exactly that.
SHARES = 25


def level_of(row: dict) -> str:
	"""Which of the three a DocShare row is, reading downwards."""
	if row.get("share"):
		return "share"
	if row.get("write"):
		return "write"
	return "read"


def shares_of(doctype: str, name: str) -> dict:
	"""Who this record is shared with, and how far.

	`everyone` is its own answer rather than a person in the list: it is a
	different kind of statement — "anybody who can sign in here" — and drawing
	it as a row among colleagues is how somebody grants it by accident.
	"""
	rows = frappe.get_all(
		"DocShare",
		filters={"share_doctype": doctype, "share_name": str(name)},
		fields=["name", "user", "everyone", "read", "write", "share"],
		limit_page_length=SHARES + 1,
	)

	people, everyone = [], None
	ids = [row["user"] for row in rows if not row["everyone"] and row["user"]]
	who = _users(ids)

	for row in rows:
		if row["everyone"]:
			everyone = {"level": level_of(row)}
			continue
		found = who.get(row["user"])
		if not found:
			# A share outlives the account it was granted to; Frappe does not
			# sweep DocShare when a user goes. Shown by id rather than dropped,
			# because a permission nobody can see is a permission nobody removes.
			found = {"value": row["user"], "label": row["user"], "image": None}
		people.append({**found, "level": level_of(row)})

	return {"people": people, "everyone": everyone}


def _users(ids: list) -> dict:
	"""Those ids as people, the same three things every identity here is drawn
	from. One query, and the same shape `spaceview._users` returns."""
	wanted = [one for one in dict.fromkeys(ids) if one]
	if not wanted:
		return {}
	return {
		row["name"]: {
			"value": row["name"],
			"label": row["full_name"] or row["name"],
			"image": row["user_image"],
		}
		for row in frappe.get_all(
			"User",
			filters={"name": ["in", wanted]},
			fields=["name", "full_name", "user_image"],
		)
	}


def share(doctype: str, name: str, user=None, everyone=0, level="read") -> dict:
	"""Share it, or change how far an existing share goes.

	`frappe.share.add_docshare` rather than a `DocShare` insert: it is what
	checks that the person doing the sharing holds each permission they are
	handing over — you cannot give write to somebody else on a record you may
	only read — and what makes the recipient follow the document when their own
	settings say to.
	"""
	from frappe.share import add_docshare

	if level not in LEVELS:
		frappe.throw(_("{0} is not a level of access.").format(level))

	everyone = int(frappe.utils.sbool(everyone) or 0)
	if not everyone and not user:
		frappe.throw(_("Name somebody to share this with."))

	held = shares_of(doctype, name)
	fresh = everyone or user not in {one["value"] for one in held["people"]}
	if fresh and len(held["people"]) >= SHARES and not everyone:
		frappe.throw(
			_("A record can be shared with {0} people. Use a role beyond that.").format(SHARES)
		)

	add_docshare(
		doctype, str(name),
		user=None if everyone else user,
		everyone=everyone,
		notify=0 if everyone else 1,
		**LEVELS[level],
	)
	return shares_of(doctype, name)


def unshare(doctype: str, name: str, user=None, everyone=0) -> dict:
	"""Take it back.

	`check_share_permission` first, because `frappe.share.remove` does not: it
	is called from places inside the framework that have already decided, and
	an endpoint is not one of them.
	"""
	from frappe.share import check_share_permission, get_share_name

	check_share_permission(doctype, str(name))

	found = get_share_name(doctype, str(name), user, int(frappe.utils.sbool(everyone) or 0))
	if found:
		frappe.delete_doc("DocShare", found, ignore_permissions=True)

	return shares_of(doctype, name)
