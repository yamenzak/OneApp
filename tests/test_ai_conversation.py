"""A run of several calls: the loop, the budget, and the two provider shapes.

The gateway suite next door proves one call holds, calls and settles. This
proves the thing above it — that a model asking for a tool gets one, that what
it gets back is charged for as a whole call, and that a loop which will not stop
is stopped rather than spending until the credits run out.

The transport is the same fake `requests.post`; everything between it and the
loop is the real code.
"""

import json
import types
from typing import Annotated

import pytest


@pytest.fixture
def gateway(stub_frappe, monkeypatch):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	stub_frappe.conf = {
		"oneapp_cf_account_id": "acct", "oneapp_ai_gateway": "oneapp",
		"oneapp_ai_gateway_token": "gwtok", "oneapp_tenant": "acme",
		"oneapp_cf_api_token": "cftok",
	}
	stub_frappe.log_error = lambda **kw: None
	stub_frappe.get_traceback = lambda: ""

	from oneapp.onespace.ai import (
		conversation, features, gateway as module, settings, tools, transcript,
	)

	features.REGISTRY.clear()
	return types.SimpleNamespace(
		module=module, features=features, settings=settings, tools=tools,
		transcript=transcript, conversation=conversation,
		frappe=stub_frappe, monkeypatch=monkeypatch,
	)


CATALOGUE = [{
	"model_key": "google-ai-studio:flash", "display_name": "Flash",
	"provider": "google-ai-studio", "model_id": "gemini-3.7-flash",
	"capability": "Text Generation", "is_recommended": 1, "prices": [],
}, {
	"model_key": "workers-ai:llama", "display_name": "Llama",
	"provider": "workers-ai", "model_id": "@cf/meta/llama-4",
	"capability": "Text Generation", "prices": [],
}]


class Single:
	"""The workspace's AI settings single, with one feature row on it.

	`key` rather than a literal because `@ai_feature` names a feature after the
	module that declared it, and here that module is this file.
	"""

	def __init__(self, model="", key=""):
		self.ai_enabled = 1
		self.credit_balance = 100
		self.features = ([types.SimpleNamespace(
			feature_key=key, enabled=1, model_key=model, prompt_addendum="",
			model_options="",
		)] if model else [])

	def get(self, field, default=None):
		"""What a Frappe Document does. The assistant's identity is read this
		way — the fields may not exist yet on a site mid-deploy, and a stub
		that raises where the real thing answers None tests the stub."""
		return getattr(self, field, default)

	def append(self, _f, values):
		self.features.append(types.SimpleNamespace(**values))
		return self.features[-1]

	def save(self, **kw):
		pass


class Response:
	def __init__(self, payload):
		self._payload = payload
		self.status_code = 200
		self.headers = {"cf-aig-log-id": "log-1"}
		self.text = json.dumps(payload)

	def json(self):
		return self._payload


def gemini(text="", calls=()):
	parts = ([{"text": text}] if text else []) + [
		{"functionCall": {"name": name, "args": args}} for name, args in calls
	]
	return Response({
		"candidates": [{"content": {"parts": parts}}],
		"usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20},
	})


def wire(gw, replies, model="", credits=0.5, turns=4, run_credits=0):
	"""One feature, a queue of provider replies, and a fake control plane."""
	gw.frappe.db.get_single_value = lambda dt, f: (
		json.dumps(CATALOGUE) if f == "catalogue_json" else json.dumps([])
	)

	answered = list(replies)
	sent = []

	def post(url, headers=None, json=None, timeout=None):
		sent.append({"url": url, "body": json})
		return answered.pop(0)

	gw.monkeypatch.setattr("oneapp.onespace.ai.gateway.requests.post", post)
	gw.monkeypatch.setattr(
		"oneapp.onespace.control_client.call",
		lambda method, payload=None: (
			{"ok": True, "reservation": "CRES-1", "ceiling": 2.0}
			if method == "ai_reserve" else {"ok": True, "credits": credits}
		),
	)

	@gw.features.ai_feature(
		"chat", label="Chat", system="You are ours.",
		max_output_tokens=400, max_turns=turns, max_run_credits=run_credits,
		tools="oneapp.onespace.chat.toolbox.tools",
	)
	def run(call, **kw):
		return call(**kw)

	feature = next(iter(gw.features.REGISTRY.values()))
	gw.frappe.get_single = lambda dt: Single(model, feature.key)
	return sent, gw.module.caller(feature)


def toolbox(gw, seen):
	@gw.tools.tool
	def count_records(
		screen: Annotated[str, "which screen"],
	) -> dict:
		"""Count records on a screen."""
		seen.append(screen)
		return {"count": 4}

	return [count_records]


# --------------------------------------------------------------------------- #
# The loop
# --------------------------------------------------------------------------- #

def test_a_tool_call_becomes_a_second_call_carrying_its_result(gateway):
	seen = []
	sent, ai = wire(gateway, [
		gemini(calls=[("count_records", {"screen": "quotations"})]),
		gemini("Four are open."),
	])

	run = gateway.conversation.run(ai, [{"role": "user", "content": "how many?"}],
	                              toolbox(gateway, seen))

	assert seen == ["quotations"], "the tool never ran"
	assert run["reply"] == "Four are open."
	assert run["turns"] == 2
	assert run["stopped"] == "answered"

	# The second request carries the answer to the first, as a functionResponse.
	second = sent[1]["body"]["contents"]
	assert any(
		part.get("functionResponse", {}).get("name") == "count_records"
		for turn in second for part in turn["parts"]
	), second


