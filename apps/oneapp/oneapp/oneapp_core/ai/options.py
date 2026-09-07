"""What else a model takes, beyond the thing it is being asked to do.

A model that reads text aloud has a language and a pace; one that draws has a
size and a number of steps. None of that belongs on the *feature* — "read this
aloud" is the same feature whichever model does it — and none of it belongs in
our code either, because the list of voices a provider offers is the provider's
to change and ours to relay.

So a model **declares** its options and the workspace **answers** them. The
declaration arrives with the catalogue, from the control plane, which is the
only place that talks to a provider. The answer is stored beside the workspace's
choice of model, and is only ever read back through the declaration — which is
what makes an option that has gone away stop being offered and stop being sent,
without anything having to migrate.

Four types, and no more until something needs a fifth: a `select` for a list the
provider fixes, a `number` for a dial with ends, a `switch` for something on or
off, and `text` for the one case none of those fit — an image model's negative
prompt. Anything richer than that is a feature, not a setting.
"""

import json

import frappe
from frappe import _

TYPES = ("select", "number", "switch", "text")

#: The longest a `text` answer may be. Prose that reaches a provider on every
#: call, so it is bounded here for the same reason the prompt addendum is.
MAX_TEXT = 500


def declared(model: dict | None) -> list[dict]:
	"""What this model says it takes, defensively.

	The catalogue is cached JSON written by a sync, so a row that is the wrong
	shape is a possibility rather than a bug to assert against: it means an
	older control plane, or a newer one. An option that cannot be read is
	dropped rather than raised on, because the alternative is a settings page
	that will not render.
	"""
	rows = (model or {}).get("options")
	if not isinstance(rows, list):
		return []

	out = []
	for row in rows:
		if not isinstance(row, dict):
			continue
		key, kind = str(row.get("key") or ""), str(row.get("type") or "")
		if not key or kind not in TYPES:
			continue
		option = {
			"key": key,
			"label": str(row.get("label") or key),
			"type": kind,
			"help": str(row.get("help") or ""),
			"default": row.get("default"),
		}
		if kind == "select":
			option["options"] = _choices(row.get("options"))
			if not option["options"]:
				continue
		if kind == "number":
			option["min"] = _number(row.get("min"))
			option["max"] = _number(row.get("max"))
		out.append(option)
	return out


def _choices(rows) -> list[dict]:
	if not isinstance(rows, list):
		return []
	return [
		{"value": str(row["value"]), "label": str(row.get("label") or row["value"])}
		for row in rows
		if isinstance(row, dict) and row.get("value") is not None
	]


def _number(value):
	try:
		return float(value)
	except (TypeError, ValueError):
		return None


def stored(row) -> dict:
	"""The answers as they were saved, without reading them as anything yet."""
	if not row:
		return {}
	try:
		answers = json.loads(row.model_options or "{}")
	except (TypeError, ValueError):
		return {}
	return answers if isinstance(answers, dict) else {}


def answered(row, model: dict | None) -> dict:
	"""The workspace's answers, narrowed to what this model still declares.

	Narrowed rather than migrated: changing the model is how a workspace stops
	using a model's options, and an answer for an option the new model does not
	have is not an answer to anything. It stays in the row — nothing deletes
	it — so changing back is not a re-typing exercise.
	"""
	answers = stored(row)
	return {
		option["key"]: answers[option["key"]]
		for option in declared(model)
		if option["key"] in answers
	}


def resolved(row, model: dict | None) -> dict:
	"""What to send: the model's own defaults, with the workspace's over them.

	This is the one a caller wants. An option nobody answered is not left out —
	it is sent as the model said it should be — so a provider never has to guess
	and the answer does not change when a workspace opens the settings page and
	saves it unchanged.
	"""
	out = {}
	for option in declared(model):
		if option.get("default") is not None:
			out[option["key"]] = option["default"]
	out.update(answered(row, model))
	return out


def checked(answers: dict, model: dict | None) -> dict:
	"""Validate what came back from a browser, or refuse it.

	Refuses rather than silently corrects. A value outside a model's range is
	either a stale page or somebody calling the endpoint directly, and both are
	better answered with a sentence than with a number the workspace did not
	choose and cannot see.
	"""
	if not isinstance(answers, dict):
		return {}

	rules = {option["key"]: option for option in declared(model)}
	out = {}
	for key, value in answers.items():
		option = rules.get(key)
		# An unknown key is dropped and not refused: a page open while an
		# operator retires an option would otherwise be unable to save at all.
		if not option:
			continue
		# And an empty answer is not an answer. It is how the panel says "use
		# whatever the model's own default is", which is a thing to *stop*
		# storing rather than a value to store — see `keys` and its caller.
		if value is None or value == "":
			continue
		out[key] = _one(option, value)
	return out


def keys(model: dict | None) -> set[str]:
	"""Which options this model declares, by key.

	What a save has to clear before writing what came back: the answers for
	*this* model are wholly replaced, and the answers for every other model the
	workspace has looked at are left alone.
	"""
	return {option["key"] for option in declared(model)}


def _one(option: dict, value):
	kind = option["type"]

	if kind == "select":
		allowed = [choice["value"] for choice in option["options"]]
		if str(value) not in allowed:
			frappe.throw(
				_("{0} is not a {1} this model offers.").format(value, option["label"])
			)
		return str(value)

	if kind == "number":
		number = _number(value)
		if number is None:
			frappe.throw(_("{0} has to be a number.").format(option["label"]))
		low, high = option.get("min"), option.get("max")
		if (low is not None and number < low) or (high is not None and number > high):
			frappe.throw(
				_("{0} has to be between {1} and {2}.").format(
					option["label"], low, high
				)
			)
		return number

	if kind == "switch":
		return bool(value)

	return str(value or "")[:MAX_TEXT]
