"""Several calls in a row, because the model asked for something first.

Derived from `frappe/flow_client` (`flow/lib/agent.py`), AGPL-3.0, Copyright (c)
2026 Frappe Technologies and contributors. The loop is theirs — ask, execute
what came back, append the results, ask again — and it is the one thing our AI
layer did not have. Everything under `gateway.py` is a single shot: one prompt
in, one answer out, one hold and one settlement. A model that can call a tool
needs to be asked more than once, and nothing above knew how.

What is not theirs is where the model comes from. Flow's `Agent` holds a
`Model`, which resolves an API key and a base URL from a `Flow Provider` row a
workspace can edit. That is exactly the arrangement OneSpace does not have: a
workspace never names a provider, never holds a key and never chooses a model
outside the catalogue. So the loop takes the callable `@ai_feature` injects, and
every turn is an ordinary metered call through the gateway — held, made,
settled, logged, indistinguishable in the ledger from a summary.

Which is also where the cost is. A turn is a whole call, so a run of nine turns
spends the feature's ceiling nine times. `max_run_credits` is the number that
bounds one ask, and it is checked here between turns rather than at the gateway,
because the gateway is looking at a call and this is the only thing that can see
the loop.
"""

import frappe

from oneapp.oneapp_core.ai import features, tools as tooling

#: A stop the caller should show rather than swallow: the model kept calling
#: tools until it ran out of room. The partial transcript is still returned.
TURNS_SPENT = "turns_spent"
BUDGET_SPENT = "budget_spent"
ANSWERED = "answered"


class Run(dict):
	"""What a whole ask cost and came to. A dict so it crosses an endpoint."""

	def __getattr__(self, name):
		try:
			return self[name]
		except KeyError as e:
			raise AttributeError(name) from e


def run(ai, messages: list[dict], toolbox: list[tooling.Tool] | None = None,
        note: str = "") -> Run:
	"""Ask until the model stops asking for things, or until the budget says stop.

	`ai` is what the decorator injected — it carries the feature, so the turn
	limit, the credit budget, the model and the system prompt all come from the
	declaration rather than from arguments here.

	`messages` is the transcript so far and is not mutated: a caller holding a
	stored session should get its rows back unchanged if this raises.

	`note` is a fact about this run — the screen the reader has open, say —
	appended to the system prompt on every turn of it. Not stored with the
	transcript: it describes where the question was asked from, and reopening
	the thread tomorrow from somewhere else must not re-assert it.
	"""
	from oneapp.oneapp_core.ai import settings

	feature = ai.feature
	budget = settings.run_budget(feature)
	turns = int(budget.get("max_turns") or 0)
	if turns < 1:
		raise features.AIError(
			f"{feature.label} is not declared conversational: it has no max_turns."
		)
	ceiling = float(budget.get("max_run_credits") or 0)

	by_name = {one.name: one for one in (toolbox or [])}
	declared = [one.declare() for one in by_name.values()] or None

	transcript = list(messages)
	spent, used_tools = 0.0, []

	for turn in range(1, turns + 1):
		# Before the call, not after: a hold is placed the moment the call is
		# made, so a run that is already over budget must not make one more.
		if ceiling and spent >= ceiling:
			return Run(messages=transcript, reply="", credits=spent, turns=turn - 1,
			           tool_calls=used_tools, stopped=BUDGET_SPENT)

		answer = ai(messages=transcript, tools=declared, note=note)
		spent += float(answer.get("credits") or 0)

		calls = answer.get("tool_calls") or []
		transcript = transcript + [{
			"role": "assistant",
			"content": answer.get("text") or "",
			**({"tool_calls": calls} if calls else {}),
		}]

		if not calls:
			return Run(messages=transcript, reply=answer.get("text") or "",
			           credits=spent, turns=turn, tool_calls=used_tools,
			           stopped=ANSWERED)

		for call in calls:
			one = by_name.get(call["name"])
			if one is None:
				# Named a tool it was not given. Told rather than aborted on:
				# the model can pick another, and a run that dies here dies
				# with the user's question unanswered.
				result = tooling.serialize({"error": f"No tool named {call['name']}."})
			else:
				result = tooling.run(one, call.get("arguments") or {})
				used_tools.append({"name": call["name"],
				                   "arguments": call.get("arguments") or {}})

			transcript = transcript + [{
				"role": "tool",
				"tool_call_id": call["id"],
				"name": call["name"],
				"content": result,
			}]

	# Out of turns with the model still working. The transcript is returned
	# rather than thrown away: the tool results in it were paid for, and a
	# caller that stores the session can let somebody ask again from here.
	frappe.log_error(
		title=f"{feature.label} ran out of turns",
		message=f"{turns} turns, {spent} credits, tools: "
		        f"{', '.join(t['name'] for t in used_tools) or 'none'}",
	)
	return Run(messages=transcript, reply="", credits=spent, turns=turns,
	           tool_calls=used_tools, stopped=TURNS_SPENT)
