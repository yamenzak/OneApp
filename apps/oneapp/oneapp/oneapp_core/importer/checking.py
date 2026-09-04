"""What a plan would do, before it does any of it.

A fourteen-step field map is a document nobody can read for correctness, and
the mistakes in one are all quiet: a source field renamed since somebody wrote
the map, a target field that does not exist on this site's version, a value
map that covers four of the five values actually in the data, a link resolved
against a step that runs later.

None of those fails loudly. The first three drop a column, the fourth files an
issue per row — and all of them are found after the run, in a report somebody
reads a week later and disbelieves.

So the plan is checked against *both ends* before it is run: the source's own
metadata over the wire, and this site's own metadata locally. It reads
everything and writes nothing, which makes it free to run as often as anybody
likes — and it is what the Check button beside Rehearse does.
"""

import frappe
import json
from .source import fetch, whole
from .mapping import SELF, _lines, explode, maps_children


# How many rows to look at when working out which values a value map has to
# cover. Enough to meet the long tail of a real column, cheap enough to run on
# a button.
SAMPLE = 500


# How many documents a check will read whole looking for one with lines on it.
# Small on purpose: this is the difference between a check that takes a second
# and one that re-reads the source.
LOOK = 8


@frappe.whitelist()
def check(plan: str) -> dict:
	"""Everything wrong with a plan that can be known without running it."""
	doc = frappe.get_doc("Import Plan", plan)
	doc.check_permission("read")
	source = frappe.get_doc("Import Source", doc.source)

	# What each step will have made by the time a later one resolves a link
	# against it. Built as the steps are walked, in their declared order, which
	# is exactly the order the run walks them in.
	made = set()
	# The names each source doctype's sample held, so a second step off the
	# same doctype can be asked the only question worth asking about it: do
	# these two steps claim the same rows?
	seen: dict[str, set] = {}
	found = []

	for step in doc.steps:
		if not step.enabled:
			made.add(step.source_doctype)
			continue
		found.append(_check_step(source, doc, step, made, seen))
		made.add(step.source_doctype)

	return {
		"plan": plan,
		"steps": found,
		"problems": sum(len(s["problems"]) for s in found),
		"warnings": sum(len(s["warnings"]) for s in found),
	}


def _check_step(source, plan, step, made: set, seen: dict | None = None) -> dict:
	"""One step, against the source's schema and this site's."""
	problems, warnings = [], []

	try:
		field_map = json.loads(step.field_map or "{}")
	except ValueError as raised:
		return {"source_doctype": step.source_doctype, "target_doctype": step.target_doctype,
		        "problems": [f"the field map is not JSON: {raised}"], "warnings": [],
		        "source_rows": None}

	seen = seen if seen is not None else {}

	try:
		filters = json.loads(step.filters or "[]")
	except ValueError as raised:
		return {"source_doctype": step.source_doctype, "target_doctype": step.target_doctype,
		        "problems": [f"the filters are not JSON: {raised}"], "warnings": [],
		        "source_rows": None}

	theirs, rows = _their_fields(source, step.source_doctype, filters, problems)
	ours = _our_fields(step.target_doctype, problems)

	# One whole document, where the map reads child rows. The list endpoint
	# does not answer them, so without this every `rows` rule would be checked
	# against a row that cannot have them and reported missing — and the field
	# names inside the lines would never be checked at all.
	if rows and maps_children(field_map):
		try:
			rows[0] = _one_with_lines(source, step, rows, field_map)
			theirs = set(rows[0])
		except Exception as raised:
			problems.append(f"could not read one whole {step.source_doctype}: {raised}")

	# Two steps off one source doctype is ordinary — a party table holding both
	# customers and suppliers is the usual reason — and fine while their
	# filters are disjoint. Where they are not it is quietly wrong: `resolve`
	# is keyed on the source doctype alone, so a row caught by both resolves to
	# whichever step ran last, and `_remember` then refuses the row mid-run.
	# Which is why this asks the rows rather than the schema.
	#
	# Keyed by target as well, because two steps into the *same* target are a
	# second pass rather than an ambiguity: a project's parent is another
	# project, so the link cannot resolve until every project exists, and the
	# only honest way to write that is to go round twice.
	names = {row.get("name") for row in (rows or [])} - {None}
	both = sorted(names & seen.get((step.source_doctype, step.target_doctype), set()))
	if both:
		warnings.append(
			f"{len(both)} row(s) of {step.source_doctype} are claimed by an earlier step "
			f"too — {', '.join(both[:3])}. Narrow one step's filters; a row cannot "
			"become two things."
		)
	key = (step.source_doctype, step.target_doctype)
	seen[key] = names | seen.get(key, set())

	# A fan-out changes what the field map may name, so it is read first: the
	# fields inside one piece are not fields of the source doctype, and
	# checking the map against the parent's columns alone would report every
	# one of them missing.
	fan_out, pieces = _check_fan_out(step, rows, theirs, problems)
	if fan_out and pieces:
		theirs = set(pieces[0][1])

	for target, rule in field_map.items():
		if not isinstance(rule, dict):
			rule = {"from": rule}

		if ours is not None and target not in ours:
			problems.append(f"{step.target_doctype} has no field `{target}`")

		if "const" in rule:
			continue

		if "rows" in rule:
			# The list itself, and then the fields inside one of its lines.
			# Checking only that the list is there would pass a map naming
			# `unit_price` on a table whose column is `rate`, which is every
			# line silently blank.
			if (theirs is not None and rule["rows"] != SELF
					and rule["rows"] not in theirs):
				problems.append(f"`{target}` reads `{rule['rows']}`, which is not there")
				continue
			lines = _lines(rows[0], rule["rows"]) if rows else []
			if not lines:
				warnings.append(
					f"`{target}` reads `{rule['rows']}`, and the row checked has no lines "
					"in it — the fields inside are unchecked"
				)
				continue
			for inner, said in (rule.get("map") or {}).items():
				if isinstance(said, dict) and ("const" in said or "rows" in said):
					continue
				field = said.get("from") if isinstance(said, dict) else said
				if field and field not in lines[0]:
					problems.append(
						f"`{target}.{inner}` reads `{field}`, which is not on a line"
					)
			continue

		if "when" in rule:
			for field, _said in rule["when"]:
				if theirs is not None and field not in theirs:
					problems.append(f"`{target}` asks about `{field}`, which is not there")
			continue

		said = rule.get("from")
		if not said:
			problems.append(f"`{target}` names no source field and no constant")
			continue
		if theirs is not None and said not in theirs:
			problems.append(f"{step.source_doctype} has no field `{said}`")

		if rule.get("link") and rule["link"] not in made:
			# Not a warning. A link resolved before its step has run finds
			# nothing on every row, and the run files one issue per record
			# rather than saying the plan is in the wrong order.
			problems.append(
				f"`{target}` resolves against {rule['link']}, which this plan "
				"runs later or not at all"
			)

		# The quiet one: a value map that covers what somebody remembered rather
		# than what is in the column. A warning and not a problem, because
		# `default` may be exactly the intent.
		if "values" in rule and rows:
			unseen = sorted({
				str(row.get(said)) for row in rows
				if row.get(said) not in (None, "") and row.get(said) not in rule["values"]
			})
			if unseen and "default" not in rule:
				warnings.append(
					f"`{said}` also holds {', '.join(unseen[:6])} — "
					"unmapped and with no default, so they cross over as-is"
				)

	return {
		"source_doctype": step.source_doctype,
		"target_doctype": step.target_doctype,
		"problems": problems,
		"warnings": warnings,
		"source_rows": len(rows) if rows is not None else None,
	}


