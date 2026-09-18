"""A form is a door into a doctype.

`docs/ONEFORMS.md`. Nothing in this product was public: dropping Frappe's portal
took the *forms* with it, so every sentence ending "and then somebody outside
sends us this" ended at a person re-keying it.

**Over Frappe's own `Web Form`**, which in v17 is most of the product already —
`anonymous` for a stranger, `key_required` with a `Web Form Request` per
recipient, `show_list` for somebody's own records, `allow_edit` for changing
one, `allowed_embedding_domains` for an iframe. And a Web Form writes into an
**ordinary doctype**, which is the whole reason it is the right foundation: a
form over Job Applicant makes a Job Applicant that OnePeople's hiring screens
already show, rather than a submission in a store nothing else can see.

**A service and not a space** — `catalogue.py` said so before this arc started.
A form is not a department you enter; it is something every department wants,
so the shape is OneTask's: a module, a dock tile, a window beside your work.

Two rules, and the first is the one that made this the first stage:

  * **A form may only be made over a doctype a space this person holds already
    shows them.** A `Web Form` can be pointed at anything on the site, so
    without this it would be a way to read and write past every grant in the
    product. `finding.placed` is the map — the same one the finder searches and
    the approvals inbox places rows with.
  * **Making one is the workspace admin's**, like an alert or a routing rule.
    `Web Form` ships with permissions for `Website Manager` and nobody in a
    workspace holds that, so this checks the reader and then writes with
    `ignore_permissions` — which is `alerts.py`'s pattern, for the same reason.

What is deliberately not here: a second form schema. `forms_pro` has one and it
is a different product — its `Form` keeps submissions in its own store, where
the point of this one is that the *doctype* is the subject.
"""

import re

import frappe
from frappe import _
from frappe.model import no_value_fields

from oneapp.onespace import finding

FORM = "Web Form"
FIELD = "Web Form Field"
REQUEST = "Web Form Request"

#: The mark `install.py` puts on a form this workspace made, as against the two
#: Frappe ships on every site and whatever an app installed. Same field and the
#: same argument as the one on `Notification` and `Assignment Rule`: a
#: workspace's own list is not where the platform's belong.
OURS = "custom_onespace"

#: Forms in one answer. A workspace with more than this has a filing problem
#: rather than a listing problem, and the window is a glance.
MOST = 100

#: What a form row carries. Small, because this is a list of doors and the
#: interesting number is beside each one rather than in it.
FIELDS = ["name", "title", "doc_type", "route", "published", "login_required",
          "anonymous", "key_required", "show_list", "allow_edit",
          "allow_multiple", "modified"]


def _admin() -> None:
	"""Making a form is the workspace admin's, and this is where that is said.

	Not a formality. A form is a route anybody on the internet can reach that
	writes into a doctype, so "who may make one" is the same question as "who
	may open the workspace to strangers" — and that is the owner's, beside the
	custom domain and the member list.
	"""
	from oneapp.onespace.workspace import OWNER_ROLE, SUPPORT_ROLE

	if not set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE}:
		frappe.throw(_("Only a workspace admin can make a form."),
		             frappe.PermissionError)


def offerable() -> list[dict]:
	"""The doctypes this person may make a form over.

	Every screen they could open, which is what `finding.placed` answers, and
	nothing else on the site. So a form cannot become a way past a grant: if
	no space of theirs shows Salary Slip, they cannot publish a page that
	writes one.

	The space is carried through because it is what makes the picker readable —
	"Job Applicant, in OnePeople" rather than a list of doctype names — and
	because a workspace with two spaces over one doctype should say which.
	"""
	return [
		{"doctype": doctype, "label": target["label"], "space": target["space"],
		 "space_label": target["space_label"], "icon": target["icon"]}
		for doctype, target in sorted(finding.placed().items())
	]


def _over(doctype: str) -> dict:
	"""That doctype as something to make a form over, or a refusal."""
	for one in offerable():
		if one["doctype"] == doctype:
			return one
	frappe.throw(
		_("{0} is not something you can make a form over.").format(_(doctype)),
		frappe.PermissionError,
	)


