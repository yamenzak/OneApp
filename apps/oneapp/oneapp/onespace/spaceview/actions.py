"""Actions a space declares for one of its screens.

A screen can list, open and edit. What it could not do is *act* — replay a
webhook, adopt a plan's terms, open the bespoke screen that belongs to this
record — and every one of those used to live in a hand-written console page.
Retiring those pages without this would have left a handful of things doable
only in the desk, which is the one place this product does not go.

Declared in code rather than stored on the Space, and the difference matters:
an action names a method somebody can invoke, so the list of them is not
something an operator should be able to extend by editing a row. A provider
is a Python function behind a hook, shipped by an app, reviewed like code.
"""

import frappe


# What an action may say about itself. Anything else is dropped rather than
# passed through: this shape ends up as a button that calls a method, and a
# provider is not a place to smuggle extra arguments in.
ACTION_FIELDS = ("key", "label", "icon", "scope", "method", "screen", "param",
                 "confirm", "upload")


#: How many records a verb takes — **not** where its button goes.
#:
#: It used to be the second thing, and that was the bug. `record` put an action
#: on the open record and `selection` put it in the bar a tick raises, so every
#: action was reachable from exactly one of the two places and the author of
#: the declaration chose which. In practice that meant you could not fetch the
#: source you had open, could not hold the tenant you were reading, and could
#: not accept the stop on your screen — and finding any button meant knowing
#: which half of the split it had landed in.
#:
#: Now every action is offered in both places and this says only whether it may
#: run against more than one row at a time. A `one` action is still offered in
#: the selection bar; it is simply disabled until exactly one row is ticked,
#: which keeps the verb where somebody looks for it and says why it is not
#: available rather than hiding it.
ACTION_SCOPES = ("one", "many")

#: What the two old words meant, so a declaration written before this still
#: resolves. `record` was "one at a time" and `selection` was "a batch".
LEGACY_SCOPES = {"record": "one", "selection": "many"}


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
	scope = LEGACY_SCOPES.get(row.get("scope"), row.get("scope"))
	action["scope"] = scope if scope in ACTION_SCOPES else "one"
	# Which query parameter the target screen reads the record's name from. Only
	# meaningful for a screen action, and given a name here so the frontend does
	# not have to invent one.
	if action.get("screen"):
		action["param"] = row.get("param") or "record"
		# Navigation is one record by construction: there is one address bar,
		# and opening a screen "with these five" is not a thing it can mean.
		action["scope"] = "one"
		# Navigation cannot carry a file, so the flag is meaningless here and
		# dropping it is better than rendering a picker that goes nowhere.
		action.pop("upload", None)
	elif action.get("upload"):
		# The action needs a file before it can run: the button opens a picker,
		# the file becomes a private `File`, and its url is the one extra
		# argument `run.run_action` will pass. Everything else about the action
		# is unchanged, which is the point — an upload is a *modifier* on a
		# method action rather than a third kind of action with its own path.
		action["upload"] = True
	return action
