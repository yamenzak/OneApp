"""Where the question was asked from, and what that is allowed to change.

Opened from the rail, the assistant answers about the whole workspace. Opened
beside a quotation it should answer about *that* quotation — "is this priced
above the last one?" ought to work without anybody retyping which one.

Two things make that happen and they are different in kind.

The **space** is bound onto the tools. `Tool.bind` fills it in and takes it out
of the schema, so a chat opened in RUA is about RUA and the model has no word
for anywhere else.

The screen and the record are **told**, not bound: one sentence appended to the
system prompt for this run, naming them in the workspace's own words, so the
model knows what "this one" means.

The screen was bound too, for a while, and it was wrong. Pinning it reads as
safety and is not — permissions are the boundary, and a bound argument only
decides what the model can *name*. What it actually cost was answers: on a
project, "is there a quotation for this?" is an ordinary question and a pinned
screen makes it unanswerable. So the binding narrows to the space, which is a
real boundary in the product, and focus is left to the sentence.

Both are checked here first, through the same resolver a click goes through: a
space this reader cannot open throws, and a record that is not on the screen it
claims to be on is dropped. Context arrives from a browser, so it is an answer
to be verified rather than a premise.
"""

import frappe

#: The fields a browser may send. Anything else is ignored rather than refused:
#: a stale URL carrying something we no longer read should still open a chat.
FIELDS = ("space", "screen", "docname")


def read(on) -> dict:
	"""What the reader actually has open, out of what the browser claimed.

	Returns `{}` where there is nothing usable, which is the ordinary case —
	the assistant opened from the rail is not looking at anything.
	"""
	if isinstance(on, str):
		on = frappe.parse_json(on or "null")
	if not isinstance(on, dict):
		return {}

	space = str(on.get("space") or "").strip()
	screen = str(on.get("screen") or "").strip()
	if not space or not screen:
		return {}

	from oneapp.onespace.spaceview.resolve import _resolve

	# Throws for a space this reader may not open, which is the same refusal the
	# browser would get, and is right: a chat opened against something you
	# cannot see is not a chat to quietly widen.
	resolved = _resolve(space, screen)
	if not resolved.get("doctype") or resolved.get("screen") != screen:
		return {}

	found = {
		"space": space,
		"screen": screen,
		"space_label": resolved.get("label") or space,
		"screen_label": resolved.get("screen_label") or screen,
		"singular": resolved.get("singular") or "record",
	}

	docname = str(on.get("docname") or "").strip()
	if docname:
		from oneapp.onespace.spaceview.records import record

		# By the screen's own rules rather than `get_doc`: a record this screen
		# would not list is not one it may name here either.
		row = record(space_code=space, screen=screen, name=docname)
		if row:
			found["docname"] = docname
			found["title"] = _title(resolved, row, docname)

	return found


def bound(toolbox: list, on: dict) -> list:
	"""The same tools, narrowed to the space that is open.

	Only onto the ones that take a space — `search_files` and `read_document`
	are about the Drive, which has no space, and binding an argument a tool does
	not declare is a TypeError a turn later.

	`list_spaces` goes: with one bound there is nothing for it to answer, and a
	tool that lists places its caller cannot then reach is an invitation to
	spend a turn finding that out.
	"""
	if not on.get("space"):
		return toolbox

	return [
		one.bind(space=on["space"]) if one.takes("space") else one
		for one in toolbox
		if one.name != "list_spaces"
	]


def note(on: dict) -> str:
	"""One sentence saying where this was asked from, for the system prompt.

	In the workspace's words rather than in codes: the reader sees "Quotations"
	and so should the answer. The codes are already bound onto the tools, which
	is where a machine name belongs.
	"""
	if not on.get("space"):
		return ""

	where = f'the {on["screen_label"]} screen of {on["space_label"]}'
	pinned = (
		f'Every tool you have is already scoped to {on["space_label"]}, and you '
		"cannot reach another space from here. You can still look at any screen "
		f"in {on['space_label']} — say which one you are looking at."
	)

	if on.get("docname"):
		return (
			f'The person asking has {on["title"]} open — one {on["singular"]} on '
			f'{where}. Read "this", "it" and "here" as that one unless they say '
			f"otherwise. {pinned}"
		)
	return (
		f'The person asking has {where} open. Read "this" and "here" as that '
		f"screen. {pinned}"
	)


def _title(resolved: dict, row: dict, docname: str) -> str:
	"""What the record is called on screen, falling back to its id.

	The screen's title column, because that is the words the reader is looking
	at. An id is a fair answer where there is no title — it is what the trail
	shows there too.
	"""
	field = (resolved.get("title_field") or "").strip()
	said = str(row.get(field) or "").strip() if field else ""
	return f"{said} ({docname})" if said and said != docname else docname
