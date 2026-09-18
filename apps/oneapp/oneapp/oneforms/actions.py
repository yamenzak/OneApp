"""What a model may ask a form to be.

Two kinds, and they are the two halves of making one: **build this form** and
**make it look like this**. Both go through `oneai/actions.py`'s card, which is
this product's rule for anything a model wants to change — a person agrees to
the diff, not to a summary of it — and both end at the same service calls a
person pressing the buttons would reach.

**The rule is not relaxed for a model.** `service._over` refuses a doctype no
space of the asker's shows them, and it is called here in `check` rather than
in `apply`: a card that offered to build a form over Salary Slip and then
refused on Apply would be a card that told somebody they could do something
they could not. Every fieldname is checked against the doctype's own, for the
same reason and at the same moment.

**And the model is not the one that writes.** A proposal is a payload; Apply
calls `make`, `layout`, `settings` and `style`, which are the same four the
builder posts to and carry the same checks. There is no privileged path here,
which is why this file is short.

`docs/ONEFORMS.md`. `onedoc/actions.py` is the pattern and says why a card is
written on the turn it is proposed rather than on Apply.
"""

from typing import Annotated

import frappe
from frappe import _

from oneapp.oneai import proposing
from oneapp.oneai.actions import Kind, Refused, register
from oneapp.oneai.tools import Tool, tool
from oneapp.oneforms import service

#: Fields one proposed form may carry. A form a stranger fills in is a page
#: they read top to bottom, and past this it is a data-entry screen — which is
#: what the space is for.
MOST_FIELDS = 25

#: Doctypes one listing carries. A workspace with every space enabled offers a
#: few dozen; past that the answer is a catalogue rather than a choice, and the
#: count that follows says how many were left out.
MOST_DOCTYPES = 40

#: How a card says who may reach the form, against what `settings` writes. The
#: model picks a word rather than three checkboxes, because three booleans that
#: contradict each other is a state nobody meant.
ACCESS = {
	"anyone": {"anonymous": 1, "login_required": 0, "key_required": 0},
	"signed-in": {"anonymous": 0, "login_required": 1, "key_required": 0},
	"invitation": {"anonymous": 0, "login_required": 0, "key_required": 1},
}


def _asked(call, *args):
	"""A service check, run at proposal time, with its refusal kept.

	`service` says no by throwing, which is right for an endpoint and wrong
	here: `actions.propose` turns a `PermissionError` into "That is not yours
	to change", and the whole point of checking early is that the model is
	told *which* rule it broke on the turn it broke it. So the sentence the
	service wrote is the sentence the model reads.
	"""
	try:
		return call(*args)
	except Exception as e:
		raise Refused(str(getattr(e, "message", None) or e) or
		              _("That cannot be done.")) from e


