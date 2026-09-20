"""A screen narrowed to whoever is reading it.

Half the screens in an HR product have two readers. Leave is a queue to the
person who approves it and a form to the person who files it; a payslip is a
run to payroll and a number to everybody else. `docs/HORILLA.md` §3.1 is that
finding read off a competitor, which answers it by putting **My leave** beside
**Leave** in the same rail — one product, two audiences, and the difference
between them is one word at the front of a label.

The cheap way to do that is a component screen per audience, and it is the
wrong way: a second screen is a second set of columns, view types, dashboard
widgets and states to keep in step with the first, and they will not stay in
step. The expensive way is an inheritance mechanism in the manifest, which is a
language nobody asked for.

So it is neither. A twin is an ordinary screen declaration — a manifest is a
Python file, so `dict(LEAVE, screen="my-leave", …)` is the whole of the reuse —
and the only thing the engine has to learn is a **filter value that means the
reader**:

    "filters": {"employee": "@me:employee"}
    "filters": {"opportunity_owner": "@me"}

`@me` is the session's user. `@me:<kind>` is somebody the user *is* in some
other app's terms, and the engine does not know what those are: OneHR's is an
Employee, found through `user_id`, and this module has never heard of HRMS. An
app that has one registers it:

    onespace_subjects = {"employee": "oneapp.onehr.own.employee_of"}

**An unresolvable subject narrows to nothing, and that is the whole safety
property.** A reader whose login was never linked to an employee record must
see an empty My leave, never everybody's — so the sentinel is replaced with a
value nothing can equal rather than dropped from the filter. Dropping it is the
one mistake here that is silent, reads as a working screen, and shows one
person the company's pay.

Resolved once, in `spaceview/resolve.py`, before anything downstream reads
`filters` — so the list, the board, the calendar, the dashboard widgets and the
count all narrow the same way and cannot disagree about whose rows these are.
"""

import frappe

#: What a filter value says when it means the reader. `@me` on its own is the
#: session's user; `@me:employee` is whoever this user is in some app's terms.
ME = "@me"
KIND = ":"

#: The hook an app registers a subject kind under. A dict of kind → dotted path
#: to a function taking no arguments and returning an id or an empty string.
HOOK = "onespace_subjects"

#: What an unresolvable subject becomes.
#:
#: A value no row can hold, rather than no filter at all. The distinction is the
#: entire point of this module: a screen narrowed to a reader the site cannot
#: identify has to be *empty*, and the failure mode of dropping the clause is a
#: screen that looks like it is working while it shows everybody everything.
#:
#: A name Frappe could never have written: it is longer than the `name` column
#: and carries characters no autoname produces.
NOBODY = "\x00-onespace-no-such-subject-\x00"


def wanted(value) -> bool:
	"""Whether a filter value is asking for the reader."""
	return isinstance(value, str) and value.strip().startswith(ME)


def subject(value) -> str:
	"""One `@me` sentinel, as an id — or `NOBODY`.

	`@me` is `frappe.session.user`, which every site has. `@me:kind` is asked of
	whichever app registered that kind, and a kind nobody registered, a provider
	that raises, and a provider that answers "nobody" are all the same answer
	here: this reader is not one of those, so nothing is theirs.
	"""
	asked = str(value).strip()
	if asked == ME:
		return frappe.session.user or NOBODY

	kind = asked[len(ME) + len(KIND):] if asked.startswith(ME + KIND) else ""
	if not kind:
		return NOBODY

	path = (frappe.get_hooks(HOOK) or {}).get(kind)
	# `get_hooks` returns every app's answer as a list, newest last. One kind
	# has one meaning per site; if two apps claim it, the last installed wins,
	# which is the same rule the rest of the hook system uses.
	if isinstance(path, (list, tuple)):
		path = path[-1] if path else ""
	if not path:
		return NOBODY

	try:
		return frappe.get_attr(path)() or NOBODY
	except Exception:
		# Logged rather than raised. This runs behind every read of a screen,
		# and an app whose provider is broken should narrow its own twin to
		# nothing rather than take the workspace down.
		frappe.log_error(title="One subject provider failed", message=path)
		return NOBODY


#: The operators that mean "contains", where a column holds several values.
#:
#: Frappe stores an assignment as a JSON array in `_assign`, so "assigned to
#: me" is `_assign like %somebody%` and there is no other spelling — the column
#: is not a Link and cannot be compared for equality. A manifest says
#: `{"_assign": ["like", "@me"]}` and this is what puts the wildcards on, so
#: the sentinel stays one word rather than a pattern somebody has to remember
#: to write around it.
CONTAINS = ("like", "not like")


def _as(operator, value: str) -> str:
	"""The resolved subject, in the shape that operator needs."""
	if str(operator).strip().lower() in CONTAINS and value:
		return f"%{value}%"
	return value


def resolve(filters) -> dict:
	"""A screen's declared filters, with every `@me` in them replaced.

	Values arrive two ways, because `_all_filters` reads them two ways: a bare
	value is an equality, and a `[operator, value]` pair is anything else. Both
	are rewritten, so `["in", "@me"]` is as honest as `"@me"` — and neither is
	left as the literal string, which would be a filter matching the four
	characters somebody typed.
	"""
	if not isinstance(filters, dict):
		return filters if isinstance(filters, dict) else {}

	found = {}
	for field, value in filters.items():
		if isinstance(value, (list, tuple)) and len(value) == 2 and wanted(value[1]):
			found[field] = [value[0], _as(value[0], subject(value[1]))]
		elif wanted(value):
			found[field] = subject(value)
		else:
			found[field] = value
	return found
