"""The tools that ask, for any feature that has tools at all.

Four of them, one per registered kind that takes arguments a model can
sensibly choose, and none of them writes anything: each records what *would*
happen and returns "waiting", and the doing is a separate request a person
makes by pressing Apply. `actions.py` is where that split is argued.

They live here rather than in `chat/toolbox.py`, where the first two started,
because the assistant is not the only thing that proposes any more. A mail
thread offers the same three verbs off the same registry, and a copy of these
declarations under `onemail/` would be four more descriptions for a model to
read slightly differently.

**Where a card belongs is bound, never chosen.** `session`, `about_doctype`
and `about_name` are filled in by the caller and taken out of the schema, so
the model has no word for them — the alternative is a model that can file its
suggestion under another person's thread, since a session id is all a card is
found by.
"""

from typing import Annotated

import frappe

from oneapp.onespace.ai.tools import Tool, tool


def _ask(kind: str, session: str, about_doctype: str, about_name: str,
         payload: dict) -> dict:
	from oneapp.onespace.ai import actions

	return actions.propose(
		kind,
		payload,
		about=(about_doctype or "", about_name or ""),
		session=session or "",
		after_message=_last_message(session),
	)


def _last_message(session: str) -> str:
	"""The turn a chat card hangs under. Empty where there is no chat."""
	if not session:
		return ""
	rows = frappe.get_all("OneSpace Chat Message", filters={"session": session},
	                      fields=["name"], order_by="seq desc", limit_page_length=1)
	return rows[0]["name"] if rows else ""


@tool
def propose_update(
	session: Annotated[str, "Filled in for you."],
	about_doctype: Annotated[str, "Filled in for you."],
	about_name: Annotated[str, "Filled in for you."],
	space: Annotated[str, "A space code from list_spaces."],
	screen: Annotated[str, "A screen from list_screens."],
	name: Annotated[str, "The record's id, as find_records returned it."],
	values: Annotated[
		dict,
		"Fieldname to new value — for example {\"status\": \"Closed\"}. "
		"Fieldnames come from describe_screen. Only the fields that should "
		"change; anything you leave out stays as it is.",
	],
) -> dict:
	"""Ask to change one record. Nothing is written until the person approves it.

	Read the record first. Say afterwards what you have asked for and that it
	is waiting — do not say it is done, because it is not.
	"""
	return _ask("record.save", session, about_doctype, about_name, {
		"space": space, "screen": screen, "docname": name, "values": values or {},
	})


@tool
def propose_create(
	session: Annotated[str, "Filled in for you."],
	about_doctype: Annotated[str, "Filled in for you."],
	about_name: Annotated[str, "Filled in for you."],
	space: Annotated[str, "A space code from list_spaces."],
	screen: Annotated[str, "A screen from list_screens."],
	values: Annotated[dict, "Fieldname to value, as in propose_update."],
) -> dict:
	"""Ask to create one record. Nothing is written until the person approves it.

	Call describe_screen first, and fill in what the person actually said.
	Do not invent a value for a field they did not mention.
	"""
	return _ask("record.save", session, about_doctype, about_name, {
		"space": space, "screen": screen, "values": values or {},
	})


@tool
def propose_task(
	session: Annotated[str, "Filled in for you."],
	about_doctype: Annotated[str, "Filled in for you."],
	about_name: Annotated[str, "Filled in for you."],
	what: Annotated[str, "The task, in one line, as the person would write it."],
	due: Annotated[str | None, "When it is due, as YYYY-MM-DD. Leave it out if "
	                           "nobody said when."] = None,
) -> dict:
	"""Ask to add a task for the person you are helping.

	Theirs, never somebody else's: a task made for a colleague is a
	notification they did not agree to. Nothing is added until they approve it.
	"""
	return _ask("task", session, about_doctype, about_name,
	            {"what": what, "due": due or ""})


@tool
def propose_event(
	session: Annotated[str, "Filled in for you."],
	about_doctype: Annotated[str, "Filled in for you."],
	about_name: Annotated[str, "Filled in for you."],
	subject: Annotated[str, "What the event is called."],
	starts_on: Annotated[str, "When it starts, as YYYY-MM-DD HH:MM:SS."],
	ends_on: Annotated[str | None, "When it ends, same format. Leave it out if "
	                               "nobody said."] = None,
	description: Annotated[str | None, "Anything else worth having in the "
	                                   "entry."] = None,
) -> dict:
	"""Ask to put something in the person's own calendar.

	Only where a real date was said. "Next week" with no day is not an event —
	say so and ask which day rather than choosing one. Nothing is added until
	they approve it.
	"""
	return _ask("calendar.event", session, about_doctype, about_name, {
		"subject": subject, "starts_on": starts_on,
		"ends_on": ends_on or "", "description": description or "",
	})


#: Every tool that asks. A list rather than a scan of this module, for the
#: same reason `chat/toolbox.py` keeps one.
PROPOSALS: list[Tool] = [propose_update, propose_create, propose_task, propose_event]


def where(toolbox: list[Tool], *, session: str = "", about_doctype: str = "",
          about_name: str = "") -> list[Tool]:
	"""Fill in where these cards belong, and take it out of the schema.

	Called by every feature that hands a model a proposing tool. A tool that
	does not take these is left alone — binding an argument a tool never
	declared is a TypeError a turn later, which is the wrong place to find out.
	"""
	filled = {"session": session, "about_doctype": about_doctype,
	          "about_name": about_name}
	return [
		one.bind(**{k: v for k, v in filled.items() if one.takes(k)})
		if any(one.takes(k) for k in filled) else one
		for one in toolbox
	]
