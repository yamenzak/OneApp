"""Storing a conversation, and reading one back as a transcript.

Two shapes for the same thing and the seam between them is here. On disk a turn
is a `OneSpace Chat Message` row, because that is what a list, a permission rule
and a delete work on. In a request it is the dict shape `ai/transcript.py`
speaks, because that is what goes to a provider.

Rows are never rewritten. A conversation is append-only: the assistant's answer
to what was true on Tuesday stays what it said on Tuesday, and a tool result is
kept beside the question it answered rather than re-run when the thread is
reopened.
"""

import json

import frappe
from frappe import _

SESSION = "OneSpace Chat Session"
MESSAGE = "OneSpace Chat Message"

#: How much of the first question becomes the thread's name.
TITLE_LENGTH = 80

#: Turns sent back to the model. A conversation older than this is still on
#: disk and still readable; it is not all re-sent, because every stored turn is
#: input tokens on every turn after it and a long thread would cost more to
#: continue than it did to have.
WINDOW = 40


def mine(name: str, level: str = "read"):
	"""The session, if it is this person's. Frappe's own check, not a new one."""
	if not frappe.has_permission(SESSION, level, doc=name):
		frappe.throw(_("That conversation is not yours."), frappe.PermissionError)
	return frappe.get_doc(SESSION, name)


def start(first_question: str) -> str:
	"""Open a thread, named after what was asked."""
	title = " ".join((first_question or "").split())[:TITLE_LENGTH] or _("New chat")
	doc = frappe.get_doc({"doctype": SESSION, "title": title})
	doc.insert()
	return doc.name


def listing(limit: int = 50) -> list[dict]:
	"""The threads this person may open, most recently spoken to first."""
	return frappe.get_list(
		SESSION,
		filters={"archived": 0},
		fields=["name", "title", "last_message_on", "message_count", "credits"],
		order_by="last_message_on desc, creation desc",
		limit_page_length=int(limit or 50),
	)


def rows(session: str) -> list[dict]:
	"""Every stored turn of one session, oldest first."""
	mine(session)
	return frappe.get_list(
		MESSAGE,
		filters={"session": session},
		fields=["name", "seq", "role", "content", "tool_calls", "tool_call_id",
		        "tool_name", "credits", "stopped", "creation"],
		order_by="seq asc",
		limit_page_length=0,
	)


def transcript(session: str) -> list[dict]:
	"""The stored turns, in the shape a provider is sent.

	Windowed from the end and then trimmed forward past any orphaned tool
	result: a transcript that opens with an answer to a question it does not
	contain is rejected by Gemini and confuses everything else.
	"""
	stored = rows(session)[-WINDOW:]
	while stored and stored[0]["role"] == "tool":
		stored.pop(0)

	out = []
	for row in stored:
		if row["role"] == "tool":
			out.append({"role": "tool", "tool_call_id": row.get("tool_call_id") or "",
			            "name": row.get("tool_name") or "", "content": row.get("content") or ""})
			continue

		turn = {"role": row["role"], "content": row.get("content") or ""}
		calls = _parsed(row.get("tool_calls"))
		if calls:
			turn["tool_calls"] = calls
		out.append(turn)
	return out


def append(session: str, turns: list[dict], credits: float = 0,
           stopped: str = "") -> None:
	"""Write new turns onto a session and move its counters.

	`credits` and `stopped` land on the last turn written, which is the
	assistant's: it is the turn the run produced, and hanging the cost off a
	tool result would say a lookup cost money the model's answer did not.
	"""
	doc = mine(session, "write")
	# The last row's own `seq` rather than a MAX(): Frappe refuses a SQL
	# function passed as a string, and one ordered row costs the same as the
	# aggregate would.
	last = frappe.get_all(MESSAGE, filters={"session": session}, fields=["seq"],
	                      order_by="seq desc", limit_page_length=1)
	seq = (last[0].get("seq") if last else 0) or 0

	written = None
	for turn in turns:
		seq += 1
		written = frappe.get_doc({
			"doctype": MESSAGE,
			"session": session,
			"seq": seq,
			"role": turn.get("role") or "user",
			"content": turn.get("content") or "",
			"tool_calls": json.dumps(turn["tool_calls"]) if turn.get("tool_calls") else "",
			"tool_call_id": turn.get("tool_call_id") or "",
			"tool_name": turn.get("name") or "",
		})
		written.insert()

	if written and (credits or stopped):
		written.db_set({"credits": credits, "stopped": stopped},
		               update_modified=False)

	doc.db_set({
		"message_count": (doc.message_count or 0) + len(turns),
		"credits": float(doc.credits or 0) + float(credits or 0),
		"last_message_on": frappe.utils.now(),
	}, update_modified=False)


def remove(session: str) -> None:
	"""Delete a thread and everything in it.

	The messages first and by hand: they link to the session, so Frappe would
	refuse to delete a session that still has any, and a chat somebody wants
	gone should not need two steps.
	"""
	mine(session, "delete")
	for row in frappe.get_all(MESSAGE, filters={"session": session}, pluck="name"):
		frappe.delete_doc(MESSAGE, row, ignore_permissions=True)
	frappe.delete_doc(SESSION, session)


def _parsed(raw):
	if not raw:
		return []
	try:
		found = json.loads(raw)
	except (TypeError, ValueError):
		return []
	return found if isinstance(found, list) else []
