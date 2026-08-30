"""AI calls, routed through Cloudflare AI Gateway and charged for what they used.

Everything reaches a provider through one gateway. What that buys is caching,
retries, rate limits, spend limits and a per-request log tagged with the tenant —
and, since the provider keys are stored in the gateway itself (BYOK), tenant
sites never hold one. A site holds a gateway token; the key stays at Cloudflare.

A call runs in three steps, and the middle one is the only one that can fail
expensively:

  1. **Hold a ceiling.** The control plane prices the feature's declared limits
     and reserves that many credits. It is a cap, not a forecast — a hold, so
     two calls at once cannot both spend the last credit.
  2. **Make the call.**
  3. **Settle the actual.** The units the provider reported go back to the
     control plane, which prices them and commits. If the call failed, the hold
     is released and nothing is charged.

Note what does not happen: the gateway does not return a cost. Cloudflare puts
one in its own log and describes it as an estimate; the exact figure we can act
on is the usage the model itself reported, priced against the catalogue. The log
is still worth having — `cf-aig-log-id` comes back on every response and is what
reconciliation later compares us against.
"""

import json

import frappe
import requests

from oneapp.oneapp_core import control_client
from oneapp.oneapp_core.ai import features, meter, settings

TIMEOUT = 120

# Cloudflare returns this on every response. It is the handle for the log entry
# holding Cloudflare's own screen of the call.
LOG_ID_HEADER = "cf-aig-log-id"


class AIError(features.AIError):
	pass


class OutOfCredits(AIError):
	pass


def config() -> dict:
	conf = frappe.conf
	return {
		"account_id": conf.get("oneapp_cf_account_id"),
		"gateway": conf.get("oneapp_ai_gateway") or "oneapp",
		"gateway_token": conf.get("oneapp_ai_gateway_token"),
		# Only set where a key has not been stored in the gateway. With BYOK
		# this is absent and the gateway supplies the key it holds.
		"google_key": conf.get("oneapp_google_ai_key"),
		"cf_token": conf.get("oneapp_cf_api_token"),
		"tenant": conf.get("oneapp_tenant"),
	}


def is_configured() -> bool:
	c = config()
	return bool(c["account_id"] and c["gateway"])


def gateway_url(provider: str, path: str) -> str:
	c = config()
	base = f"https://gateway.ai.cloudflare.com/v1/{c['account_id']}/{c['gateway']}/{provider}"
	return f"{base}/{path.lstrip('/')}"


# --------------------------------------------------------------------------- #
# Building a request
#
# One builder per (provider, capability). Each returns (path, headers, body,
# extra request context the meter needs).
# --------------------------------------------------------------------------- #

def _google_headers() -> dict:
	c = config()
	headers = {"Content-Type": "application/json"}
	if c["google_key"]:
		headers["x-goog-api-key"] = c["google_key"]
	return headers


def _google_text(model, prompt, system, limits, request):
	body = {
		"contents": [{"role": "user", "parts": [{"text": prompt}]}],
		"generationConfig": {},
	}
	if limits.get("max_output_tokens"):
		body["generationConfig"]["maxOutputTokens"] = limits["max_output_tokens"]
	if system:
		body["systemInstruction"] = {"parts": [{"text": system}]}
	return f"v1beta/models/{model['model_id']}:generateContent", _google_headers(), body


def _google_image(model, prompt, system, limits, request):
	path, headers, body = _google_text(model, prompt, system, limits, request)
	body["generationConfig"]["responseModalities"] = ["TEXT", "IMAGE"]
	return path, headers, body


def _google_speech(model, prompt, system, limits, request):
	path, headers, body = _google_text(model, prompt, system, limits, request)
	body["generationConfig"]["responseModalities"] = ["AUDIO"]
	if request.get("voice"):
		body["generationConfig"]["speechConfig"] = {
			"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": request["voice"]}}
		}
	return path, headers, body


def _google_interaction(model, prompt, system, limits, request):
	"""Lyria and the rest of the Interactions API.

	A different endpoint shape from generateContent: the model is in the body
	rather than the path, and there is one `input` instead of a contents array.
	Our instructions are prepended to the prompt because the Interactions
	create call takes no separate system field.
	"""
	body = {
		"model": model["model_id"],
		"input": f"{system}\n\n{prompt}".strip() if system else prompt,
	}
	if request.get("response_format"):
		body["response_format"] = {"type": request["response_format"]}
	return "v1beta/interactions", _google_headers(), body


def _google_embed(model, prompt, system, limits, request):
	return (
		f"v1beta/models/{model['model_id']}:embedContent",
		_google_headers(),
		{"content": {"parts": [{"text": prompt}]}},
	)


def _workers_headers() -> dict:
	c = config()
	headers = {"Content-Type": "application/json"}
	if c["cf_token"]:
		headers["Authorization"] = f"Bearer {c['cf_token']}"
	return headers