def _ours(name: str):
	"""One of this workspace's forms, loaded, or a refusal.

	A form an app shipped is left alone: it is part of what that app *is*, like
	its doctypes and its print formats, and a window that let somebody edit
	Frappe's own two would be a window that breaks a site.
	"""
	doc = frappe.get_doc(FORM, name)
	if not doc.get(OURS):
		frappe.throw(_("That form was not made here."), frappe.PermissionError)
	return doc


def _route(title: str) -> str:
	"""A URL for a form, from its title.

	Frappe wants one and will not make it up, and a route is the address people
	paste into an email — so it is worth being ordinary. Scrubbed to words and
	hyphens, and suffixed until it is free rather than refused: two forms
	called "Contact us" is an ordinary thing for a workspace to want.
	"""
	base = frappe.scrub(title or "form").replace("_", "-").strip("-") or "form"
	route, at = base, 1
	while frappe.db.exists(FORM, {"route": route}):
		at += 1
		route = f"{base}-{at}"
	return route


def _counted(rows: list[dict]) -> list[dict]:
	"""Each form, with how many invitations are out and how many were used.

	**Not how many records it made**, and that is stage 6's finding rather than
	an omission: a Web Form writes an ordinary document and marks it in no way,
	so "responses to this form" is not a question the database can answer. It
	could be made answerable by adding a column to every doctype a form is over,
	which is a schema change to somebody else's table for a number — and the
	number people actually want is on the list screen in the space, where every
	other count in this product is.

	So a form says what it *does* know: who it was sent to and who answered.
	And `place` is the way to the rest, which is the doctype's own screen.
	"""
	where = finding.placed()
	out = []
	for row in rows:
		sent = frappe.get_all(
			REQUEST, filters={"web_form": row["name"]},
			fields=["name", "first_used_on"], ignore_permissions=True,
		)
		target = where.get(row["doc_type"]) or {}
		out.append({
			**row,
			"invited": len(sent),
			"answered": sum(1 for one in sent if one["first_used_on"]),
			"place": {"space": target.get("space") or "",
			          "screen": target.get("screen") or "",
			          "label": target.get("space_label") or ""},
		})
	return out


@frappe.whitelist(methods=["GET"])
def forms() -> dict:
	"""This workspace's forms, and what it may make one over."""
	_admin()
	rows = frappe.get_all(
		FORM, filters={OURS: 1}, fields=FIELDS,
		order_by="modified desc", limit_page_length=MOST,
		ignore_permissions=True,
	)
	return {"rows": _counted([dict(row) for row in rows]), "offerable": offerable()}


@frappe.whitelist(methods=["POST"])
def make(doctype: str, title: str = "") -> dict:
	"""A new form over one of the offerable doctypes.

	Unpublished, with no fields on it. Publishing is a second press and the
	fields are stage 2's: a form that went live the moment it was named would
	be a URL somebody made by accident.
	"""
	_admin()
	over = _over(doctype)
	title = (title or "").strip() or over["label"]

	doc = frappe.new_doc(FORM)
	doc.update({
		"title": title,
		"doc_type": doctype,
		"route": _route(title),
		"module": "OneForms",
		"published": 0,
		"login_required": 1,
		"success_message": _("Thank you."),
		OURS: 1,
	})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "route": doc.route, "title": doc.title}


@frappe.whitelist(methods=["POST"])
def rename(name: str, title: str) -> dict:
	"""What it is called. The route is left alone — it is a link people hold."""
	_admin()
	doc = _ours(name)
	title = (title or "").strip()
	if not title:
		frappe.throw(_("A form needs a name."))
	doc.title = title
	doc.save(ignore_permissions=True)
	return {"name": doc.name, "title": doc.title}


@frappe.whitelist(methods=["POST"])
def publish(name: str, live: int | str = 1) -> dict:
	"""Live or not, which is the only switch that changes who can reach it."""
	_admin()
	doc = _ours(name)
	doc.published = 1 if str(live) in ("1", "true", "True") else 0
	doc.save(ignore_permissions=True)
	return {"name": doc.name, "published": doc.published}