def test_every_turn_is_its_own_metered_call(gateway):
	"""Three turns is three holds and three settlements, and it says so."""
	sent, ai = wire(gateway, [
		gemini(calls=[("count_records", {"screen": "a"})]),
		gemini(calls=[("count_records", {"screen": "b"})]),
		gemini("Done."),
	], credits=0.5)

	run = gateway.conversation.run(ai, [{"role": "user", "content": "hi"}],
	                              toolbox(gateway, []))

	assert len(sent) == 3
	assert run["credits"] == 1.5


def test_the_loop_stops_at_the_declared_turn_limit(gateway):
	"""A model that never stops asking is stopped, with what it did kept."""
	sent, ai = wire(gateway, [
		gemini(calls=[("count_records", {"screen": "a"})]) for _ in range(4)
	], turns=4)

	run = gateway.conversation.run(ai, [{"role": "user", "content": "hi"}],
	                              toolbox(gateway, []))

	assert len(sent) == 4
	assert run["stopped"] == "turns_spent"
	assert run["reply"] == ""
	# The transcript is not thrown away: those tool results were paid for.
	assert any(turn["role"] == "tool" for turn in run["messages"])


def test_the_run_budget_stops_it_before_the_turn_limit_does(gateway):
	"""`max_run_credits` is checked between turns, against what settled.

	Before the call and not after: a hold is placed the moment a call is made,
	so a run already over budget must not make one more.
	"""
	sent, ai = wire(gateway, [
		gemini(calls=[("count_records", {"screen": "a"})]) for _ in range(4)
	], credits=0.6, turns=4, run_credits=1.0)

	run = gateway.conversation.run(ai, [{"role": "user", "content": "hi"}],
	                              toolbox(gateway, []))

	assert len(sent) == 2, "a third call was made past the budget"
	assert run["stopped"] == "budget_spent"
	assert run["credits"] == pytest.approx(1.2)


def test_a_feature_with_no_turn_limit_is_not_conversational(gateway):
	_, ai = wire(gateway, [gemini("hi")], turns=0)
	with pytest.raises(gateway.features.AIError, match="not declared conversational"):
		gateway.conversation.run(ai, [{"role": "user", "content": "hi"}], [])


def test_a_tool_the_model_invented_is_answered_rather_than_fatal(gateway):
	sent, ai = wire(gateway, [
		gemini(calls=[("delete_everything", {})]),
		gemini("I cannot do that."),
	])

	run = gateway.conversation.run(ai, [{"role": "user", "content": "hi"}],
	                              toolbox(gateway, []))

	assert run["reply"] == "I cannot do that."
	answered = [m for m in run["messages"] if m["role"] == "tool"]
	assert "No tool named delete_everything" in answered[0]["content"]


def test_a_tool_that_raises_tells_the_model_rather_than_the_user(gateway):
	@gateway.tools.tool
	def read_record(name: str) -> dict:
		"""Read a record."""
		raise PermissionError("You are not allowed to read that.")

	sent, ai = wire(gateway, [
		gemini(calls=[("read_record", {"name": "Q-1"})]),
		gemini("You do not have access to that quotation."),
	])

	run = gateway.conversation.run(ai, [{"role": "user", "content": "read Q-1"}],
	                              [read_record])

	assert run["reply"] == "You do not have access to that quotation."
	told = [m for m in run["messages"] if m["role"] == "tool"][0]["content"]
	assert "not allowed to read that" in told


# --------------------------------------------------------------------------- #
# What reaches the provider
# --------------------------------------------------------------------------- #

def test_the_tools_reach_gemini_as_function_declarations(gateway):
	sent, ai = wire(gateway, [gemini("hi")])
	gateway.conversation.run(ai, [{"role": "user", "content": "hi"}],
	                        toolbox(gateway, []))

	declared = sent[0]["body"]["tools"][0]["functionDeclarations"]
	assert [one["name"] for one in declared] == ["count_records"]
	# The arguments survived the trip. Filtering `properties` the way the level
	# above it is filtered deletes every one of them, which is a tool the model
	# is told takes nothing.
	assert "screen" in declared[0]["parameters"]["properties"]
	assert "additionalProperties" not in declared[0]["parameters"]


def test_the_same_loop_runs_on_workers_ai(gateway):
	"""The one provider that speaks OpenAI, so the transcript is nearly untouched."""
	answered = [
		Response({"result": {"response": "", "tool_calls": [
			{"name": "count_records", "arguments": {"screen": "quotations"}}]}}),
		Response({"result": {"response": "Four are open."}}),
	]
	seen = []
	sent, ai = wire(gateway, answered, model="workers-ai:llama")

	run = gateway.conversation.run(ai, [{"role": "user", "content": "how many?"}],
	                              toolbox(gateway, seen))

	assert seen == ["quotations"]
	assert run["reply"] == "Four are open."
	# Its own shape: a system message in `messages`, and tools as OpenAI declares.
	assert sent[0]["body"]["messages"][0]["role"] == "system"
	assert sent[0]["body"]["tools"][0]["function"]["name"] == "count_records"


def test_the_system_prompt_is_ours_and_the_workspace_may_only_add(gateway):
	"""The rule the whole AI layer rests on, checked on the conversational path."""
	gateway.frappe.get_single = lambda dt: Single()
	sent, ai = wire(gateway, [gemini("hi")])
	gateway.conversation.run(ai, [{"role": "user", "content": "hi"}], [])

	said = sent[0]["body"]["systemInstruction"]["parts"][0]["text"]
	assert said.startswith("You are ours.")
	# And the house rules behind it, last, on this path as on every other.
	assert said.rstrip().endswith(gateway.settings.house())
