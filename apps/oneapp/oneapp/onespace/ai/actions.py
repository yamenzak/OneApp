"""Something a model asked for, and the moment a person says yes.

A model in this product cannot write. What it can do is put a card in front of
somebody — this record, these fields, that value; this date, in your diary;
this, as a task — and the doing happens later, in a request a person made by
pressing Apply, through the same path they would have gone through by hand.

That split is the whole of the safety argument and it is worth being exact
about why it is not a formality. A tool that saves is a tool that saves on a
model's say-so, and the failure mode is not a wrong field — it is a wrong
*record*, at the end of a chain of lookups nobody read. Putting a human
between the asking and the doing also puts the diff in front of them while
they decide.

**One doctype and a kind.** The assistant's record edit was the first of these
and for a while the only one, which is why it used to live in
`chat/changes.py` under a doctype called Chat Change. What broke that was mail
noticing a date and offering to put it in a diary: three more verbs would have
meant three more tables, three more cards and three more Apply endpoints, and
no two of them agreeing what Proposed means. So a `Kind` is a small class with
six methods, a module registers its own through the `ai_actions` hook, and
adding "AI noticed X and offers Y" is a handler and nothing else.

Four rules every kind keeps, and the registry is where they are enforced
rather than remembered:

* **It is checked when it is proposed, not when it is applied.** A model that
  named a field wrongly is told so on the turn it made the mistake, rather
  than a person discovering it after they agreed to something.
* **What is there now is captured with it.** `before` holds what the handler
  read at proposal time; Apply compares, and something that moved in between
  is refused rather than overwritten. The person agreed to a diff and it is no
  longer that diff.
* **Applying runs as the person.** Never `ignore_permissions`, never a
  privileged path: a change to a screen they may not write is refused here
  exactly as it would be from the form.
* **Nothing drains this.** No scheduler, no queue, no retry. A proposal nobody
  answered is a question nobody answered, and the only two things that resolve
  one are a person pressing Apply and a person pressing Discard.
"""

import json

import frappe
from frappe import _

SUGGESTION = "OneSpace Suggestion"

PROPOSED, APPLIED, DISCARDED, FAILED = "Proposed", "Applied", "Discarded", "Failed"

#: key -> Kind. Populated by import, which is why `discover()` exists.
REGISTRY: dict[str, "Kind"] = {}


class Refused(Exception):
	"""Why this cannot be proposed, in words the model is shown.

	An exception rather than an error dict because a handler is several
	functions deep by the time it knows, and threading a refusal back up
	through each of them is how one of them ends up not doing it.
	"""


class Kind:
	"""One thing a model may ask for.

	Six methods, of which two are required. Subclass, set `key`, `label` and
	`icon`, and register it — see `kinds.py` for the four this ships with.
	"""

	#: `module.verb`. Namespaced because a kind is a registry entry and two
	#: apps will eventually both want to call one `task`.
	key = ""
	label = ""
	icon = ""

	def check(self, payload: dict) -> dict:
		"""Normalise, and raise `Refused` if this could not be done.

		Everything knowable now is decided now: the screen resolves, the field
		exists, the date parses, the record is one this person may edit. What
		comes back is what gets stored, so a handler may fill in defaults here
		and rely on them in `apply`.
		"""
		return payload

	def before(self, payload: dict) -> dict:
		"""What is there now, for the fields this would change. `{}` where
		there is nothing to compare — a create, a new event."""
		return {}

	def summarise(self, payload: dict, before: dict) -> str:
		"""One line. Written here rather than by the model.

		A card whose heading is the model's wording and whose rows are the
		stored payload is a card that can say two different things, and the one
		somebody reads is the heading.
		"""
		return self.label

	def rows(self, payload: dict, before: dict) -> list[dict]:
		"""The card's body, as `{label, was, now}`.

		Resolved on the way out rather than stored, so a screen that renames a
		column renames it on a card nobody has answered yet.
		"""
		return []

	def moved(self, payload: dict, before: dict) -> str:
		"""Whether what this would change has changed since, said in words."""
		return ""

	def apply(self, payload: dict, before: dict) -> dict:
		"""Do it, as the person who pressed the button. `{doctype, name}`."""
		raise NotImplementedError


