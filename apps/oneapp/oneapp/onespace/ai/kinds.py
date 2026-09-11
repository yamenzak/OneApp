"""The three things a model may ask for that belong to no module in particular.

A record saved, a date in somebody's diary, a task. Here rather than in a
module because none of them is about mail or documents or sheets: every one is
the framework's own noun, and a fourth surface wanting to offer "put this in
my calendar" should find the kind already registered rather than write a
second one.

What each of them does on Apply is the rule from `actions.py` made concrete:
**the same path a person would have gone through by hand.** A record goes
through `spaceview.records.save`, which the form posts to. An event goes
through `onecalendar.diary.save_event`, which the diary posts to. A task is
the one that has no screen yet, and its handler says so rather than quietly
inventing a privileged write.
"""

import frappe
from frappe import _

from oneapp.onespace.ai.actions import Kind, Refused, register, same

#: Fields one record suggestion may touch. Not a performance limit — a model
#: that has decided to rewrite forty fields has misunderstood the question,
#: and a card with forty rows is one nobody reads before pressing Apply.
MAX_FIELDS = 20


# --------------------------------------------------------------------------- #
# A record
# --------------------------------------------------------------------------- #

class RecordSave(Kind):
	"""Change a record, or make one. One kind because it is one path.

	A create and an update differ in a `docname` and in the word on the card;
	everything else — resolving the screen, checking the field is writable,
	saving through `records.save` — is the same code, and two handlers would
	be two copies of it with one of them fixed.
	"""

	key = "record.save"
	label = _("Change a record")
	icon = "lucide-pencil-line"

	def check(self, payload: dict) -> dict:
		space = (payload.get("space") or "").strip()
		screen = (payload.get("screen") or "").strip()
		docname = (payload.get("docname") or "").strip()
		values = payload.get("values")

		resolved = self._resolve(space, screen)
		if not resolved.get("doctype"):
			raise Refused(_("That screen holds no records to change."))

		if not isinstance(values, dict) or not values:
			raise Refused(_("Say which fields to set, and to what."))
		if len(values) > MAX_FIELDS:
			raise Refused(_("That is more fields than one change may set."))

		writable = self._writable(resolved)
		unknown = [one for one in values if one not in writable]
		if unknown:
			raise Refused(_("This screen has no field called {0}. Call "
			                "describe_screen to see what it carries.").format(unknown[0]))

		if docname:
			current = self._record(space, screen, docname)
			if not current:
				raise Refused(_("No record called {0} on that screen.").format(docname))
			if not self._editable(resolved["doctype"], docname):
				raise Refused(_("That record is not yours to change where it is."))
			values = {k: v for k, v in values.items() if not same(current.get(k), v)}
			if not values:
				raise Refused(_("It already says that. Nothing to change."))

		return {"space": space, "screen": screen, "docname": docname, "values": values}

	def before(self, payload: dict) -> dict:
		if not payload.get("docname"):
			return {}
		current = self._record(payload["space"], payload["screen"], payload["docname"]) or {}
		return {one: current.get(one) for one in payload["values"]}

	def summarise(self, payload: dict, before: dict) -> str:
		resolved = self._resolve(payload["space"], payload["screen"])
		one_of = resolved.get("singular") or _("record")
		if not payload.get("docname"):
			return _("Create a {0} on {1}").format(one_of, resolved.get("screen_label") or "")

		current = self._record(payload["space"], payload["screen"], payload["docname"]) or {}
		title = (resolved.get("title_field") or "").strip()
		said = str(current.get(title) or "").strip() if title else ""
		docname = payload["docname"]
		called = f"{said} ({docname})" if said and said != docname else docname
		return _("Change {0} on {1}").format(called, self._words(resolved, payload["values"]))

	def rows(self, payload: dict, before: dict) -> list[dict]:
		try:
			resolved = self._resolve(payload["space"], payload["screen"])
		except Exception:
			resolved = {}
		labels = self._labels(resolved)
		return [
			{"label": labels.get(one, one), "was": before.get(one), "now": value}
			for one, value in (payload.get("values") or {}).items()
		]

	def moved(self, payload: dict, before: dict) -> str:
		if not (payload.get("docname") and before):
			return ""
		now = self._record(payload["space"], payload["screen"], payload["docname"])
		if not now:
			return _("That record is gone.")
		moved = [one for one, was in before.items() if not same(was, now.get(one))]
		if moved:
			return _("{0} changed since this was suggested, so it was not "
			         "applied.").format(", ".join(moved))
		return ""

	def apply(self, payload: dict, before: dict) -> dict:
		from oneapp.onespace.spaceview.records import save

		resolved = self._resolve(payload["space"], payload["screen"])
		written = save(
			space_code=payload["space"], screen=payload["screen"],
			values=payload["values"], name=payload.get("docname") or None,
		)
		return {
			"doctype": resolved.get("doctype") or "",
			"name": written.get("name") or payload.get("docname") or "",
		}

	# --- the screen, asked once per call rather than re-implemented --------

	@staticmethod
	def _resolve(space: str, screen: str) -> dict:
		from oneapp.onespace.spaceview.resolve import _resolve

		return _resolve(space, screen)

	@staticmethod
	def _writable(resolved: dict) -> set:
		"""What this screen may write. `records._writable`, not a second answer."""
		from oneapp.onespace.spaceview.records import _writable as allowed

		return set(allowed(resolved))

	@staticmethod
	def _record(space: str, screen: str, docname: str) -> dict | None:
		from oneapp.onespace.spaceview.records import record

		return record(space_code=space, screen=screen, name=docname)

	@staticmethod
	def _editable(doctype: str, docname: str) -> bool:
		"""The workflow's answer, asked before the card is drawn rather than after.

		`records.save` asks it too and would refuse on Apply. Asking here as
		well is the difference between the model being told now and a person
		being told after they agreed to something that was never going to
		happen.
		"""
		from oneapp.onespace import docflow

		try:
			return bool(docflow.editable(frappe.get_doc(doctype, docname)))
		except frappe.PermissionError:
			return False

	@staticmethod
	def _labels(resolved: dict) -> dict:
		return {c["fieldname"]: c.get("label") or c["fieldname"]
		        for c in (resolved.get("all_columns") or resolved.get("columns") or [])}

	def _words(self, resolved: dict, values: dict) -> str:
		labels = self._labels(resolved)
		return ", ".join(labels.get(one, one) for one in values)


