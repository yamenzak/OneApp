"""The rules a field carries: when it is asked, and what an answer may be.

`docs/ONEFORMS.md` §14, stage 10. A form that asks everybody everything is a
form most people answer "n/a" to nine times, and branching is the one thing
`bwhtech/forms_pro` is genuinely ahead on. `Web Form Field.depends_on` has been
carrying the answer to the browser since stage 1 and the page has never read it.

**The catch is what `depends_on` actually is.** It is a JavaScript expression —
`eval:doc.status=="Open"` — and Frappe's own renderer evaluates it. That is
precisely what §12 refused for `client_script`: we are not shipping a script
evaluator to a stranger's browser, and "but only an admin can write it" is the
argument that was wrong there too. An admin's own code is still code, running in
somebody else's browser, on a page they opened because they were asked to fill
something in.

So a condition here is a **grammar this module parses**, not an expression
anything evaluates:

    fieldname == "value"      fieldname != "value"
    fieldname == ""           fieldname != ""
    fieldname > 3             fieldname >= 3
    fieldname < 3             fieldname <= 3
    fieldname in "a, b, c"

Parsed on save into `{field, op, value}`, canonicalised back into `depends_on`
so the stored form is still readable by a person and still a Frappe document,
and sent to the page as the tuple. The browser compares; nothing evaluates.

Two consequences worth stating rather than discovering:

* **An `eval:` expression is refused**, so a form imported from a Frappe site
  says so on the way in rather than silently not branching.
* **A condition is a rule, not a drawing.** `hides` is called from the submit
  path as well, because a browser that declined to draw a field is a browser,
  and anybody can post straight to `accept`. `WebForm.validate_submission`
  re-checks `reqd` server-side for the same reason and this joins it.

`max_length` and `max_value` live here rather than in a module of their own, and
that is the same sentence: they are rules a `Web Form Field` carries, nothing
enforces them today, and they have to be checked where a condition is checked
because both are things a browser can be asked to skip. A file's size is the
third of these and is in `attaching.py`, where the bytes are.
"""

import re

import frappe
from frappe import _

#: What one may be written with. Ordered longest-first so `>=` is not read as
#: `>` with a stray `=`.
OPERATORS = (">=", "<=", "==", "!=", "in", ">", "<")

#: The whole grammar, as one expression. A fieldname, an operator, a value —
#: quoted or bare — and nothing else on the line.
RULE = re.compile(
	r"""^\s*
	(?P<field>[a-z_][a-z0-9_]*)\s*
	(?P<op>>=|<=|==|!=|\bin\b|>|<)\s*
	(?P<value>"[^"]*"|'[^']*'|[^\s].*?)
	\s*$""",
	re.X | re.I,
)

#: How many a form may carry. Not a technical limit: a form where forty fields
#: each watch another one is a form nobody can reason about, including the
#: person who built it.
MOST = 60


def parse(said: str) -> dict:
	"""One condition, as `{field, op, value}`, or `{}` for none.

	Refuses rather than ignores. A rule somebody wrote that quietly did nothing
	is worse than no rule, because the form looks like it branches.
	"""
	said = (said or "").strip()
	if not said:
		return {}

	if said.lower().startswith("eval:"):
		frappe.throw(_("A condition here is a comparison rather than code — "
		               "write it as {0}, without the eval:.")
		             .format('status == "Open"'))

	found = RULE.match(said)
	if not found:
		frappe.throw(_("{0} is not a condition this form understands. Write "
		               "one comparison: a field, one of {1}, and a value.")
		             .format(said, ", ".join(OPERATORS)))

	value = found["value"].strip()
	if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
		value = value[1:-1]

	op = found["op"].lower()
	if op in (">", ">=", "<", "<=") and not _numeric(value):
		frappe.throw(_("{0} compares with a number, and {1} is not one.")
		             .format(op, value or '""'))

	return {"field": found["field"], "op": op, "value": value}


def written(rule: dict) -> str:
	"""The canonical text for a parsed rule — what gets stored.

	Round-tripped rather than kept as the reader typed it, so two people who
	wrote the same condition differently end up with the same document and a
	diff of a form says something.
	"""
	if not rule:
		return ""
	if rule["op"] in (">", ">=", "<", "<="):
		return f"{rule['field']} {rule['op']} {rule['value']}"
	return '{} {} "{}"'.format(rule["field"], rule["op"], rule["value"])


