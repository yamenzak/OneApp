"""What the workspace assistant may look at, and how it is stopped.

Every tool here is a thin wrapper over an endpoint the SPA already calls, and
that is the whole design. `spaceview.records.rows` decides which spaces a person
may open, which screens they may see, which fields those screens carry, which
filters are allowed on them and — through `frappe.get_list` — which rows come
back under User Permissions. None of that is re-implemented here, because a
second implementation is a second set of bugs and only one of them would be the
one anybody tests.

So the assistant is not privileged. It runs as the person who typed, sees what
they would see if they clicked, and a question about a space they cannot open
comes back as the same refusal the browser would get. A model that decides to
read every quotation on the site reads the ones its asker could have opened.

Everything is read-only. Not because writing is impossible — the loop in
`ai/conversation.py` would carry it — but because a write needs a confirmation
step in front of it and a confirmation step needs somewhere to appear. Until
that exists, a tool that changes a record is a tool that changes it on a model's
say-so, and `docs/ONESPACE.md` §13 says why that is not shipping.
"""

from typing import Annotated

import frappe

from oneapp.oneapp_core.ai.tools import Tool, tool

#: Rows one tool call may return. The model is looking for an answer, not
#: reading the table — and every row it takes back is input tokens on every
#: turn after it, so a generous limit is paid for repeatedly.
MAX_ROWS = 20

#: Characters of a document the model is shown. A long contract does not fit in
#: a turn and truncating says so rather than silently halving it.
MAX_TEXT = 12_000


@tool
def list_spaces() -> list[dict]:
	"""List the spaces in this workspace that the person asking can open."""
	from oneapp.oneapp_core import sync
	from oneapp.oneapp_core.spaceview.resolve import visible

	return [
		{"space": s.get("space_code"), "label": s.get("space_label")}
		for s in visible(sync.state().get("spaces") or [])
	]


@tool
def list_screens(
	space: Annotated[str, "A space code from list_spaces."],
) -> list[dict]:
	"""List the screens on one space, and what each one holds."""
	from oneapp.oneapp_core.spaceview.resolve import _resolve

	resolved = _resolve(space)
	return [
		{"screen": s["screen"], "label": s["label"]}
		for s in resolved.get("screens") or []
	]


@tool
def describe_screen(
	space: Annotated[str, "A space code from list_spaces."],
	screen: Annotated[str, "A screen from list_screens."],
) -> dict:
	"""Describe one screen: the fields it carries and which may be filtered on.

	Call this before find_records if you are unsure what a field is called. The
	fieldnames it returns are the only ones a filter may name.
	"""
	from oneapp.oneapp_core.spaceview.resolve import _resolve

	resolved = _resolve(space, screen)
	if not resolved.get("doctype"):
		return {"screen": screen, "fields": [], "note": "This screen holds no records."}

	return {
		"screen": resolved["screen"],
		"label": resolved.get("screen_label") or "",
		"one_of_these": resolved.get("singular") or "",
		"fields": [
			{"fieldname": c["fieldname"], "label": c.get("label") or c["fieldname"],
			 "type": c.get("fieldtype") or "Data"}
			for c in (resolved.get("all_columns") or resolved.get("columns") or [])
		],
	}


@tool
def find_records(
	space: Annotated[str, "A space code from list_spaces."],
	screen: Annotated[str, "A screen from list_screens."],
	filters: Annotated[
		list | None,
		"Narrowing, as a list of [fieldname, operator, value] — for example "
		'[["status", "=", "Open"], ["grand_total", ">", 1000]]. Fieldnames come '
		"from describe_screen. A filter naming a field the screen does not "
		"carry is ignored, so check the fields you are shown rather than "
		"guessing.",
	] = None,
	order_by: Annotated[str, "For example 'modified desc'."] = "",
	limit: Annotated[int, "At most 20."] = 10,
) -> dict:
	"""Find records on a screen. Read-only, and only records the asker may see."""
	from oneapp.oneapp_core.spaceview.records import rows

	found = rows(
		space_code=space,
		screen=screen,
		limit=min(int(limit or 10), MAX_ROWS),
		overrides={"filters": filters or []},
	)
	return {
		"records": [_slim(row) for row in found.get("rows") or []],
		"more": bool(found.get("more") or found.get("has_more")),
	}