def register(kind: Kind) -> Kind:
	REGISTRY[kind.key] = kind
	return kind


def discover() -> dict[str, Kind]:
	"""Import every module an installed app declared under `ai_actions`.

	Hooks rather than a filesystem walk, and for the same reason `ai_features`
	uses them: a kind that only registers when something happens to import its
	module is a card that fails to apply on a cold worker.
	"""
	for path in frappe.get_hooks("ai_actions") or []:
		try:
			frappe.get_module(path)
		except Exception:
			frappe.log_error(
				title=f"AI action module {path} failed to import",
				message=frappe.get_traceback(),
			)
	return REGISTRY


def get(key: str) -> Kind | None:
	if key not in REGISTRY:
		discover()
	return REGISTRY.get(key)


def kinds() -> list[dict]:
	"""What a model may ask for, as the tool description needs it."""
	discover()
	return [{"kind": one.key, "label": one.label} for one in REGISTRY.values()]


# --------------------------------------------------------------------------- #
# Proposing
# --------------------------------------------------------------------------- #

def propose(kind: str, payload: dict, *, about: tuple[str, str] | None = None,
            session: str = "", after_message: str = "") -> dict:
	"""Record what would be done, having checked that it could be.

	Returns what a *model* is told, which is deliberately not "done": it says
	the thing is waiting, so the answer the model writes afterwards says so
	too. A surface calling this directly reads `proposed` and draws the card.
	"""
	handler = get(kind)
	if not handler:
		return {"error": _("There is no such suggestion.")}

	try:
		payload = handler.check(dict(payload or {}))
		before = handler.before(payload)
	except Refused as e:
		return {"error": str(e)}
	except frappe.PermissionError:
		return {"error": _("That is not yours to change.")}

	doc = frappe.get_doc({
		"doctype": SUGGESTION,
		"kind": kind,
		"state": PROPOSED,
		"summary": handler.summarise(payload, before),
		"payload": json.dumps(payload, default=str),
		"before": json.dumps(before, default=str),
		"about_doctype": (about or ("", ""))[0],
		"about_name": (about or ("", ""))[1],
		"session": session or "",
		"after_message": after_message or "",
	})
	doc.insert()

	return {
		"proposed": doc.name,
		"summary": doc.summary,
		"note": _("Nothing has happened yet. This is waiting for the person to "
		          "approve it — tell them what it would do and stop there."),
	}


# --------------------------------------------------------------------------- #
# Answering
# --------------------------------------------------------------------------- #

def mine(name: str, level: str = "read"):
	"""The suggestion, if it is this person's."""
	if not frappe.has_permission(SUGGESTION, level, doc=name):
		frappe.throw(_("That suggestion is not yours."), frappe.PermissionError)
	return frappe.get_doc(SUGGESTION, name)


def apply(name: str) -> dict:
	"""Do it. This is the write, and it is a request a person made."""
	doc = mine(name, "write")
	if doc.state != PROPOSED:
		frappe.throw(_("That has already been answered."))

	handler = get(doc.kind)
	if not handler:
		frappe.throw(_("There is no such suggestion."))

	payload, before = _read(doc.payload), _read(doc.before)

	if stale := handler.moved(payload, before):
		doc.db_set({"state": FAILED, "error": stale}, update_modified=False)
		return {"ok": False, "state": FAILED, "error": stale}

	# A savepoint rather than the whole transaction: a validation failure
	# part-way through a document must not leave half of it behind, and
	# rolling the request back instead would take the Failed row with it and
	# leave the card on Proposed, inviting the same press.
	frappe.db.savepoint("ai_action")
	try:
		done = handler.apply(payload, before) or {}
	except Exception as e:
		frappe.db.rollback(save_point="ai_action")
		doc.db_set({"state": FAILED, "error": _said(e)}, update_modified=False)
		return {"ok": False, "state": FAILED, "error": doc.error}
	frappe.db.release_savepoint("ai_action")

	doc.db_set({
		"state": APPLIED,
		"applied_on": frappe.utils.now(),
		"applied_doctype": done.get("doctype") or "",
		"applied_name": done.get("name") or "",
	}, update_modified=False)
	return {"ok": True, "state": APPLIED, **done}


