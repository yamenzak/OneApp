"""What else a model takes, read off the provider's own documentation.

`AI Model.options_json` is the declaration a tenant renders under its model
picker — a voice, a language, a size. Typed by hand it is wrong within a month
for the same reason a hand-typed price is: providers add voices and drop them
without telling anyone, and the way you find out is a customer asking why the
list is short.

So it is derived, from the same kind of source the prices come from. Google
publishes its voice list and its language list as tables in the speech
generation page; Cloudflare returns a JSON Schema of each model's input on the
endpoint the sync already calls. Neither is a guess, and where a provider
publishes nothing this derives nothing rather than inventing a list.

Two rules, both the same rule the price sync already follows:

* **An operator's list is never overwritten.** `options_locked` says a human
  decided, and a human beats a parser.
* **A model nothing could be derived for keeps whatever it had.** An empty
  answer from a parser is "the page changed", not "the model lost its voices".
"""

import json
import re

#: Where each capability's options go inside the request our gateway builds.
#: Not the provider's documentation shape — *ours* — because the declaration is
#: read by `oneapp_core/ai/gateway.py`, which already decides which endpoint and
#: which body a capability gets. See `_google_speech` there for this one.
GOOGLE_VOICE_PATH = "generationConfig.speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName"

#: `| **Zephyr** -- *Bright* | **Puck** -- *Upbeat* | …`, three to a row.
_VOICE = re.compile(r"\*\*([A-Z][a-z]+)\*\*\s*--\s*\*([^*]+)\*")


def google_voices(doc: str) -> list[dict]:
	"""The prebuilt voices, from the speech generation page.

	Each is a name and the one word Google uses to describe it — "Bright",
	"Breezy" — which is worth carrying, because thirty names and nothing else is
	a list nobody can choose from.
	"""
	seen, out = set(), []
	for name, described in _VOICE.findall(doc):
		if name in seen:
			continue
		seen.add(name)
		out.append({"value": name, "label": f"{name} — {described.strip()}"})
	return out


def for_google(capability: str, speech_doc: str) -> list[dict]:
	"""What a Google model of this capability lets a workspace decide.

	Only Text to Speech for now, and only because it is the only one Google
	documents as a list rather than as prose. A number a page describes in a
	sentence is a number somebody has to read and type — see `options_locked`.
	"""
	if capability != "Text to Speech":
		return []

	voices = google_voices(speech_doc)
	if not voices:
		return []

	# Voice and nothing else. The same page lists forty-odd languages, and they
	# are not a setting: Google says the TTS models detect the input language
	# themselves, so a picker for it would be a control that changes nothing.
	return [{
		"key": "voiceName",
		"label": "Voice",
		"type": "select",
		"path": GOOGLE_VOICE_PATH,
		"default": voices[0]["value"],
		"options": voices,
	}]


#: Input properties that are the ask itself rather than a setting about it.
#: A workspace does not choose the prompt.
NOT_A_SETTING = frozenset({
	"prompt", "text", "input", "messages", "image", "image_b64", "audio",
	"video", "input_text", "system", "instructions", "guidance_prompt",
	"raw", "stream", "functions", "tools", "response_format", "mask",
})


def from_workers_schema(schema, capability: str = "") -> list[dict]:
	"""What a Workers AI model declares it takes, from its own input schema.

	Cloudflare returns a JSON Schema per model on the endpoint the sync already
	calls for the model list. Only the properties that are settings are kept,
	and only the ones a control can actually draw: something with an `enum` is a
	list, a number with both ends is a dial, a boolean is a switch. A free
	string with no shape is left out — a text box that reaches a provider with
	no rules is a support ticket, not a setting.

	Defensive throughout: this reads a payload from someone else's API, and the
	failure that matters is a shape we did not expect turning a catalogue sync
	into an exception.
	"""
	if isinstance(schema, str):
		try:
			schema = json.loads(schema)
		except ValueError:
			return []
	if not isinstance(schema, dict):
		return []

	properties = ((schema.get("input") or schema).get("properties") or {})
	if not isinstance(properties, dict):
		return []

	out = []
	for key, rule in properties.items():
		if key in NOT_A_SETTING or not isinstance(rule, dict):
			continue
		option = _from_property(key, rule)
		if option:
			out.append(option)
	return out


def _from_property(key: str, rule: dict) -> dict | None:
	label = key.replace("_", " ").strip().capitalize()
	described = str(rule.get("description") or "")[:200]
	kind = rule.get("type")

	if isinstance(rule.get("enum"), list) and rule["enum"]:
		return {
			"key": key, "label": label, "type": "select", "help": described,
			"default": rule.get("default", rule["enum"][0]),
			"options": [{"value": str(v), "label": str(v)} for v in rule["enum"]],
		}

	if kind in ("number", "integer"):
		low, high = rule.get("minimum"), rule.get("maximum")
		# Both ends or none: a dial with one stop is a box that refuses numbers
		# for a reason the workspace cannot see.
		if low is None or high is None:
			return None
		return {
			"key": key, "label": label, "type": "number", "help": described,
			"default": rule.get("default"), "min": low, "max": high,
		}

	if kind == "boolean":
		return {
			"key": key, "label": label, "type": "switch", "help": described,
			"default": bool(rule.get("default")),
		}

	return None
