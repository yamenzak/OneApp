"""One change, applied to a selection.

Forty records whose status is wrong are forty round trips through a record
pane, and the person fixing them is doing data entry with a form in the way.
The report view answers that one cell at a time; this answers it for a whole
selection at once, which is what the desk's bulk operations are for.

Two rules, and they are the same two `remove` follows:

* **One call, not one per row.** A selection of forty is forty requests
  otherwise, and a partial failure halfway through leaves nobody able to say
  what happened.

* **Each record is saved on its own, and what could not be saved is named.**
  Through `save()` rather than `db.set_value`, so the doctype's own validation,
  its permissions, its `fetch_from` and its workflow all still run — and a
  submitted document, a mandatory field left empty or a rule the value breaks
  is a fact about that record rather than a bug in this. Forty records do not
  fail as one opaque error.

What is deliberately not here is a filter. A bulk change takes a list of ids
that came from a selection somebody made and looked at; "apply this to
everything that matches" is the same operation with the safety catch taken off.
"""

import re

import frappe
from frappe import _

from .filters import MAX_DELETE
from .resolve import _resolve
from .records import _writable
from .assign import _colleagues


@frappe.whitelist(methods=["POST"])
def bulk_set(space_code: str, screen: str, names: str | list, field: str,
             value: str | int | float | bool | None = None) -> dict:
	"""Set one field to one value on every record in a selection."""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("This screen has nothing to change."))

	# The same allowlist a single save goes through: the screen decides which
	# fields may be written, so a bulk change cannot reach a field the screen
	# does not show.
	if field not in _writable(resolved):
		frappe.throw(_("{0} is not a field this screen may change.").format(field))

	return _each(doctype, _names(names), lambda doc: doc.set(field, value))


@frappe.whitelist(methods=["POST"])
def bulk_assign(space_code: str, screen: str, names: str | list,
                users: str | list = None) -> dict:
	"""Add people to the assignment on every record in a selection.

	Added rather than replaced, which is the opposite of what the single-record
	control does and is right for both. One record's assignment is a list
	somebody is looking at and editing whole; a selection's is not on screen at
	all, and replacing forty assignments with one name is a way to take work off
	thirty-nine people by accident.
	"""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("This screen has nothing to assign."))

	wanted = _people(users)
	if not wanted:
		frappe.throw(_("Nobody to assign it to."))

	from frappe.desk.form.assign_to import add

	found, refused = [], []
	for one in _names(names):
		try:
			add({"doctype": doctype, "name": one, "assign_to": wanted})
			found.append(one)
		except Exception as exc:
			refused.append({"name": one, "reason": str(exc)})
	return {"ok": not refused, "done": found, "refused": refused}


def _names(names) -> list[str]:
	"""The selection, as ids and nothing else, and never more than the cap."""
	if isinstance(names, str):
		try:
			names = frappe.parse_json(names or "null")
		except (TypeError, ValueError):
			names = None
	if not isinstance(names, (list, tuple)):
		frappe.throw(_("Nothing was selected."))

	kept = [one for one in names if isinstance(one, str) and one]
	if not kept:
		frappe.throw(_("Nothing was selected."))
	# The same ceiling a bulk delete has, and for the same reason: past it this
	# is a script somebody should be writing rather than a button.
	if len(kept) > MAX_DELETE:
		frappe.throw(_("Too many at once. Choose {0} or fewer.").format(MAX_DELETE))
	return kept


def _people(users) -> list[str]:
	"""Who was chosen, narrowed to people this workspace actually has.

	`_colleagues` is what `assignees` offers the picker from, so an id typed
	into the request that is not on it is not somebody this workspace can assign
	anything to. Checked here rather than trusted, because a selection travels
	as JSON in a request body like anything else.
	"""
	if isinstance(users, str):
		try:
			users = frappe.parse_json(users or "null")
		except (TypeError, ValueError):
			users = None
	if not isinstance(users, (list, tuple)):
		return []

	offered = set(_colleagues())
	return [one for one in dict.fromkeys(users) if isinstance(one, str) and one in offered]


def _each(doctype: str, names: list[str], change) -> dict:
	"""Apply one change to each record, and say which ones would not take it.

	Three things a per-record `try` alone does not give you, and every one of
	them was found by pointing this at a submitted document:

	* **A savepoint per record.** A `save()` that raises has already written
	  part of itself, and the request commits at the end regardless — so
	  without this, a record that refused the change would leave half of one
	  behind in the same transaction as the thirty-nine that took it.

	* **The message log cleared.** `frappe.throw` puts its message in
	  `message_log` and this catches the exception, but the message stays — and
	  the browser reads a response carrying one as a failed request. A batch
	  where one record refused came back as "Something went wrong" with no
	  detail, which is precisely the swallowing this exists to prevent.

	* **The status code put back.** `throw` also sets the response to 417, and
	  that outlives the `except` too.
	"""
	done, refused = [], []
	for one in names:
		frappe.db.savepoint("oneapp_bulk")
		try:
			doc = frappe.get_doc(doctype, one)
			change(doc)
			doc.save()
			done.append(one)
		except Exception as exc:
			# A submitted document, a validation rule, a permission this person
			# does not have on this row: all facts about that record, and all
			# worth saying per record rather than as one failure.
			frappe.db.rollback(save_point="oneapp_bulk")
			refused.append({"name": one, "reason": _said(exc)})
			_quietly()
	return {"ok": not refused, "done": done, "refused": refused}


def _said(exc: Exception) -> str:
	"""What went wrong, in words rather than in markup.

	Frappe writes its validation messages with `<strong>` in them, which is
	right in a desk dialog that renders HTML and wrong in a toast that does
	not — the tags arrive as literal text beside the sentence.
	"""
	return re.sub(r"<[^>]+>", "", str(exc)).strip()


def _quietly() -> None:
	"""Undo what `frappe.throw` left behind in the response.

	The whole log rather than the last message: a `save()` can raise after
	printing more than one, and `clear_last_message` pops exactly one — which
	left the browser reading the answer as a failed request with no detail,
	because the client treats any `_server_messages` as an error.

	Nothing is lost by being blunt here. This endpoint's own answer carries the
	detail, per record and named, which is more than a message log would have
	said.
	"""
	frappe.local.message_log = []
	if isinstance(getattr(frappe.local, "response", None), dict):
		frappe.local.response.pop("http_status_code", None)
		frappe.local.response.pop("_server_messages", None)
