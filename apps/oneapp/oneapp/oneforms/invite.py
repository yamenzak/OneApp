"""A link addressed to one person, and what they can see with it.

`docs/ONEFORMS.md` stages 4 and 5, which are one file because they are one
idea: a `Web Form Request` is a key, and everything a keyed form does — pre-fill
it, bind it to somebody's own record, let them come back and change it, let them
see the others they have sent — hangs off that row.

**Frappe wrote the hard half and did not ship the easy one.** `Web Form Request`
carries a `key` (auto-generated), an `expires_on`, a `first_used_on`, a
`web_form_values` of what to pre-fill and a `references` table of the documents
that key may touch; `validate` checks the pre-fill against the form's own fields
and the doc values against the doctype's; `validate_key` refuses one that is
spent or expired. What it has no API for is *making* one, which is this file.

**And the security is still Frappe's.** `get_web_form_request` is what turns a
key into a request, `get_web_form_list` filters to the key's own references
before it runs, and `accept` binds the docname. Nothing here re-decides any of
it — the public half of this module is two lookups and a delegation.

The mail is `frappe.sendmail`, queued. Not OneMail's composer: an invitation is
a transactional message from the workspace rather than a person's own mail, and
putting it in somebody's Sent folder would be filing a machine's letter as
theirs.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import get_url

from oneapp.oneforms.service import FORM, REQUEST, _admin, _ours

#: How long an invitation is good for, unless somebody says otherwise. Long
#: enough to survive a holiday and short enough that a link in an old mailbox
#: is not a way in for ever.
DAYS = 30

#: Invitations listed for one form. A form sent to more people than this wants
#: a different tool — a mail merge — and saying so is better than paging.
MOST = 200

#: What an invitation row says. `key` is deliberately in it: whoever may send
#: an invitation may re-send the same link, and hiding it would mean the only
#: way to help somebody who lost theirs is to issue a second.
FIELDS = ["name", "key", "expires_on", "first_used_on", "creation"]


def _keyed(doc) -> None:
	"""A form nobody needs a key for cannot be invited to.

	Refused rather than quietly making a key that does nothing: an invitation
	to an open form is a link anybody already had, and a list of them would be
	a list of nothing.
	"""
	if not doc.key_required:
		frappe.throw(
			_("Turn on “Only by invitation” before sending one."),
		)


def _link(doc, key: str) -> str:
	"""Where the invitation points.

	Our own route rather than Frappe's: `/f/<route>` is the page this product
	draws, and `?key=` is what `public.page` reads. The site's own URL, so a
	workspace on a custom domain sends a link to its own domain.
	"""
	return f"{get_url()}/one/f/{doc.route}?key={key}"


@frappe.whitelist(methods=["GET"])
def invitations(name: str) -> dict:
	"""Who has been invited to this form, and whether they have used it."""
	_admin()
	doc = _ours(name)
	rows = frappe.get_all(
		REQUEST, filters={"web_form": doc.name}, fields=FIELDS,
		order_by="creation desc", limit_page_length=MOST,
		ignore_permissions=True,
	)
	return {
		"rows": [{**row, "url": _link(doc, row["key"])} for row in rows],
		"keyed": int(doc.key_required or 0),
		"route": doc.route,
	}


@frappe.whitelist(methods=["POST"])
def invite(name: str, to: str = "", values: str | dict | None = None,
           about: str = "", days: int | str = DAYS) -> dict:
	"""One invitation: a key, what it pre-fills, and what it may touch.

	`values` is what the person finds already filled in — their name, their
	employee number, whatever this workspace already knows. Frappe validates it
	against the form's own fields on save, so a payload naming a field the form
	does not carry is refused there rather than here.

	`about` is the document this key is bound to, and it is what makes "come
	back and change your answer" safe: `get_web_form_request` refuses a docname
	the key is not bound to, so a key holder cannot walk the doctype by id.

	Mailed where an address was given, and made either way — somebody sending
	the link by hand is an ordinary thing, and a maker that insisted on an
	address would be a maker with a second path around it. "Either way" is
	literal and was not, at first: `sendmail` throws on a workspace with no
	outgoing account, Frappe rolls the request back with it, and the key the
	press was *for* was lost over the delivery of a copy of it. So the send is
	best-effort and the answer says whether it went.
	"""
	_admin()
	doc = _ours(name)
	_keyed(doc)

	asked = frappe.parse_json(values) if isinstance(values, str) else dict(values or {})

	request = frappe.new_doc(REQUEST)
	request.web_form = doc.name
	request.expires_on = frappe.utils.add_days(frappe.utils.now_datetime(),
	                                           int(days or DAYS))
	if asked:
		request.web_form_values = frappe.as_json(asked)
	if about:
		# `link_doctype` is set by the request's own `validate` from the form's
		# doctype, so this names the row and not its type — one fewer thing to
		# get out of step.
		request.append("references", {"link_name": about})
	request.insert(ignore_permissions=True)

	url = _link(doc, request.key)
	return {"name": request.name, "key": request.key, "url": url, "to": to,
	        "mailed": _send(doc, to, url) if to else False}


def _send(doc, to: str, url: str) -> bool:
	"""The invitation, as mail. Whether it went.

	Queued rather than sent inline: a form sent to forty people is forty SMTP
	round trips, and the person who pressed the button should not be holding
	the page open for them.

	Swallowed rather than raised, because the invitation is the key and the
	mail is a copy of it. A workspace that has not set an outgoing account yet
	still gets its link, and the builder says the letter did not go so they can
	send it themselves.
	"""
	try:
		frappe.sendmail(
			recipients=[to],
			subject=doc.title,
			message=(
				f"<p>{frappe.utils.escape_html(doc.title)}</p>"
				f'<p><a href="{url}">{_("Open the form")}</a></p>'
			),
			now=False,
		)
		return True
	except Exception:
		frappe.log_error(title="Form invitation could not be mailed",
		                 message=frappe.get_traceback())
		return False


@frappe.whitelist(methods=["POST"])
def uninvite(request: str) -> dict:
	"""Take one link back.

	Deleted rather than expired, because an invitation is not a record of
	anything: what it produced is a document of its own and stays. A row kept
	as "revoked" would be a list people have to read past for ever.
	"""
	_admin()
	row = frappe.get_doc(REQUEST, request)
	# Through `_ours`, so a request against a form this workspace did not make
	# is refused for the same reason the form itself is.
	_ours(row.web_form)
	frappe.delete_doc(REQUEST, row.name, ignore_permissions=True)
	return {"name": request}


# --------------------------------------------------------------------------- #
# Stage 5 — what a key holder can see
# --------------------------------------------------------------------------- #

@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(key="route", limit=60, seconds=60)
def theirs(route: str, key: str = "") -> dict:
	"""The documents this key may look at, which is the form's own list.

	Straight through to `get_web_form_list`, which filters to the key's own
	`references` before it queries and caps the page at a hundred. This adds
	the route lookup and nothing else — a second reading of which rows a key
	may see is the one thing that must not exist.
	"""
	from frappe.website.doctype.web_form.web_form import get_web_form_list

	from oneapp.oneforms.public import _admitted, _form

	doc = _form(route)
	_admitted(doc, key)
	if not doc.show_list:
		frappe.throw(_("This form does not show a list."), frappe.PermissionError)

	rows = get_web_form_list(web_form=doc.name, web_form_request_key=key)
	return {
		"rows": [dict(row) for row in rows],
		"columns": [
			{"fieldname": one.fieldname, "label": one.label or one.fieldname}
			for one in (doc.list_columns or [])
		],
		"title": doc.list_title or doc.title,
		"can_edit": int(doc.allow_edit or 0),
	}
