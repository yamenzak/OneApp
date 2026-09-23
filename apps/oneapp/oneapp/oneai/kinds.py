"""What a model may ask for that belongs to no module in particular: a record
saved. Here rather than in a module because it is the framework's own noun.

What it does on Apply is the rule from `actions.py` made concrete: **the same
path a person would have gone through by hand**, which for a record is
`spaceview.records.save`, the path the form posts to. The date and the task a
model could once ask for went with OneCalendar and OneTask, which are rebuilt
in OneDesk.
"""

import frappe
from frappe import _

from oneapp.oneai.actions import Kind, Refused, register, same

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

	def opened(self, payload: dict, done: dict) -> dict:
		"""The record, on the screen it was changed through.

		Worth having on a change as well as on a create: the card is often
		read in a thread on a different screen from the one it is about, and
		"which quotation was that" is a question the card can answer itself.
		"""
		if not done.get("name"):
			return {}
		return {"label": _("Open it"), "href":
		        f"/one/space/{payload['space']}?screen={payload['screen']}"
		        f"&at=record:{done['name']}"}

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


register(RecordSave())
