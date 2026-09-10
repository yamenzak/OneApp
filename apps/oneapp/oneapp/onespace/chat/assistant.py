"""The workspace assistant: one declared AI feature that happens to loop.

Everything about it is ordinary. It is an `@ai_feature`, so it appears in the
workspace's AI settings as a row with a model picker filtered to the capability
it declared, it can be switched off, a workspace may append to its instructions
and may never read them, and every turn holds credits before the call and
settles them after. There is no second AI path and no configuration surface of
its own — a chat that could name a provider would be the thing we do not do.

What makes it a chat rather than a summary is two lines of the declaration:
`tools` names what it may read, and `max_turns` says how many calls one question
may become. `ai/conversation.py` is the loop; `toolbox.py` is what the loop may
run; neither is reachable except through here.

The cost shape is the thing to keep in view. A question that needs three
lookups is four calls, four holds and four settlements, and it is charged as
four — which is honest and is also why `max_run_credits` exists.
"""

import frappe
from frappe import _

from oneapp.onespace.ai import conversation
from oneapp.onespace.ai.features import ai_feature
from oneapp.onespace.chat import context, session as store
from oneapp.onespace.chat.toolbox import tools

SYSTEM = """You are the assistant inside a OneSpace workspace. You help the \
person you are talking to with their own work in this workspace.

Answer from what the tools tell you. You cannot see anything until you look, so \
when a question is about this workspace's records, files or documents, use the \
tools rather than answering from memory — and when the tools return nothing, \
say that nothing was found rather than filling the gap.

The tools run as the person asking, so what you can read is what they could \
have opened themselves. If a tool refuses, tell them plainly that they do not \
have access to it; never speculate about what the record might have said.

Work in the workspace's own words. A screen is called what its label calls it, \
and a record is one of whatever the screen says it is one of. The names the \
tools take and return are for the tools; the answer uses the words on screen.

Be brief. Give the answer first. Quote figures exactly as the tools reported \
them and never round a total or estimate a count — call count_records instead. \
When you name a record, give the id the tools returned so it can be found.

You cannot change anything. Every tool is read-only. If you are asked to create, \
edit, send or delete something, say that you can only read, and say where in the \
workspace it can be done."""


@ai_feature(
	"chat.workspace",
	label="Workspace assistant",
	capability="Text Generation",
	system=SYSTEM,
	description="Answers questions about this workspace's records, files and documents.",
	tools="oneapp.onespace.chat.toolbox.tools",
	# One question, at most eight calls. Enough for look, narrow, read, answer
	# with room to recover from a wrong guess; short enough that a model stuck
	# in a loop costs a known amount rather than an open-ended one.
	max_turns=8,
	max_run_credits=25,
	# Per call, and generous on input because a transcript grows: by the sixth
	# turn the prompt carries five answers and everything they returned.
	max_input_tokens=120_000,
	max_output_tokens=2_000,
)
def ask(ai, session: str, question: str, on: dict | None = None) -> dict:
	"""Answer one question in a stored conversation, using the workspace's data.

	`on` is what the reader has open, already checked by `context.read`. It
	narrows the tools to that space and puts one sentence in front of the model
	saying which screen and which record — so "is this priced above the last
	one?" works in the panel beside a quotation and means nothing from the rail.
	"""
	on = on or {}
	spoken = store.transcript(session) + [{"role": "user", "content": question}]

	run = conversation.run(ai, spoken, context.bound(tools(), on), context.note(on))

	# Only what this ask added. `run.messages` is the whole transcript because
	# the loop needs it; storing it whole would write every earlier turn again.
	store.append(session, run["messages"][len(spoken) - 1:],
	             credits=run.get("credits") or 0, stopped=run.get("stopped") or "")
	return run


# --------------------------------------------------------------------------- #
# Endpoints
#
# Four, and none of them takes a model, a prompt or a limit. What the assistant
# is allowed to do is declared above; a browser picks the session and types the
# question.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def sessions() -> dict:
	"""The threads this person has, and whether the assistant is available."""
	from oneapp.onespace.ai import features, gateway

	feature = features.get("oneapp.chat.workspace")
	return {
		"sessions": store.listing(),
		"available": bool(feature and gateway.is_configured()
		                  and features.is_enabled(feature.key)),
	}


@frappe.whitelist(methods=["GET"])
def messages(session: str) -> dict:
	"""One thread, as it is shown: the turns a person sees and what was looked at.

	`tool` rows are not returned as messages. They are the working, not the
	conversation — but which tools ran is worth showing, so the lookups are
	carried onto the answer they led to and the reader can see it came from four
	quotations rather than from nowhere.

	A turn where the model only asked for tools has no text of its own. Those
	rows are not sent either: rendering one is an empty bubble between the
	question and the answer, which reads as a failure. Their lookups gather onto
	the next turn that actually says something, so a reply arrives with its whole
	working under it.
	"""
	shown, gathered = [], []
	for row in store.rows(session):
		if row["role"] == "tool":
			continue

		gathered += [
			{"tool": call.get("name") or "", "arguments": call.get("arguments") or {}}
			for call in store._parsed(row.get("tool_calls"))
		]

		# The exception is a run that stopped without answering: it has no text
		# either, and it is the one case where the silence has to be shown,
		# because `stopped` is what the reader is told instead.
		if not (row.get("content") or "").strip() and not row.get("stopped"):
			continue

		shown.append({
			"name": row["name"],
			"role": row["role"],
			"content": row.get("content") or "",
			"looked_at": gathered,
			"credits": row.get("credits") or 0,
			"stopped": row.get("stopped") or "",
			"on": str(row.get("creation") or ""),
		})
		gathered = []

	return {"session": session, "messages": shown}


@frappe.whitelist(methods=["POST"])
def send(question: str, session: str = "", on: str | dict | None = None) -> dict:
	"""Ask. Opens a thread if there is not one yet, and returns the whole reply.

	Not streamed. A streaming answer would have to hold a worker open for the
	length of a loop that may make eight provider calls, and a chat is not worth
	a request that can occupy a worker for two minutes. What arrives instead is
	the finished answer with the tools it used beside it.

	`on` is where the question was asked from — `{space, screen, docname}`, as
	the panel knows it. It arrives from a browser, so `context.read` resolves it
	through the same checks a click goes through and drops what does not hold.
	"""
	from oneapp.onespace.ai import features, gateway

	question = (question or "").strip()
	if not question:
		frappe.throw(_("Ask something first."))

	session = session or store.start(question)
	store.mine(session, "write")

	try:
		run = ask(session, question, context.read(on))
	except gateway.OutOfCredits as e:
		return {"session": session, "ok": False, "reason": "insufficient_credits",
		        "message": str(e)}
	except features.FeatureDisabled as e:
		return {"session": session, "ok": False, "reason": "disabled", "message": str(e)}

	return {
		"session": session,
		"ok": True,
		"reply": run.get("reply") or "",
		"stopped": run.get("stopped") or "",
		"credits": run.get("credits") or 0,
		"looked_at": run.get("tool_calls") or [],
		**messages(session),
	}


@frappe.whitelist(methods=["POST"])
def forget(session: str) -> dict:
	"""Delete a thread. There is no archive-and-keep: gone is what it says."""
	store.remove(session)
	return {"ok": True}
