"""Turning one site's row into this one's, and saying what it could not."""

import frappe
import re
from copy import deepcopy
from frappe import _


class Unresolved(Exception):
	"""A link that pointed at something no step has made yet.

	Its own exception because it is not a bad row — it is a plan whose steps are
	in the wrong order, and the row is fine and will import once they are not.
	The message says which link, because that is the whole diagnosis.
	"""


def build(row: dict, field_map: dict, plan: str) -> dict:
	"""One source row as the values of one target record.

	Every rule is explicit. There is deliberately no "copy anything whose name
	matches": two systems that happen to share a fieldname mean the same thing
	about a third of the time, and the third that do not are the ones nobody
	notices until the numbers are wrong.
	"""
	values = {}

	for target, rule in (field_map or {}).items():
		if not isinstance(rule, dict):
			# The short form, because `{"customer_name": "party"}` is what
			# somebody writes first and refusing it teaches nothing.
			rule = {"from": rule}

		if "const" in rule:
			# Copied, not shared. A constant that is a list of child rows would
			# otherwise be the same objects on every record the run makes, and
			# whatever the first document's controller wrote into them would be
			# what the second one started from.
			said = rule["const"]
			values[target] = deepcopy(said) if isinstance(said, list | dict) else said
			continue

		if "rows" in rule:
			# A child table. The target's own rows, built out of a list on the
			# source with a field map of their own — the same four rule shapes,
			# because a line on an invoice is a record like any other and
			# nothing about it wants a second vocabulary.
			values[target] = [
				build(one, rule.get("map") or {}, plan)
				for one in _lines(row, rule["rows"])
			]
			continue

		if "when" in rule:
			# The first of these fields that is true gives its value. For the
			# columns a bespoke system keeps as three booleans where a real one
			# keeps a status — present, late, absent — which cannot be a `from`
			# because the answer is not in any one of them.
			values[target] = next(
				(said for field, said in rule["when"] if row.get(field)),
				rule.get("default"),
			)
			continue

		said = row.get(rule.get("from"))

		if "pick" in rule:
			# One entry out of a list the old system denormalised onto the row.
			# Their project carries every party on it — client, consultant, four
			# suppliers — as JSON with a `type` on each, and the customer is
			# whichever one says Client. Without this the field is unreachable:
			# it is not a column and it is not a child table.
			said = _pick(said, rule["pick"], rule.get("take"))

		if rule.get("link"):
			if said in (None, ""):
				continue
			found = resolve(plan, rule["link"], said)
			if not found:
				raise Unresolved(
					f"{target}: nothing here yet for {rule['link']} {said}. "
					"Run that step first, or move it earlier in the plan."
				)
			values[target] = found
			continue

		if rule.get("number"):
			# What somebody typed, as a number. Their widths are strings —
			# `"200.0 cm"` — because the old form had one box and no unit, and
			# a system that keeps a measurement as prose cannot add two of
			# them. Deliberately narrow: the leading number, or nothing.
			said = _number(said)

		if "values" in rule:
			said = rule["values"].get(said, rule.get("default", said))

		# A second field to try before giving up. For the columns a bespoke
		# system left optional that this one requires: two of their employees
		# have no joining date, and the date the record was made is wrong by
		# however long the old system lagged and is the only date there is.
		if said in (None, "") and "default_from" in rule:
			said = row.get(rule["default_from"])

		if said in (None, "") and "default" in rule:
			said = rule["default"]

		if rule.get("into"):
			# A small closed vocabulary the old system kept as free text and
			# this one keeps as records: fourteen job titles, two emirates,
			# three branches. Deliberately per-rule and not a default — the
			# same mechanism pointed at a quotation's line codes would invent
			# an item master out of a year of typing.
			if said in (None, ""):
				continue
			said = vocabulary(rule["into"], said, rule.get("with"))

		values[target] = said

	return values