def discard(name: str) -> dict:
	"""No. Kept rather than deleted, so the thread still says it was asked."""
	doc = mine(name, "write")
	if doc.state != PROPOSED:
		frappe.throw(_("That has already been answered."))
	doc.db_set({"state": DISCARDED}, update_modified=False)
	return {"ok": True, "state": DISCARDED}


# --------------------------------------------------------------------------- #
# Reading them back
# --------------------------------------------------------------------------- #

def for_session(session: str) -> list[dict]:
	"""Every suggestion made in one chat thread, oldest first."""
	return _listing({"session": session})


def for_about(doctype: str, name: str) -> list[dict]:
	"""Every suggestion made about one thing — a conversation, a document."""
	if not (doctype and name):
		return []
	return _listing({"about_doctype": doctype, "about_name": name})


def _listing(filters: dict) -> list[dict]:
	rows = frappe.get_list(
		SUGGESTION,
		filters=filters,
		fields=["name", "kind", "state", "summary", "payload", "before",
		        "after_message", "applied_doctype", "applied_name", "error"],
		order_by="creation asc",
		limit_page_length=0,
	)
	for row in rows:
		payload, before = _read(row.get("payload")), _read(row.get("before"))
		handler = get(row["kind"])
		row["payload"] = payload
		row["before"] = before
		row["label"] = handler.label if handler else row["kind"]
		row["icon"] = handler.icon if handler else ""
		# A handler whose own lookup fails — a screen that has gone, a doctype
		# an app took with it — must not take the card with it. An empty body
		# under a summary that still reads is a card somebody can still
		# discard.
		try:
			row["rows"] = handler.rows(payload, before) if handler else []
		except Exception:
			row["rows"] = []
	return rows


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def apply_suggestion(name: str) -> dict:
	"""Make it happen. The one write in this module, and a person asked for it.

	Reachable by a browser and by nothing else: there is no tool that calls it,
	and adding one would undo the only thing that makes proposing safe.
	"""
	return apply(name)


@frappe.whitelist(methods=["POST"])
def discard_suggestion(name: str) -> dict:
	"""No. The row stays, so the surface still shows it was offered."""
	return discard(name)


@frappe.whitelist(methods=["GET"])
def suggestions(doctype: str, name: str) -> list[dict]:
	"""What has been suggested about one thing, for the surface showing it."""
	return for_about(doctype, name)


# --------------------------------------------------------------------------- #
# Small shared things
# --------------------------------------------------------------------------- #

def same(one, other) -> bool:
	"""Whether two stored values are the same to a person.

	`1` and `"1"` come back differently from a form and from a model, and a
	proposal that reads as a change because a check arrived as a string is a
	card with a row on it saying nothing changed.
	"""
	if one is None or one == "":
		one = ""
	if other is None or other == "":
		other = ""
	return str(one) == str(other)


def _said(e: Exception) -> str:
	"""What went wrong, in the words the form would have shown.

	Frappe's own validation speaks through `frappe.throw`, which puts a
	sentence a person can act on into the message log; the exception's own
	`str` is that sentence wrapped in markup or, for anything else, a class
	name. So the log first, and a plain apology rather than a traceback when
	there is nothing in it — a stack trace on a card is a stack trace in front
	of a customer.
	"""
	log = getattr(frappe.local, "message_log", None) or []
	said = ""
	if log:
		last = log[-1]
		said = (last.get("message") if isinstance(last, dict) else str(last)) or ""
	said = frappe.utils.strip_html(said).strip() if said else ""
	return (said or _("That could not be done."))[:500]


def _read(raw):
	try:
		found = json.loads(raw or "{}")
	except (TypeError, ValueError):
		return {}
	return found if isinstance(found, dict) else {}