@frappe.whitelist(methods=["POST"])
def forget(name: str) -> dict:
	"""Delete the form, and the invitations to it.

	The invitations go first because they link to it and Frappe refuses to
	delete a document something points at — which is right, and here means the
	keys have to be taken back before the door is. That is also the behaviour
	somebody wants: the links stop working, which is what deleting the form
	was for.

	What the form *collected* stays. Those are ordinary records in an ordinary
	doctype, and a form is a door rather than a folder.
	"""
	_admin()
	doc = _ours(name)
	for row in frappe.get_all(REQUEST, filters={"web_form": doc.name}, pluck="name",
	                          ignore_permissions=True):
		frappe.delete_doc(REQUEST, row, force=True, ignore_permissions=True)
	frappe.delete_doc(FORM, doc.name, ignore_permissions=True)
	return {"name": name}


# --------------------------------------------------------------------------- #
# The builder — `docs/ONEFORMS.md` stage 2
#
# A Web Form field is **chosen from the doctype**, not invented: `fieldname` on
# `Web Form Field` is a Select of the target doctype's own fields, and that is
# the whole difference between this and a survey tool. So the builder is
# "which of these fields, in what order, said how" rather than a field factory,
# and the interaction is drag-to-order with the two breaks as things you drag
# in.
#
# `bwhtech/forms_pro` is where the interaction comes from and none of its code
# does: its builder is a grid over its own `Form Field`, with a row, a column
# and a cell index per field, and `Web Form Field` has none of those. Porting
# it would have been porting its schema.
# --------------------------------------------------------------------------- #

#: The layout items — not fields of the doctype, so they are offered separately
#: and are the only entries whose `fieldname` is allowed to be empty.
#:
#: `Page Break` is the one that makes a form more than a column of controls: the
#: public page draws each run between two of them as a step, with dots and a
#: Next, which is what an application form of thirty questions has to be before
#: anybody finishes it. It was left out of stage 3 and the page was poorer for
#: it — see `docs/ONEFORMS.md` §13.
BREAKS = ("Section Break", "Column Break", "Page Break")

#: What never goes on a form, whatever the doctype has. Each for its own
#: reason: a Table is a grid inside a page a stranger is filling in, `Password`
#: is ciphertext, and the layout-ish ones are the form's own to place — a
#: doctype's own section break is where *its* designer wanted a heading, and
#: the form is a different page.
NEVER = {
	"Table", "Table MultiSelect", "Password", "Signature", "Geolocation",
	"Section Break", "Column Break", "Page Break", "Tab Break", "Fold",
	"HTML", "Heading",
	"Button", "Barcode", "Code", "JSON", "Icon", "Image",
}

#: What a field on a form carries, and the whole of what `layout` will write.
#: A short list on purpose: `Web Form Field` has seventeen columns and most of
#: them are a desk form's, and a property nobody can set here is a property
#: nobody has to be told about.
SHAPE = ("fieldname", "fieldtype", "label", "reqd", "read_only", "hidden",
         "description", "default", "placeholder", "options", "depends_on",
         "max_length", "max_value")

#: Columns on the list a key holder sees. Four is what fits on a phone, which
#: is where a supplier opens a link somebody mailed them.
LIST_COLUMNS = 4

#: The form's own settings a builder may change. Everything else on `Web Form`
#: — `doc_type`, `route`, `module`, the client script, the custom CSS — is
#: either fixed at making time or is not a customer's to set.
SETTINGS = ("title", "introduction_text", "success_message", "success_title",
            "success_url", "button_label", "login_required", "anonymous",
            "key_required", "allow_edit", "allow_multiple", "allow_delete",
            "allow_comments", "show_attachments", "show_list", "list_title",
            "apply_document_permissions", "allowed_embedding_domains",
            "hide_navbar", "hide_footer", "max_attachment_size")

#: What a Link column costs on a list a stranger sees, and the reason
#: `list_columns` is not optional here. With none set, Frappe falls back to the
#: doctype's list-view fields and resolves every Link in them through
#: `ensure_guest_key_link_doctype_allowed` — so a form over Job Applicant, whose
#: `job_title` links to Job Opening, answers "You don't have permission to
#: access the Job Opening DocType" to the person holding a perfectly good key.
#: Measured, on the dev fixture, the first time `show_list` was turned on.
LINKISH = ("Link", "Dynamic Link", "Table MultiSelect")

#: The settings that are a checkbox rather than a sentence, so the write can
#: coerce rather than trust whatever the browser sent.
SWITCHES = ("login_required", "anonymous", "key_required", "allow_edit",
            "allow_multiple", "allow_delete", "allow_comments",
            "show_attachments", "show_list", "apply_document_permissions",
            "hide_navbar", "hide_footer")