class BuildForm(Kind):
	"""A form, described and waiting to be made."""

	key = "forms.build"
	label = _("Build a form")
	icon = "lucide-inbox"

	def check(self, payload: dict) -> dict:
		# Both asked now rather than on Apply: making a form is the workspace
		# admin's, and it can only ever be over a doctype one of their own
		# spaces shows them. A card that offered either and then refused would
		# have told somebody they could do something they could not.
		_asked(service._admin)
		doctype = (payload.get("doctype") or "").strip()
		over = _asked(service._over, doctype)

		title = (payload.get("title") or "").strip() or over["label"]
		access = (payload.get("access") or "signed-in").strip()
		if access not in ACCESS:
			raise Refused(_("Say who may reach it: anyone, signed-in or invitation."))

		known = {one["fieldname"]: one for one in service.available(doctype)}
		asked = payload.get("fields") or []
		if not isinstance(asked, list) or not asked:
			raise Refused(_("A form with no fields on it is a page that asks "
			                "nothing."))
		if len(asked) > MOST_FIELDS:
			raise Refused(_("That is more fields than one form should ask for "
			                "in a single page."))

		fields = []
		for row in asked:
			if not isinstance(row, dict):
				continue

			# The three that are furniture rather than questions. A model that
			# could only list fields could only ever build a column, and a
			# thirty-question column is a form nobody finishes — see
			# `oneforms/lib/layout.js` and `docs/ONEFORMS.md` §13.
			fieldtype = (row.get("fieldtype") or "").strip()
			if fieldtype in service.BREAKS:
				fields.append({"fieldtype": fieldtype,
				               "label": (row.get("label") or "").strip()})
				continue

			fieldname = (row.get("fieldname") or "").strip()
			field = known.get(fieldname)
			if not field:
				raise Refused(
					_("{0} is not a field on {1}.").format(fieldname or "?", _(doctype)))
			fields.append({
				"fieldname": fieldname,
				"label": (row.get("label") or field["label"]).strip(),
				"reqd": 1 if field["reqd"] else int(row.get("reqd") or 0),
			})

		return {
			"doctype": doctype, "title": title[:140], "access": access,
			"introduction": (payload.get("introduction") or "").strip()[:2_000],
			"fields": fields,
		}

	def summarise(self, payload: dict, before: dict) -> str:
		return _("Build {0}, a form over {1}").format(
			payload["title"], _(payload["doctype"]))

	def rows(self, payload: dict, before: dict) -> list[dict]:
		said = [{"label": _("Name"), "now": payload["title"]},
		        {"label": _("Makes a"), "now": _(payload["doctype"])},
		        {"label": _("Who can reach it"), "now": self._said(payload["access"])}]
		if payload.get("introduction"):
			said.append({"label": _("Introduction"), "now": payload["introduction"]})
		# Every field, not a count. The whole argument for a card is that
		# somebody reads what would happen, and "nine fields" is a summary.
		said.append({"label": _("Asks for"),
		             "now": "\n".join(self._reads(one) for one in payload["fields"])})
		return said

	@staticmethod
	def _reads(one: dict) -> str:
		"""One row of the card's field list, furniture included.

		A break is shown rather than skipped: whether a form is four steps or
		one page is the thing about it a person notices first, and a card that
		listed only the questions would be a card that got that wrong silently.
		"""
		if one.get("fieldtype") == "Page Break":
			return _("— next step —")
		if one.get("fieldtype") == "Section Break":
			return _("{0} —").format(one.get("label") or _("Section"))
		if one.get("fieldtype") == "Column Break":
			return _("— beside —")
		return f"{one['label']}{' *' if one['reqd'] else ''}"

	def apply(self, payload: dict, before: dict) -> dict:
		made = service.make(payload["doctype"], payload["title"])
		service.layout(made["name"], payload["fields"])
		service.settings(made["name"], {
			**ACCESS[payload["access"]],
			"introduction_text": payload.get("introduction") or "",
		})
		return {"doctype": service.FORM, "name": made["name"]}

	def opened(self, payload: dict, done: dict) -> dict:
		"""Where the form it made is — the builder, unpublished."""
		if not done.get("name"):
			return {}
		return {"label": _("Open it"), "href": f"/one/forms/{done['name']}"}

	@staticmethod
	def _said(access: str) -> str:
		return {"anyone": _("Anyone with the link"),
		        "signed-in": _("Anybody signed in"),
		        "invitation": _("Only by invitation")}[access]


class StyleForm(Kind):
	"""A stylesheet for a form that already exists."""

	key = "forms.style"
	label = _("Style a form")
	icon = "lucide-palette"

	def check(self, payload: dict) -> dict:
		_asked(service._admin)
		name = (payload.get("form") or "").strip()
		doc = _asked(service._ours, name)
		css = _asked(service.check_css, payload.get("css") or "")
		if not css:
			raise Refused(_("Write the stylesheet. An empty one changes "
			                "nothing."))
		return {"form": doc.name, "title": doc.title, "css": css}

	def before(self, payload: dict) -> dict:
		return {"css": frappe.db.get_value(service.FORM, payload["form"],
		                                   "custom_css") or ""}

	def summarise(self, payload: dict, before: dict) -> str:
		return _("Restyle {0}").format(payload["title"])

	def rows(self, payload: dict, before: dict) -> list[dict]:
		return [{"label": _("Styling"), "was": before.get("css") or "",
		         "now": payload["css"]}]

	def moved(self, payload: dict, before: dict) -> str:
		"""Somebody wrote a different stylesheet while this card waited.

		`actions.py`'s second rule, and a replace rather than a patch is
		exactly where it bites: the card showed what was there against what
		the model wrote, and applying it now would throw away work nobody on
		this card has seen.
		"""
		now = frappe.db.get_value(service.FORM, payload["form"], "custom_css") or ""
		if now != (before.get("css") or ""):
			return _("The styling has changed since this was suggested.")
		return ""

	def apply(self, payload: dict, before: dict) -> dict:
		service.style(payload["form"], payload["css"])
		return {"doctype": service.FORM, "name": payload["form"]}

	def opened(self, payload: dict, done: dict) -> dict:
		return {"label": _("Open it"), "href": f"/one/forms/{payload['form']}"}


register(BuildForm())
register(StyleForm())


# --------------------------------------------------------------------------- #
# The two tools that ask
#
# Beside the kinds rather than in `oneai/proposing.py`, which holds the four
# the spine ships with: a form belongs to OneForms, and `docs/ARCHITECTURE.md`
# says a module owns both halves of its own feature.
# --------------------------------------------------------------------------- #