def _one_with_lines(source, step, rows: list, field_map: dict) -> dict:
	"""A whole document out of the sample, preferring one that has lines on it.

	The first row is the obvious one to read and often the wrong one: their
	oldest purchase order has no items on it at all, and checking against that
	one says nothing about the map and warns about the data. So a few are tried
	and the first with lines wins — `LOOK` of them, because this is a check and
	not a second import.
	"""
	tables = [rule["rows"] for rule in field_map.values()
	          if isinstance(rule, dict) and rule.get("rows") not in (None, SELF)]
	first = None

	for row in rows[:LOOK]:
		found = {**row, **whole(source, step.source_doctype, row.get("name"))}
		first = first if first is not None else found
		if any(found.get(table) for table in tables):
			return found

	return first if first is not None else rows[0]


def _check_fan_out(step, rows, theirs, problems: list):
	"""The `fan_out` rule, and one real row put through it.

	Exploding a sample is the only honest check: the rule names a field holding
	JSON, and whether that JSON is the shape it claims cannot be known from a
	schema. A step that says `map` over a column holding an array fails on every
	row, and this is where that is cheap to find out.
	"""
	if not step.fan_out:
		return None, None

	try:
		rule = json.loads(step.fan_out)
	except ValueError as raised:
		problems.append(f"the fan-out is not JSON: {raised}")
		return None, None

	if theirs is not None and rule.get("from") not in theirs:
		problems.append(f"the fan-out reads `{rule.get('from')}`, which is not there")
		return rule, None

	if not rows:
		return rule, None

	try:
		pieces = explode(rows[0], rule)
	except Exception as raised:
		problems.append(f"the fan-out does not fit the data: {raised}")
		return rule, None

	if not pieces:
		problems.append(f"the first row's `{rule.get('from')}` is empty, so nothing fans out")
	return rule, pieces


def _their_fields(source, doctype: str, filters: list, problems: list):
	"""The source's own column names, and a sample of its rows.

	Read off the data rather than off `DocType`/`DocField`: an API user is not
	always allowed to read the schema tables, and every row already carries
	every fieldname. It also means what is checked is what will actually
	arrive.

	Sampled through the step's own filters, for the same reason: a value the
	step excludes is not a value it has to map, and reporting it is how a check
	teaches people to stop reading its output.
	"""
	try:
		rows = fetch(source, doctype, filters, 0, SAMPLE)
	except Exception as raised:
		problems.append(f"could not read {doctype} from the source: {raised}")
		return None, None

	if not rows:
		problems.append(f"{doctype} has no rows on the source matching this step")
		return None, []

	return set(rows[0]), rows


def _our_fields(doctype: str, problems: list):
	"""This site's own column names for the target, or None if it is absent."""
	if not frappe.db.exists("DocType", doctype):
		problems.append(f"{doctype} is not installed on this site")
		return None

	meta = frappe.get_meta(doctype)
	return {df.fieldname for df in meta.fields} | {
		"name", "owner", "creation", "modified", "docstatus", "naming_series",
	}
