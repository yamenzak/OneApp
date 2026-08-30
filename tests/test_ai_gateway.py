"""One call, all the way through: hold, call, meter, settle.

The transport is faked at `requests.post` and the control plane at
`control_client.call`; everything between them is the real code, so what is
being checked is the sequence and what each step sends — including that a failed
call charges nothing and an unmeterable one is not billed at a guess.
"""

import json
import types

import pytest


@pytest.fixture
def gateway(stub_frappe, monkeypatch):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	stub_frappe.conf = {
		"oneapp_cf_account_id": "acct", "oneapp_ai_gateway": "oneapp",
		"oneapp_ai_gateway_token": "gwtok", "oneapp_tenant": "acme",
		"oneapp_cf_api_token": "cftok",
	}
	stub_frappe.log_error = lambda **kw: None
	stub_frappe.get_traceback = lambda: ""

	from oneapp.oneapp_core.ai import features, gateway as module, settings

	features.REGISTRY.clear()
	return types.SimpleNamespace(
		module=module, features=features, settings=settings, frappe=stub_frappe,
		monkeypatch=monkeypatch,
	)


CATALOGUE = [{
	"model_key": "google-ai-studio:flash", "display_name": "Flash",
	"provider": "google-ai-studio", "model_id": "gemini-3.7-flash",
	"capability": "Text Generation", "is_recommended": 1, "prices": [],
}, {
	"model_key": "workers-ai:flux", "display_name": "Flux",
	"provider": "workers-ai", "model_id": "@cf/black-forest-labs/flux-1-schnell",
	"capability": "Image Generation", "is_recommended": 1,
	"prices": [
		{"kind": "Output", "modality": "Image", "unit": "Tile"},
		{"kind": "Output", "modality": "Image", "unit": "Step"},
	],
}]


class Single:
	def __init__(self):
		self.ai_enabled = 1
		self.features = []
		self.credit_balance = 100

	def append(self, _f, values):
		self.features.append(types.SimpleNamespace(**values))
		return self.features[-1]

	def save(self, **kw):
		pass


class Response:
	def __init__(self, payload, status=200, headers=None):
		self._payload = payload
		self.status_code = status
		self.headers = headers or {"cf-aig-log-id": "log-1"}
		self.text = json.dumps(payload)

	def json(self):
		return self._payload


def wire(gw, response, capability="Text Generation", control=None):
	gw.frappe.get_single = lambda dt: Single()
	gw.frappe.db.get_single_value = lambda dt, f: (
		json.dumps(CATALOGUE) if f == "catalogue_json" else json.dumps([])
	)

	sent = {}

	def post(url, headers=None, json=None, timeout=None):
		sent.update(url=url, headers=headers, body=json)
		if isinstance(response, Exception):
			raise response
		return response

	gw.monkeypatch.setattr("oneapp.oneapp_core.ai.gateway.requests.post", post)

	calls = []
	answers = control or {}

	def control_call(method, payload=None):
		calls.append((method, payload))
		if method == "ai_reserve":
			return answers.get("ai_reserve", {"ok": True, "reservation": "CRES-1",
			                                  "ceiling": 2.0})
		return answers.get("ai_settle", {"ok": True, "credits": 0.47})

	gw.monkeypatch.setattr(
		"oneapp.oneapp_core.control_client.call", control_call)

	@gw.features.ai_feature("summary", label="Summary", capability=capability,
	                        system="You are our assistant.", max_output_tokens=400)
	def run(call, text=""):
		return call(text)

	return sent, calls, next(iter(gw.features.REGISTRY.values()))


GEMINI_OK = Response({
	"candidates": [{"content": {"parts": [{"text": "Two invoices are overdue."}]}}],
	"usageMetadata": {"promptTokenCount": 812, "candidatesTokenCount": 96},
})


def test_a_call_holds_then_settles(gateway):
	sent, calls, feature = wire(gateway, GEMINI_OK)
	result = gateway.module.call(feature, "Summarise this.")

	assert [method for method, _ in calls] == ["ai_reserve", "ai_settle"]
	assert result["text"] == "Two invoices are overdue."
	assert result["credits"] == 0.47


def test_the_hold_is_the_features_declared_ceiling(gateway):
	_, calls, feature = wire(gateway, GEMINI_OK)
	gateway.module.call(feature, "hi")

	reserve = calls[0][1]
	assert reserve["model"] == "google-ai-studio:flash"
	assert reserve["limits"]["max_output_tokens"] == 400