@tool
def the_forms_of_this_workspace() -> dict:
	"""The forms this workspace already has, and the doctypes a new one could
	be made over with the fields each has. Call this before proposing a form
	or a restyle: a form can only be made over something one of their own
	spaces already shows them, the field names have to be that doctype's own,
	and a restyle needs the id of a form that exists."""
	try:
		service._admin()
	except Exception:
		# Said rather than thrown. "Only an admin can make a form" is an
		# answer a model can give the person; a traceback is not.
		return {"forms": [], "could_be_made_over": [],
		        "reason": "only a workspace admin can make or style a form"}

	found = service.offerable()
	return {
		"forms": [
			{"id": one["name"], "title": one["title"], "makes_a": one["doc_type"],
			 "published": bool(one["published"]),
			 "invited": one.get("invited"), "answered": one.get("answered")}
			for one in service.forms()["rows"]
		],
		"could_be_made_over": [
			{**one, "fields": [
				{"fieldname": field["fieldname"], "label": field["label"],
				 "fieldtype": field["fieldtype"], "required": bool(field["reqd"])}
				for field in service.available(one["doctype"])
			]}
			for one in found[:MOST_DOCTYPES]
		],
		"more": max(0, len(found) - MOST_DOCTYPES),
	}


@tool
def propose_form(
	session: Annotated[str, "Filled in for you."],
	about_doctype: Annotated[str, "Filled in for you."],
	about_name: Annotated[str, "Filled in for you."],
	doctype: Annotated[str, "The doctype the form writes into — one of the "
	                        "names the_forms_of_this_workspace returned."],
	title: Annotated[str, "What the form is called, as the person filling it "
	                      "in would read it at the top of the page."],
	fields: Annotated[
		list,
		"The fields, in the order they should be asked, as "
		"[{'fieldname': '…', 'label': '…', 'reqd': 0 or 1}]. "
		"Every fieldname must be one that doctype actually has. Relabel freely "
		"— the doctype's own names are for staff and the form is not. "
		"Three entries have no fieldname and are layout instead: "
		"{'fieldtype': 'Page Break'} starts a new step, with a progress bar "
		"and a Next; {'fieldtype': 'Section Break', 'label': '…'} starts a "
		"titled group; {'fieldtype': 'Column Break'} puts what follows beside "
		"what came before rather than under it.",
	],
	access: Annotated[str, "anyone, signed-in or invitation."] = "signed-in",
	introduction: Annotated[str, "A sentence or two above the first field, "
	                             "saying what this is for. Plain text."] = "",
) -> dict:
	"""Build a form and ask to make it. Nothing is made until the person approves.

	Call the_forms_of_this_workspace first and pick from what it returns —
	a form can only ever be over a doctype one of their own spaces shows them,
	and a fieldname that doctype has not got is refused.

	Ask for what somebody outside would reasonably know. A doctype has columns
	for the staff who work it — a status, an owner, a workflow state — and none
	of those belong on a page a stranger fills in.

	Lay it out. Past about six questions, put a page break between the groups
	— a long form is a scroll people abandon and four steps of five is one they
	finish — and use a column break to put two short related fields side by
	side rather than under one another.

	The form is made unpublished, so say it is waiting and that they can look
	at it before it goes live.
	"""
	return proposing.ask("forms.build", session, about_doctype, about_name, {
		"doctype": doctype, "title": title, "fields": fields,
		"access": access, "introduction": introduction,
	})


@tool
def propose_form_styling(
	session: Annotated[str, "Filled in for you."],
	about_doctype: Annotated[str, "Filled in for you."],
	about_name: Annotated[str, "Filled in for you."],
	form: Annotated[str, "The form's id, as the_forms_of_this_workspace lists it."],
	css: Annotated[
		str,
		"The whole stylesheet, replacing whatever is there. Plain CSS. It is "
		"loaded on the public page, which draws nothing but the form, so "
		"ordinary selectors (h1, label, input, button) reach it. Four named "
		"hooks that will not move: [data-slot='form-page'] is the page behind "
		"the form (not body, which the page paints over), "
		"[data-slot='public-form'] the form itself, [data-slot='form-title'] "
		"its heading, [data-slot='form-introduction'] the paragraph above the "
		"first field. "
		"No @import and no url() to another site — a data: url is fine.",
	],
) -> dict:
	"""Restyle a form's public page. Nothing changes until the person approves.

	The whole stylesheet, not a patch: the card shows what is there now against
	what you wrote, and a fragment would make that comparison a lie.
	"""
	return proposing.ask("forms.style", session, about_doctype, about_name, {
		"form": form, "css": css,
	})


def tools() -> list[Tool]:
	"""What `onespace_chat_tools` asks this module for."""
	return [the_forms_of_this_workspace, propose_form, propose_form_styling]
