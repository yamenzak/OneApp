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
from oneapp.onespace.chat import changes, context, session as store
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

You do not change anything yourself. Two tools — propose_update and \
propose_create — ask for a change and write nothing: they put a card in front \
of the person with the exact fields on it, and the change happens if and when \
they press Apply. So never say you have changed, created, updated or saved \
something. Say what you have asked for and that it is waiting for them.

Read the record before proposing a change to it, so the card shows what is \
actually there. Set only the fields the person asked about, and never invent a \
value for one they did not mention. If a change turns out to be several — three \
records to close — propose each one, so each can be agreed to or refused on its \
own.

Everything else is read-only. There is no tool that deletes, submits, cancels \
or sends, and there is no way to ask for one. If that is what is wanted, say so \
plainly and say where in the workspace it can be done."""


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

	# The session is bound rather than declared, the same way the space is: a
	# proposal belongs to the thread it was asked for in, and an argument the
	# model can still see is one it can be talked into changing — into another
	# person's thread, since a session id is all a proposal is filed under.
	usable = [one.bind(session=session) if one.takes("session") else one
	          for one in context.bound(tools(), on)]

	run = conversation.run(ai, spoken, usable, context.note(on))

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
	# The thread first, because `store.rows` is where the ownership check is
	# and a refusal should happen before anything else is read.
	stored = store.rows(session)
	waiting = changes.for_session(session)

	shown, gathered = [], []
	for row in stored:
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
			"changes": [],
			"credits": row.get("credits") or 0,
			"stopped": row.get("stopped") or "",
			"on": str(row.get("creation") or ""),
		})
		gathered = []

	_hang(shown, waiting)
	return {"session": session, "messages": shown}


def _hang(shown: list[dict], waiting: list[dict]) -> None:
	"""Put each proposed change under the answer that asked for it.

	A change carries the last turn stored when the tool ran, which is the
	previous run's answer or nothing at all. So it belongs to the first
	assistant turn *after* that one — the answer this run went on to write.

	The fallback is the last turn shown, and it is the case that actually
	happens: a run that proposed something and then ran out of turns has no
	answer of its own, and a card with nowhere to hang is a change somebody
	agreed to that they can no longer see.
	"""
	if not shown:
		return

	by_name = {turn["name"]: at for at, turn in enumerate(shown)}
	for change in waiting:
		after = by_name.get(change.get("after_message") or "", -1)
		landed = next(
			(turn for turn in shown[after + 1:] if turn["role"] == "assistant"),
			shown[-1],
		)
		landed["changes"].append(change)


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
def apply_change(name: str) -> dict:
	"""Make the change the assistant asked for. This is the write.

	Here rather than inside the loop, and that is the whole design: the request
	is one a person made, it runs as them, and it goes through the same save
	the record form posts to. A model cannot reach this — there is no tool that
	calls it, and adding one would undo the only thing that makes the pair of
	`propose_` tools safe.
	"""
	return changes.apply(name)


@frappe.whitelist(methods=["POST"])
def discard_change(name: str) -> dict:
	"""No. The row stays, so the thread still shows what was asked."""
	return changes.discard(name)


@frappe.whitelist(methods=["POST"])
def forget(session: str) -> dict:
	"""Delete a thread. There is no archive-and-keep: gone is what it says."""
	store.remove(session)
	return {"ok": True}