@tool
def count_records(
	space: Annotated[str, "A space code from list_spaces."],
	screen: Annotated[str, "A screen from list_screens."],
	filters: Annotated[list | None, "As in find_records."] = None,
) -> dict:
	"""Count records on a screen without fetching them.

	Use this for "how many" — fetching twenty rows to count them answers a
	different question and answers it wrongly once there are twenty-one.
	"""
	from oneapp.oneapp_core.spaceview.records import count

	return count(space_code=space, screen=screen, overrides={"filters": filters or []})


@tool
def read_record(
	space: Annotated[str, "A space code from list_spaces."],
	screen: Annotated[str, "A screen from list_screens."],
	name: Annotated[str, "The record's id, as find_records returned it."],
) -> dict:
	"""Read one record in full, including its child tables."""
	from oneapp.oneapp_core.spaceview.records import record

	found = record(space_code=space, screen=screen, name=name)
	if not found:
		return {"error": f"No record called {name} on that screen."}
	return _slim(found, keep_children=True)


@tool
def search_files(
	query: Annotated[str, "Words to look for in file names and document text."],
	limit: Annotated[int, "At most 20."] = 10,
) -> dict:
	"""Search the workspace Drive by file name and by what a document says."""
	from oneapp.oneapp_core.drive.query import ALL
	from oneapp.oneapp_core.drive.reading import listing

	found = listing(place=ALL, search=query, limit=min(int(limit or 10), MAX_ROWS))
	return {
		"files": [
			{"name": f.get("name"), "file_name": f.get("file_name"),
			 "kind": f.get("custom_kind") or "", "folder": f.get("folder_label") or "",
			 "modified": str(f.get("modified") or "")}
			for f in found.get("files") or []
		],
		"more": bool(found.get("more")),
	}


@tool
def read_document(
	name: Annotated[str, "A file id from search_files."],
) -> dict:
	"""Read the text of a document or a plain-text file in the Drive."""
	from oneapp.oneapp_core.docs import body, text

	file_name = frappe.db.get_value("File", name, "file_name") or ""
	if text.is_text(file_name):
		got = text.get_text(name)
		return _clipped(got.get("content") or "")

	body.may_read(name)
	return _clipped(body.readable(body.load(name).get("content") or ""))


#: Every tool the workspace assistant is given. A list rather than a scan of
#: this module: a tool becomes available because it was put here, not because
#: somebody happened to decorate a function in the right file.
TOOLBOX: list[Tool] = [
	list_spaces, list_screens, describe_screen,
	find_records, count_records, read_record,
	search_files, read_document,
]


def tools() -> list[Tool]:
	"""What `@ai_feature(tools=...)` resolves to. See `features.Feature.tools`.

	Not named `toolbox`: a function of that name in a module of that name is a
	function that shadows its own module wherever the package re-exports it, and
	the path the decorator holds would then resolve to the callable rather than
	to the module containing it.
	"""
	return TOOLBOX


# --------------------------------------------------------------------------- #
# Trimming
#
# What comes back from a screen is shaped for a browser — link previews, owner
# avatars, comment counts, a `_liked_by` blob. None of it helps a model answer a
# question and all of it is input tokens on every subsequent turn of the same
# conversation, which is where a chat quietly becomes expensive.
# --------------------------------------------------------------------------- #

#: Keys the SPA needs and a model does not, that are not already underscored.
CHROME = {"liked", "owner_person", "modified_pretty", "state", "links", "people"}


def _slim(row: dict, keep_children: bool = False) -> dict:
	"""One record, with the browser's half taken off.

	Two rules and both are about cost. Every leading-underscore key is Frappe's
	own bookkeeping — `_liked_by`, `_user_tags`, `_assign`, and the `_meta` block
	the list builds out of them — so the whole prefix goes; the one thing in
	there a question can turn on is when the record last changed, which is
	lifted out by name. And child tables come back only for `read_record`,
	because twenty records with their line items is not an answer to anything
	and is input tokens on every turn afterwards.
	"""
	out = {}
	for key, value in (row or {}).items():
		if key.startswith("_") or key in CHROME:
			continue
		if isinstance(value, list):
			if keep_children:
				out[key] = [_slim(child) for child in value[:MAX_ROWS]
				            if isinstance(child, dict)]
			continue
		out[key] = value if not hasattr(value, "isoformat") else str(value)

	changed = (row or {}).get("_meta", {})
	if isinstance(changed, dict) and changed.get("modified"):
		out["modified"] = str(changed["modified"])
	return out


def _clipped(content: str) -> dict:
	if len(content) <= MAX_TEXT:
		return {"text": content, "truncated": False}
	return {"text": content[:MAX_TEXT], "truncated": True,
	        "note": f"Only the first {MAX_TEXT} characters are shown."}
