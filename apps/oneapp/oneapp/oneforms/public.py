"""The page a stranger sees.

`docs/ONEFORMS.md` stage 3. Frappe renders a web form with Jinja into
`templates/web.html` — its own navbar, its own footer, Bootstrap — which is a
look this product deliberately does not have; `hide_navbar` and `hide_footer`
exist on `Web Form` because everybody who ships one thinks so.

All four of Frappe's own endpoints are `allow_guest=True`, so there is nothing
to work around: the SPA draws the form and posts to `accept`. The route pattern
was already here — `/link/:secret` is OneCloud's public share and `meta.public`
is the flag the router guard reads.

**Two endpoints, and neither of them decides anything.**

`page` resolves a route to a form and asks Frappe the access question through
`WebForm.get_web_form_request`, which is the same call the framework's own page
makes. `send` hands the whole submission to `frappe...accept`, which does
`raise_if_unpublished`, binds the request key to the docname, refuses a guest
on a form that needs a sign-in, and downgrades a signed-in session to Guest on
an anonymous form. Reimplementing any of that would be a second answer to who
may write what.

**What this adds is a shape, not a rule**: the fields as a browser needs them,
with a Link field's options resolved through `get_link_options` — which is not
whitelisted, deliberately, because it has its own three checks and Frappe means
them to run on the server.

Rate limited per route, because the whole point is that anybody can reach it.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

FORM = "Web Form"

#: Options offered for a Link field on a public form. A cap rather than the
#: whole table: a picker is a thing somebody chooses from, and a form that
#: shipped eleven thousand customers to a stranger's browser would be a
#: disclosure as well as a page that does not load.
OPTIONS = 100

#: What a field carries to the browser. `Web Form Field` has seventeen columns
#: and the rest are the desk's.
SHAPE = ("fieldname", "fieldtype", "label", "reqd", "read_only", "hidden",
         "description", "default", "placeholder", "options", "depends_on",
         "max_length", "max_value")

#: The presentation of the form itself. Everything here is something the page
#: draws; nothing here decides who may see it.
SAID = ("title", "introduction_text", "button_label", "success_message",
        "success_title", "success_url", "banner_image", "allow_edit",
        "allow_multiple", "show_list", "list_title", "doc_type")


def _form(route: str):
	"""The published form at that route, or nothing anybody can learn from.

	One sentence for "no such form" and for "not published", which is
	deliberate and is the opposite of the rule inside the product: out here the
	difference between the two is a fact about this workspace that a stranger
	has no business being told.
	"""
	name = frappe.db.get_value(FORM, {"route": (route or "").strip()}, "name")
	if not name:
		frappe.throw(_("This form is not available."), frappe.DoesNotExistError)
	doc = frappe.get_doc(FORM, name)
	if not doc.published:
		frappe.throw(_("This form is not available."), frappe.DoesNotExistError)
	return doc


def _admitted(doc, key: str):
	"""Frappe's own access question, asked Frappe's own way.

	`get_web_form_request` returns the request for a keyed form, refuses a key
	that is wrong, expired or spent, and answers `None` for a form that needs
	no key. The sign-in rule is separate and is checked here for the same
	reason `accept` checks it again on the way in: this is a read and that is a
	write, and neither is allowed to assume the other ran.
	"""
	if doc.login_required and frappe.session.user == "Guest":
		frappe.throw(_("You must be signed in to use this form."),
		             frappe.PermissionError)
	return doc.get_web_form_request(key or None, allow_used=True)


def _options(doc, field) -> list[str]:
	"""What a Link field on this form may be set to.

	Through `get_link_options`, which is not whitelisted on purpose: it refuses
	a doctype Guest cannot read, refuses one no field of this form links to,
	and refuses a keyed form without its key. Three checks that only run if the
	call stays on the server, which is where this keeps it.
	"""
	from frappe.website.doctype.web_form.web_form import get_link_options

	try:
		found = get_link_options(doc.name, field.options,
		                         web_form_request_key=frappe.form_dict.get("key"))
	except Exception:
		frappe.clear_messages()
		return []
	rows = found.split("\n") if isinstance(found, str) else list(found or [])
	return [str(one) for one in rows if one][:OPTIONS]


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(key="route", limit=60, seconds=60)
def page(route: str, key: str = "") -> dict:
	"""One form, as a browser needs to draw it."""
	doc = _form(route)
	_admitted(doc, key)

	fields = []
	for row in doc.web_form_fields or []:
		field = {one: row.get(one) for one in SHAPE}
		if row.fieldtype == "Link" and row.options:
			field["choices"] = _options(doc, row)
		fields.append(field)

	from frappe.utils.html_utils import sanitize_html

	said = {one: doc.get(one) for one in SAID}
	# The one field on a form that is markup, and the one place this module
	# hands a browser something to render rather than to read. Sanitised even
	# though only a workspace admin can set it: the page is served to
	# strangers, so a script tag here would run in *their* browser, and
	# `client_script` and `custom_css` are outside `SETTINGS` for the same
	# reason. An admin's own rich text is not a licence to ship them code.
	said["introduction_text"] = sanitize_html(said.get("introduction_text") or "")

	return {
		"route": doc.route,
		"said": said,
		"fields": fields,
		# What the page has to know about itself to behave, and no more. Not
		# `login_required`: a form that needs a sign-in has already refused by
		# the time this returns.
		"keyed": int(doc.key_required or 0),
		"anonymous": int(doc.anonymous or 0),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="route", limit=20, seconds=60)
def send(route: str, values: str | dict, key: str = "") -> dict:
	"""A submission, handed straight to Frappe.

	`accept` is the whole of the write: it re-checks that the form is
	published, binds the key to the document, refuses a guest where a sign-in
	is required, and drops a signed-in session to Guest on an anonymous form.
	What this adds is the route lookup and the shape of the answer.
	"""
	from frappe.website.doctype.web_form.web_form import accept

	doc = _form(route)
	_admitted(doc, key)

	asked = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})
	asked["doctype"] = doc.doc_type

	made = accept(web_form=doc.name, data=asked, web_form_request_key=key or None)
	return {
		"name": getattr(made, "name", "") if made else "",
		"said": doc.success_message or _("Thank you."),
		"title": doc.success_title or "",
		"url": doc.success_url or "",
	}