def test_what_is_settled_is_what_the_model_reported(gateway):
	"""Not a length, not a guess: the counts out of usageMetadata."""
	_, calls, feature = wire(gateway, GEMINI_OK)
	gateway.module.call(feature, "x" * 5000)

	units = {(u["kind"], u["count"]) for u in calls[1][1]["units"]}
	assert units == {("Input", 812), ("Output", 96)}


def test_the_gateway_log_id_is_carried_to_settlement(gateway):
	"""It is the only handle on Cloudflare's own view of the call."""
	_, calls, feature = wire(gateway, GEMINI_OK)
	gateway.module.call(feature, "hi")
	assert calls[1][1]["log_id"] == "log-1"


def test_our_prompt_goes_to_the_model_and_the_ceiling_goes_with_it(gateway):
	sent, _, feature = wire(gateway, GEMINI_OK)
	gateway.module.call(feature, "Summarise this.")

	assert sent["body"]["systemInstruction"]["parts"][0]["text"] == "You are our assistant."
	assert sent["body"]["generationConfig"]["maxOutputTokens"] == 400


def test_the_request_is_tagged_for_the_gateway_log(gateway):
	"""Spend has to be attributable per tenant and per feature without anyone
	reading a prompt."""
	sent, _, feature = wire(gateway, GEMINI_OK)
	gateway.module.call(feature, "hi")

	metadata = json.loads(sent["headers"]["cf-aig-metadata"])
	assert metadata["tenant"] == "acme"
	assert metadata["feature"] == feature.key


def test_no_provider_key_is_sent_when_the_gateway_holds_one(gateway):
	"""BYOK: the key stays at Cloudflare and a tenant site never has one."""
	sent, _, feature = wire(gateway, GEMINI_OK)
	gateway.module.call(feature, "hi")

	assert "x-goog-api-key" not in sent["headers"]
	assert sent["headers"]["cf-aig-authorization"] == "Bearer gwtok"


def test_a_failed_call_charges_nothing(gateway):
	_, calls, feature = wire(gateway, Response({"error": "upstream"}, status=502))

	with pytest.raises(gateway.module.AIError):
		gateway.module.call(feature, "hi")

	assert calls[1][0] == "ai_settle"
	assert calls[1][1]["release"] is True


def test_an_unreachable_gateway_charges_nothing(gateway):
	import requests

	_, calls, feature = wire(gateway, requests.RequestException("no route"))

	with pytest.raises(gateway.module.AIError):
		gateway.module.call(feature, "hi")

	assert calls[1][1]["release"] is True


def test_a_response_we_cannot_meter_is_not_billed_at_a_guess(gateway):
	"""The customer has their answer and we cannot say what it cost. Releasing
	the hold is the only honest move."""
	_, calls, feature = wire(gateway, Response({
		"candidates": [{"content": {"parts": [{"text": "hi"}]}}],
	}))

	result = gateway.module.call(feature, "hi")
	assert result["credits"] == 0
	assert calls[1][1]["release"] is True


def test_out_of_credits_stops_the_call_before_it_is_made(gateway):
	sent, calls, feature = wire(gateway, GEMINI_OK, control={
		"ai_reserve": {"ok": False, "reason": "insufficient_credits",
		               "available": 0.1, "needed": 2.0},
	})

	with pytest.raises(gateway.module.OutOfCredits):
		gateway.module.call(feature, "hi")

	assert not sent, "the provider was called anyway"


def test_a_disabled_feature_does_not_reach_the_provider(gateway):
	sent, calls, feature = wire(gateway, GEMINI_OK)
	gateway.frappe.db.get_single_value = lambda dt, f: (
		json.dumps(CATALOGUE) if f == "catalogue_json" else json.dumps(
			[{"key": feature.key, "status": "Suspended"}])
	)

	with pytest.raises(gateway.features.FeatureDisabled):
		gateway.module.call(feature, "hi")

	assert not sent
	assert not calls


def test_an_image_call_is_metered_from_what_we_asked_for(gateway):
	"""Flux returns a picture and no usage. The tiles and steps we sent are the
	same numbers Cloudflare bills against."""
	sent, calls, feature = wire(
		gateway, Response({"result": {"image": "base64..."}}),
		capability="Image Generation",
	)

	result = gateway.module.call(feature, "a cat", steps=4)

	assert result["images"] == ["base64..."]
	units = {(u["unit"], u["count"]) for u in calls[1][1]["units"]}
	assert units == {("Tile", 4), ("Step", 4)}