def vocabulary(doctype: str, said, extra: dict | None = None) -> str:
	"""One record of a small vocabulary, made if it is not there.

	Named by the field the doctype names itself after, which is what makes this
	answerable at all: Designation is `field:designation_name`, Territory is
	`field:territory_name`, and a doctype named any other way is not a
	vocabulary and does not belong behind this rule.

	Inserted as the operator, like everything else the engine writes: an import
	that could create what its operator cannot is a way around every permission
	on the site.
	"""
	if frappe.db.exists(doctype, said):
		return said

	named = frappe.get_meta(doctype).autoname or ""
	if not named.startswith("field:"):
		frappe.throw(_("{0} is not named after a field, so it cannot be filled in "
		               "from a value.").format(doctype))

	doc = frappe.get_doc({"doctype": doctype, **(extra or {}),
	                      named.split(":", 1)[1]: said}).insert()
	return doc.name


# A `rows` rule that says this rather than a fieldname builds one child row out
# of the parent. For a document whose amount is a header field because it was
# never itemised — a progress invoice is one number against a contract — and
# which the target doctype nonetheless requires a line for.
SELF = "__self"


def _lines(row: dict, rows: str) -> list[dict]:
	return [row] if rows == SELF else (row.get(rows) or [])


def maps_children(field_map: dict) -> bool:
	"""Whether anything in this map reads a child table off the source.

	`__self` is not one: it builds a row out of the parent, which the list
	endpoint already answered, so a step that only does that does not need the
	second read per row.
	"""
	return any(
		isinstance(rule, dict) and rule.get("rows") not in (None, SELF)
		for rule in (field_map or {}).values()
	)


def _pick(said, matching: dict, take: str | None):
	"""The first item of a list that matches, or nothing.

	Nothing rather than the first item: a project with no consultant on it has
	no consultant, and handing back whoever happened to be listed first is how
	a migration invents relationships.
	"""
	if said in (None, ""):
		return None

	held = frappe.parse_json(said)
	if not isinstance(held, list):
		raise ValueError("`pick` needs a list, and this is not one")

	found = next(
		(one for one in held
		 if isinstance(one, dict)
		 and all(one.get(key) == value for key, value in (matching or {}).items())),
		None,
	)
	if found is None:
		return None
	return found.get(take) if take else found


def _number(said):
	"""The leading number in whatever this is, or None."""
	if said in (None, ""):
		return None
	if isinstance(said, int | float):
		return said
	found = re.search(r"-?\d+(?:\.\d+)?", str(said))
	return float(found.group()) if found else None


def explode(row: dict, rule: dict | None) -> list[tuple[str, dict]]:
	"""One source row as the several target rows it actually is.

	Answers `[(key, row)]` either way, so the caller has one loop and not two:
	a step with no `fan_out` is one piece keyed by the row's own name, which is
	exactly the identity it had before this existed.

	A piece's key is the row's name *and* the piece's own, because neither
	alone identifies it. Keyed on the piece alone, a month of attendance keyed
	by employee is one record per employee overwritten once a day: 20,229 rows
	read and 71 kept, and the run reports twenty thousand updates as if that
	were the point of them.

	The piece's own fields are merged *over* the parent's rather than under
	them. A day's row carries `name`, `date` and `modified`; an employee's entry
	inside it carries `present` and `overtime`. Where both name something, the
	inner one is the more specific and wins.
	"""
	if not rule:
		return [(str(row.get("name")), row)]

	held = row.get(rule.get("from"))
	if held in (None, ""):
		return []

	held = frappe.parse_json(held)

	if rule.get("shape") == "list":
		if not isinstance(held, list):
			raise ValueError(f"`{rule['from']}` is not a list")
		# Keyed by position, because a list has no other stable name — and a
		# stable name is what makes a second run an update.
		return [
			(f"{row.get('name')}:{at}",
			 {**row, **(one if isinstance(one, dict) else {"value": one}),
			  "__key": str(at)})
			for at, one in enumerate(held)
		]

	if not isinstance(held, dict):
		raise ValueError(f"`{rule['from']}` is not an object")

	return [
		(f"{row.get('name')}:{key}",
		 {**row, **(one if isinstance(one, dict) else {"value": one}),
		  "__key": str(key)})
		for key, one in held.items()
	]


def resolve(plan: str, source_doctype: str, source_name: str) -> str:
	"""What this plan made of one source row, or nothing.

	The whole of link resolution, and the reason it is a table rather than a
	naming convention: a source row named by hash whose target is named after a
	field has no other way back to itself.
	"""
	return frappe.db.get_value(
		"Import Identity",
		{"plan": plan, "source_doctype": source_doctype, "source_name": source_name},
		"target_name",
	)
