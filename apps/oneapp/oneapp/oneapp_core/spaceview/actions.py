"""Actions a space declares for one of its screens."""

import frappe


# What an action may say about itself. Anything else is dropped rather than
# passed through: this shape ends up as a button that calls a method, and a
# provider is not a place to smuggle extra arguments in.
ACTION_FIELDS = ("key", "label", "icon", "scope", "method", "screen", "param", "confirm")


# `record` puts the action on the open record. `selection` puts it in the bar a
# selection raises, where it is handed every chosen row.
ACTION_SCOPES = ("record", "selection")


def actions(space_code: str, screen: str) -> list[dict]:
	"""The actions declared for one screen, keyed `space_code/screen`.

	Merged from every provider, in install order, and normalised here so that
	the payload the frontend sees and the allowlist `run_action` checks against
	are the same list built by the same code.
	"""
	found = []
	for path in frappe.get_hooks("onespace_screen_actions") or []:
		try:
			declared = frappe.get_attr(path)() or {}
		except Exception:
			# One app's provider failing must not take out a screen. Logged
			# rather than raised, exactly as the space providers are.
			frappe.log_error(title="OneSpace action provider failed", message=path)
			continue
		for row in declared.get(f"{space_code}/{screen}") or []:
			action = _action(row)
			if action:
				found.append(action)
	return found


def _action(row: dict) -> dict | None:
	"""One declared action, narrowed to what an action may be.

	An action either calls a method or opens a screen, never both and never
	neither — "a button that does nothing" is not a state worth rendering, and a
	row that means to do both is a provider bug worth failing loudly at the one
	place that can see it.
	"""
	if not row.get("key") or not row.get("label"):
		return None
	if bool(row.get("method")) == bool(row.get("screen")):
		return None

	action = {name: row.get(name) for name in ACTION_FIELDS if row.get(name) is not None}
	action["scope"] = row.get("scope") if row.get("scope") in ACTION_SCOPES else "record"
	# Which query parameter the target screen reads the record's name from. Only
	# meaningful for a screen action, and given a name here so the frontend does
	# not have to invent one.
	if action.get("screen"):
		action["param"] = row.get("param") or "record"
	return action