def _workers_text(model, prompt, system, limits, request):
	messages = ([{"role": "system", "content": system}] if system else []) + [
		{"role": "user", "content": prompt}
	]
	body = {"messages": messages}
	if limits.get("max_output_tokens"):
		body["max_tokens"] = limits["max_output_tokens"]
	return model["model_id"], _workers_headers(), body


def _workers_embed(model, prompt, system, limits, request):
	return model["model_id"], _workers_headers(), {"text": [prompt]}


def _workers_image(model, prompt, system, limits, request):
	body = {"prompt": prompt, "steps": int(request.get("steps") or 4)}
	return model["model_id"], _workers_headers(), body


def _workers_speech(model, prompt, system, limits, request):
	body = {"text": prompt}
	if request.get("voice"):
		body["speaker"] = request["voice"]
	return model["model_id"], _workers_headers(), body


def _workers_transcribe(model, prompt, system, limits, request):
	audio = request.get("audio")
	if not audio:
		raise AIError("Speech to text needs `audio`.")
	return model["model_id"], _workers_headers(), {"audio": list(audio)}


BUILDERS = {
	("google-ai-studio", "Text Generation"): _google_text,
	("google-ai-studio", "Image Generation"): _google_image,
	("google-ai-studio", "Text to Speech"): _google_speech,
	("google-ai-studio", "Text Embeddings"): _google_embed,
	("google-ai-studio", "Audio Generation"): _google_interaction,
	("workers-ai", "Text Generation"): _workers_text,
	("workers-ai", "Text Embeddings"): _workers_embed,
	("workers-ai", "Image Generation"): _workers_image,
	("workers-ai", "Text to Speech"): _workers_speech,
	("workers-ai", "Speech to Text"): _workers_transcribe,
}


# --------------------------------------------------------------------------- #
# Reading a response
# --------------------------------------------------------------------------- #

def _interaction_result(payload: dict) -> dict:
	"""Pull the audio and the lyrics out of an Interaction.

	The SDKs expose `output_audio` and `output_text` as conveniences over a
	timeline of steps, and the docs say those conveniences can miss parts of an
	interleaved answer. So the steps are the source and the conveniences are the
	shortcut, not the other way round.
	"""
	text, audio = "", []

	for step in payload.get("steps") or []:
		if step.get("type") != "model_output":
			continue
		for block in step.get("content") or []:
			if block.get("type") == "audio" and block.get("data"):
				audio.append(block["data"])
			elif block.get("type") == "text":
				text += block.get("text") or ""

	if not audio:
		shortcut = payload.get("output_audio") or payload.get("outputAudio") or {}
		if shortcut.get("data"):
			audio.append(shortcut["data"])
	if not text:
		text = payload.get("output_text") or payload.get("outputText") or ""

	return {"audio": audio, "text": text, "images": []}


def _google_result(payload: dict, capability: str) -> dict:
	if capability == "Audio Generation":
		return _interaction_result(payload)

	text, images, audio = "", [], []
	for candidate in payload.get("candidates") or []:
		for part in (candidate.get("content") or {}).get("parts") or []:
			if part.get("text"):
				text += part["text"]
			inline = part.get("inlineData") or part.get("inline_data")
			if inline:
				mime = inline.get("mimeType") or inline.get("mime_type") or ""
				(audio if mime.startswith("audio/") else images).append(inline.get("data"))

	if capability == "Text Embeddings":
		return {"embedding": (payload.get("embedding") or {}).get("values") or []}
	return {"text": text, "images": images, "audio": audio}


def _workers_result(payload: dict, capability: str) -> dict:
	result = payload.get("result")
	if not isinstance(result, dict):
		return {"text": "", "raw": result}

	if capability == "Text Embeddings":
		return {"embedding": (result.get("data") or [[]])[0]}
	if capability == "Image Generation":
		return {"images": [result["image"]] if result.get("image") else [], "text": ""}
	if capability == "Text to Speech":
		return {"audio": [result.get("audio")] if result.get("audio") else [], "text": ""}
	return {"text": result.get("response") or result.get("text") or ""}


# --------------------------------------------------------------------------- #
# One call
# --------------------------------------------------------------------------- #

class Result(dict):
	"""A dict, so callers can index it, with the useful bits as attributes."""

	def __getattr__(self, name):
		try:
			return self[name]
		except KeyError as e:
			raise AttributeError(name) from e


def caller(feature: features.Feature):
	"""The callable the decorator injects. Closes over the feature's policy."""

	def run(prompt: str = "", **request) -> Result:
		return call(feature, prompt, **request)

	run.feature = feature
	return run