def available(doctype: str) -> list[dict]:
	"""The fields of that doctype a form could carry.

	Read off the meta rather than listed, so a form over a doctype somebody
	customised offers the field they added. `NEVER` is the only narrowing and
	every entry in it has a reason beside it.
	"""
	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return []
	return [
		{"fieldname": field.fieldname, "label": field.label or field.fieldname,
		 "fieldtype": field.fieldtype, "reqd": int(field.reqd or 0),
		 "options": field.options or ""}
		for field in meta.fields
		if field.fieldname and field.fieldtype not in NEVER
	]


@frappe.whitelist(methods=["GET"])
def read(name: str) -> dict:
	"""One form: its settings, the fields on it, and what else it could carry."""
	_admin()
	doc = _ours(name)
	return {
		"name": doc.name,
		"doc_type": doc.doc_type,
		"route": doc.route,
		"published": int(doc.published or 0),
		"settings": {key: doc.get(key) for key in SETTINGS},
		# Beside the settings rather than in them, which is the same split
		# `style` keeps on the way back: it is read with the form and written
		# through a door of its own.
		"css": doc.custom_css or "",
		"fields": [
			{key: row.get(key) for key in SHAPE}
			for row in (doc.web_form_fields or [])
		],
		"available": available(doc.doc_type),
		"breaks": list(BREAKS),
	}


@frappe.whitelist(methods=["POST"])
def layout(name: str, fields: str | list) -> dict:
	"""Replace the fields on a form, in the order they arrive.

	Replaced rather than merged, which is what a drag-and-drop builder means:
	the browser is holding the whole list and reconciling two orderings would
	be inventing a conflict nobody has.

	Every row is checked against the doctype's own fields. That is the same
	rule `_over` keeps one level up — a form is a view of a doctype and not a
	way to name a column — and without it a posted payload could put
	`fieldname: "password"` on a form over User.
	"""
	_admin()
	doc = _ours(name)
	asked = frappe.parse_json(fields) if isinstance(fields, str) else (fields or [])
	known = {one["fieldname"]: one for one in available(doc.doc_type)}

	doc.web_form_fields = []
	for row in asked:
		if not isinstance(row, dict):
			continue
		fieldtype = (row.get("fieldtype") or "").strip()
		fieldname = (row.get("fieldname") or "").strip()

		if fieldtype in BREAKS:
			# A break is the form's own furniture and belongs to no doctype, so
			# it is the one row with no fieldname to check. Frappe wants one
			# anyway, and a stable made-up name keeps a saved form diffable —
			# but only for the breaks the framework counts as valueless.
			#
			# `Page Break` is not one of them, and `WebForm.validate_fields`
			# checks every *named* row against the doctype: a page break called
			# `page_break_5` is refused as a missing field. So it goes in
			# nameless, which is the shape that check was written to let
			# through. Read off `frappe.model` rather than copied, because a
			# copy of somebody else's tuple is a copy that goes stale.
			named = fieldname or frappe.scrub(f"{fieldtype} {len(doc.web_form_fields)}")
			doc.append("web_form_fields", {
				"fieldtype": fieldtype,
				"fieldname": named if fieldtype in no_value_fields else "",
				"label": (row.get("label") or "").strip(),
			})
			continue

		field = known.get(fieldname)
		if not field:
			frappe.throw(
				_("{0} is not a field on {1}.").format(fieldname or "?", _(doc.doc_type)),
				frappe.PermissionError,
			)
		written = {key: row.get(key) for key in SHAPE if key in row}
		written.update({
			"fieldname": fieldname,
			# The doctype's, not the browser's: a form that said a Date was a
			# Data would write a string into a date column.
			"fieldtype": field["fieldtype"],
			"label": (row.get("label") or field["label"]).strip(),
			# A field the doctype itself requires stays required, whatever the
			# form says. The other direction is allowed — a form may ask for
			# something the doctype does not insist on.
			"reqd": 1 if field["reqd"] else int(row.get("reqd") or 0),
		})
		doc.append("web_form_fields", written)

	doc.save(ignore_permissions=True)
	return {"name": doc.name, "fields": len(doc.web_form_fields)}