# --------------------------------------------------------------------------- #
# A date in somebody's diary
# --------------------------------------------------------------------------- #

class CalendarEvent(Kind):
	"""Put something in the asker's own week.

	Theirs and private, which is what `diary.save_event` already writes: a
	public Event is one the whole site sees, and a model offering to make one
	is the last place to allow that by accident.
	"""

	key = "calendar.event"
	label = _("Add to calendar")
	icon = "lucide-calendar"

	def check(self, payload: dict) -> dict:
		subject = (payload.get("subject") or "").strip()
		if not subject:
			raise Refused(_("Say what the event is called."))

		starts_on = _when(payload.get("starts_on"))
		if not starts_on:
			raise Refused(_("Say when it starts, as a date and time."))

		ends_on = _when(payload.get("ends_on"))
		# Silently dropped rather than refused: a model that returned an end
		# before the start has made a typo about one field, and the event is
		# still worth offering without it.
		if ends_on and ends_on < starts_on:
			ends_on = ""

		return {
			"subject": subject[:140],
			"starts_on": starts_on,
			"ends_on": ends_on,
			"all_day": 1 if payload.get("all_day") else 0,
			"description": (payload.get("description") or "").strip()[:2000],
		}

	def summarise(self, payload: dict, before: dict) -> str:
		return _("Put {0} in your calendar on {1}").format(
			payload["subject"], frappe.utils.format_datetime(payload["starts_on"]),
		)

	def rows(self, payload: dict, before: dict) -> list[dict]:
		said = [
			{"label": _("What"), "now": payload["subject"]},
			{"label": _("Starts"), "now": frappe.utils.format_datetime(payload["starts_on"])},
		]
		if payload.get("ends_on"):
			said.append({"label": _("Ends"),
			             "now": frappe.utils.format_datetime(payload["ends_on"])})
		if payload.get("description"):
			said.append({"label": _("Notes"), "now": payload["description"]})
		return said

	def apply(self, payload: dict, before: dict) -> dict:
		from oneapp.onecalendar import diary

		done = diary.save_event(payload)
		return {"doctype": diary.EVENT, "name": done.get("name") or ""}


# --------------------------------------------------------------------------- #
# A task
# --------------------------------------------------------------------------- #

class Task(Kind):
	"""One thing to do, for the person who was offered it.

	The one kind with no endpoint behind it, and the reason is worth writing
	down rather than working out later: this product has no tasks *screen*
	yet, so there is no "the same path a person would have gone through" to
	route through. What it does instead is the narrowest thing that is still
	honest — insert a `ToDo` allocated to the asker, as the asker, under the
	framework's own permission check on that doctype. Nothing here is
	privileged and nothing is assigned to anybody else: a task a model made
	for a colleague is a notification they did not agree to.

    When a tasks screen exists, this handler should go through it and this
    paragraph should go.
	"""

	key = "task"
	label = _("Make a task")
	icon = "lucide-circle-check"

	def check(self, payload: dict) -> dict:
		what = (payload.get("what") or "").strip()
		if not what:
			raise Refused(_("Say what the task is."))
		return {
			"what": what[:500],
			"due": frappe.utils.getdate(payload["due"]).isoformat()
			if payload.get("due") else "",
			"priority": payload.get("priority")
			if payload.get("priority") in ("Low", "Medium", "High") else "Medium",
		}

	def summarise(self, payload: dict, before: dict) -> str:
		if payload.get("due"):
			return _("Add a task: {0}, by {1}").format(
				payload["what"], frappe.utils.formatdate(payload["due"]))
		return _("Add a task: {0}").format(payload["what"])

	def rows(self, payload: dict, before: dict) -> list[dict]:
		said = [{"label": _("Task"), "now": payload["what"]}]
		if payload.get("due"):
			said.append({"label": _("Due"), "now": frappe.utils.formatdate(payload["due"])})
		return said

	def apply(self, payload: dict, before: dict) -> dict:
		doc = frappe.get_doc({
			"doctype": "ToDo",
			"description": payload["what"],
			"allocated_to": frappe.session.user,
			"date": payload.get("due") or None,
			"priority": payload.get("priority") or "Medium",
		})
		doc.insert()
		return {"doctype": "ToDo", "name": doc.name}


def _when(value) -> str:
	"""A datetime a model wrote, or nothing.

	Nothing rather than an exception: a date it could not express is one field
	of a suggestion, and `check` decides whether the suggestion survives
	without it.
	"""
	if not value:
		return ""
	try:
		return frappe.utils.get_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
	except Exception:
		return ""


register(RecordSave())
register(CalendarEvent())
register(Task())