def call(feature: features.Feature, prompt: str = "", **request) -> Result:
	if not is_configured():
		raise AIError("AI gateway is not configured in site_config.json.")

	if not settings.is_enabled(feature):
		raise features.FeatureDisabled(f"{feature.label} is switched off for this workspace.")

	model_key = settings.model_for(feature)
	model = next((m for m in settings.catalogue() if m["model_key"] == model_key), None)
	if not model:
		raise AIError(f"{model_key} is not in this workspace's catalogue.")

	builder = BUILDERS.get((model["provider"], feature.capability))
	if not builder:
		raise AIError(
			f"No request shape for {feature.capability} on {model['provider']}."
		)

	limits = settings.limits(feature)
	system = settings.system_prompt(feature)

	held = control_client.call("ai_reserve", {
		"feature": feature.key, "model": model_key, "limits": limits,
	})
	if not held.get("ok"):
		if held.get("reason") == "insufficient_credits":
			raise OutOfCredits(
				f"{held.get('needed')} credits needed, {held.get('available')} available."
			)
		raise AIError(f"Could not reserve credits: {held.get('message') or held.get('reason')}")

	reservation = held["reservation"]

	try:
		payload, log_id = _execute(model, feature, builder, prompt, system, limits, request)
	except Exception as e:
		_release(reservation, str(e)[:140])
		raise

	try:
		units = _meter(model, feature, request, payload, prompt)
	except meter.Unmetered as e:
		# The customer has their answer and we cannot say what it cost. Release
		# rather than invent a figure; the control plane records the gap.
		_settle(reservation, model_key, feature, [], log_id, unmetered=str(e))
		frappe.log_error(title="AI call could not be metered", message=str(e))
		units = []
		settled = {"credits": 0}
	else:
		settled = _settle(reservation, model_key, feature, units, log_id)

	reader = _google_result if model["provider"] == "google-ai-studio" else _workers_result
	result = Result(reader(payload, feature.capability))
	result.update({
		"model": model_key,
		"provider": model["provider"],
		"feature": feature.key,
		"units": units,
		"credits": settled.get("credits") or 0,
		"log_id": log_id,
	})
	return result


def _execute(model, feature, builder, prompt, system, limits, request):
	c = config()
	path, headers, body = builder(model, prompt, system, limits, request)
	url = gateway_url(model["provider"], path)

	if c["gateway_token"]:
		headers["cf-aig-authorization"] = f"Bearer {c['gateway_token']}"
	# Tags the gateway log, which is what makes spend attributable per tenant and
	# per feature without reading anyone's prompt.
	headers["cf-aig-metadata"] = json.dumps(
		{"tenant": c["tenant"] or "", "feature": feature.key}
	)

	try:
		response = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
	except requests.RequestException as e:
		raise AIError(f"AI gateway unreachable: {e}") from e

	log_id = response.headers.get(LOG_ID_HEADER)

	if response.status_code != 200:
		raise AIError(f"AI gateway {response.status_code}: {response.text[:300]}")

	try:
		return response.json(), log_id
	except ValueError as e:
		raise AIError("AI gateway returned a body that is not JSON.") from e


def _meter(model, feature, request, payload, prompt):
	"""Counts for the models that report none back.

	Counting the request is not estimating the response: the picture size and
	step count we asked for, the length of the audio we sent, the number of
	characters we asked it to speak and the number of generations we asked for
	are the same numbers the provider bills against.

	Set unconditionally because the meters only reach for them when the model
	has no usage to report and actually holds a rate in that unit.
	"""
	counted = dict(request)
	counted.setdefault("outputs", 1)
	if feature.capability == "Image Generation":
		counted.setdefault("images", 1)
	if feature.capability == "Text to Speech":
		counted.setdefault("characters", len(prompt or ""))

	if model["provider"] == "google-ai-studio":
		return meter.gemini(payload, model, counted)
	return meter.workers(payload, model, counted)


def _settle(reservation, model_key, feature, units, log_id, unmetered=""):
	payload = {
		"reservation": reservation,
		"model": model_key,
		"feature": feature.key,
		"units": units,
		"log_id": log_id,
	}
	if unmetered:
		payload["release"] = True
		payload["reason"] = f"unmetered: {unmetered[:120]}"

	try:
		return control_client.call("ai_settle", payload)
	except control_client.ControlPlaneError:
		# The work is done and the customer has their answer. A stuck reservation
		# is swept and released by the control plane rather than failing here.
		frappe.log_error(title="AI settlement failed", message=frappe.get_traceback())
		return {"credits": 0}


def _release(reservation, reason):
	try:
		control_client.call("ai_settle", {"reservation": reservation, "release": True,
		                                  "reason": reason})
	except control_client.ControlPlaneError:
		frappe.log_error(title="AI credit release failed", message=frappe.get_traceback())


@frappe.whitelist()
def ask(feature: str, prompt: str) -> dict:
	"""SPA entry point. Runs a declared feature and nothing else.

	Deliberately not a general "call a model" endpoint: a feature is where the
	prompt, the ceiling and the workspace's permission to run it all live, and
	an endpoint that takes a model name has none of them.
	"""
	spec = features.get(feature)
	if not spec:
		frappe.throw(f"No AI feature named {feature}.")

	try:
		return dict(call(spec, prompt))
	except OutOfCredits as e:
		return {"ok": False, "reason": "insufficient_credits", "message": str(e)}
	except features.FeatureDisabled as e:
		return {"ok": False, "reason": "disabled", "message": str(e)}