@frappe.whitelist(methods=["POST"])
def settings(name: str, values: str | dict) -> dict:
	"""The form's own switches — who may reach it and what it says.

	`SETTINGS` is the allowlist and it is short. Everything outside it is either
	fixed when the form is made (`doc_type`, `route`, `module`) or is not a
	customer's to set: `client_script` and `custom_css` are code, and code on a
	page strangers load is not a setting.
	"""
	_admin()
	doc = _ours(name)
	asked = frappe.parse_json(values) if isinstance(values, str) else (values or {})

	for key in SETTINGS:
		if key not in asked:
			continue
		value = asked[key]
		if key in SWITCHES:
			# Coerced rather than trusted: a checkbox arrives as a string from
			# a form post and as a boolean from the SPA, and `"false"` is
			# truthy in Python.
			value = 1 if str(value) in ("1", "True", "true") else 0
		doc.set(key, value)

	# Frappe's own rule, restated here because the browser can post anything:
	# a form open to anybody cannot also require a sign-in, and the pair
	# silently disagreeing is a page that refuses everyone.
	if doc.anonymous:
		doc.login_required = 0

	# The columns a key holder sees, where they asked for a list and chose
	# none. Set rather than left empty, because empty is not "the default" — it
	# is the fallback above, which throws. The form's own plain fields, which
	# are the ones this person already decided somebody outside may see.
	if doc.show_list and not doc.list_columns:
		for row in (doc.web_form_fields or [])[:LIST_COLUMNS]:
			if row.fieldtype in BREAKS or row.fieldtype in LINKISH:
				continue
			doc.append("list_columns", {"fieldname": row.fieldname,
			                            "fieldtype": row.fieldtype,
			                            "label": row.label})
	if not doc.show_list:
		doc.list_columns = []

	doc.save(ignore_permissions=True)
	return {"name": doc.name, "settings": {key: doc.get(key) for key in SETTINGS}}


# --------------------------------------------------------------------------- #
# The form's own look
#
# `custom_css` is Frappe's field and is deliberately *not* in `SETTINGS`: it is
# code on a page strangers load, so it goes through a door of its own with its
# own checks rather than riding in with the button label.
#
# `client_script` has no door at all, and the reason is not caution. It is
# written against `frappe.web_form.on(...)`, a runtime that exists on Frappe's
# own Jinja page and not on ours — so a script saved here would be dead code a
# customer had written and been charged for. Giving it a runtime means shipping
# a script evaluator to a stranger's browser, which is a different decision and
# a bigger one than "let them style the page".
# --------------------------------------------------------------------------- #

#: How much stylesheet one form may carry. A form is a page with a heading and
#: a dozen controls on it; past this somebody is building a website, and
#: `docs/ONEFORMS.md` says that is not what this is.
MAX_CSS = 20_000

#: What a stylesheet on a public page may not do. Both of these are the same
#: thing — a fetch to somewhere else, made by the visitor's browser, on a page
#: they opened because they were asked to fill something in. A rule naming an
#: external URL is a beacon whether or not anybody meant it as one.
#:
#: `url(data:…)` is allowed: an inlined background is a picture, not a call.
AWAY = re.compile(r"@import\b|url\(\s*['\"]?(?!data:)[a-z]+:", re.I)

#: And the one that is not about the network: `</style` ends the element the
#: browser is reading, so everything after it is markup rather than CSS.
BREAKS_OUT = re.compile(r"</\s*style", re.I)


def check_css(css: str) -> str:
	"""A stylesheet, or a refusal that says which rule it broke."""
	css = (css or "").strip()
	if len(css) > MAX_CSS:
		frappe.throw(_("That is longer than one form's styling may be."))
	if AWAY.search(css):
		frappe.throw(_("A form's styling cannot fetch anything from another "
		               "site — no @import, and no url() except a data: one."))
	if BREAKS_OUT.search(css):
		frappe.throw(_("That would close the stylesheet and start writing "
		               "markup."))
	return css


@frappe.whitelist(methods=["POST"])
def style(name: str, css: str = "") -> dict:
	"""The form's own stylesheet, checked and stored."""
	_admin()
	doc = _ours(name)
	doc.custom_css = check_css(css)
	doc.save(ignore_permissions=True)
	return {"name": doc.name, "css": doc.custom_css}