def check(said: str, known: set) -> str:
	"""A condition, canonicalised, or a refusal naming what is wrong with it.

	`known` is the fieldnames the form carries. A condition on a field the form
	does not ask for is a field that never changes, so it is a field that is
	hidden for ever — which is the shape of somebody having renamed something
	and not noticed.
	"""
	rule = parse(said)
	if not rule:
		return ""
	if rule["field"] not in known:
		frappe.throw(_("{0} is not a field on this form, so nothing would ever "
		               "make that condition true.").format(rule["field"]))
	return written(rule)


def holds(rule: dict, values: dict) -> bool:
	"""Whether a parsed condition is true of what somebody has filled in.

	The same comparison the browser makes, in the one place that decides — see
	`hides` for why the browser's answer is not the one that counts.
	"""
	if not rule:
		return True

	said = values.get(rule["field"])
	said = "" if said is None else said
	wanted = rule["value"]

	if rule["op"] == "==":
		return _same(said, wanted)
	if rule["op"] == "!=":
		return not _same(said, wanted)
	if rule["op"] == "in":
		return any(_same(said, one.strip()) for one in wanted.split(","))

	left, right = _number(said), _number(wanted)
	if left is None or right is None:
		return False
	return {">": left > right, ">=": left >= right,
	        "<": left < right, "<=": left <= right}[rule["op"]]


def hides(fields: list, values: dict) -> set:
	"""The fieldnames whose condition does not hold, given what was sent.

	Called from the submit path, not only from the page. A field the browser
	declined to draw is a field the browser declined to draw: anybody can post
	straight to `accept`, which is why `validate_submission` re-checks `reqd`
	there, and a condition that only ever ran in a renderer is not a rule.

	One pass rather than a fixed point. A chain — B depends on A, C depends on
	B — resolves anyway because a hidden field carries no value and a condition
	on an empty value is almost always false; and a *cycle* has no answer at
	all, so iterating would only pick one arbitrarily and take longer doing it.
	"""
	out = set()
	for field in fields or []:
		name = (field.get("fieldname") or "").strip()
		if not name:
			continue
		if not holds(parse(field.get("depends_on") or ""), values):
			out.add(name)
	return out


# --------------------------------------------------------------------------- #
# Comparing, which is where a form is not a spreadsheet
# --------------------------------------------------------------------------- #

def _same(said, wanted) -> bool:
	"""Equal, as somebody filling a form in would mean it.

	Case-insensitive and trimmed, because "Yes" and "yes" are the same answer
	and the difference between them is a Select option's capitalisation that
	nobody filling the form in can see. Numbers compare as numbers, so a
	condition written `count == 3` is true of the string "3" the browser sent.
	"""
	left, right = _number(said), _number(wanted)
	if left is not None and right is not None:
		return left == right
	return str(said).strip().casefold() == str(wanted).strip().casefold()


def _numeric(value: str) -> bool:
	return _number(value) is not None


def _number(value):
	"""That, as a number, or nothing. A checkbox arrives as 0/1 and as
	true/false depending on who sent it, and both are numbers here."""
	if isinstance(value, bool):
		return 1 if value else 0
	if isinstance(value, (int, float)):
		return float(value)
	said = str(value or "").strip()
	if said.lower() in ("true", "false"):
		return 1 if said.lower() == "true" else 0
	try:
		return float(said)
	except ValueError:
		return None


# --------------------------------------------------------------------------- #
# What an answer may be
#
# The other two rules a `Web Form Field` has carried since stage 1 and nothing
# has ever read. `WebForm.validate_submission` checks `reqd` and a Data field's
# `options`; it does not look at these, and neither did we, so until now the
# only thing enforcing them was a `maxlength` attribute — which `FormControl`
# does not even take.
# --------------------------------------------------------------------------- #

def within(fields: list, values: dict) -> None:
	"""Refuse an answer longer or larger than the field allows.

	Throws rather than truncates. A form that silently cut somebody's covering
	letter in half would be a form that lost the end of it without telling
	anybody, and the person who would find out is the one reading the record.
	"""
	for field in fields or []:
		name = (field.get("fieldname") or "").strip()
		if not name or name not in values:
			continue
		said = values.get(name)
		if said in (None, ""):
			continue

		longest = int(field.get("max_length") or 0)
		if longest and len(str(said)) > longest:
			frappe.throw(_("{0} is longer than {1} characters.")
			             .format(field.get("label") or name, longest))

		largest = field.get("max_value")
		if largest not in (None, "", 0):
			left, right = _number(said), _number(largest)
			if left is not None and right is not None and left > right:
				frappe.throw(_("{0} is more than {1}.")
				             .format(field.get("label") or name, largest))
