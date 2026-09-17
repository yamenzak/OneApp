"""One shape for a conversation, and the two provider shapes it becomes.

A transcript here is a list of plain dicts:

    {"role": "user",      "content": "how many open quotations?"}
    {"role": "assistant", "content": "",  "tool_calls": [
        {"id": "call_0", "name": "count_records", "arguments": {...}}]}
    {"role": "tool",      "tool_call_id": "call_0", "name": "count_records",
                          "content": "{\\"count\\": 4}"}

which is OpenAI's shape with the arguments left as a dict rather than a string
inside a string. A user turn may also carry

    {"role": "user", "content": "what does this say?", "attachments": [
        {"mime": "image/png", "data": "<base64>"}]}

which is how a picture reaches a model at all — see `Attachments`, below. It is ours because it is what gets stored: a session is read
back turn by turn, and JSON nested inside JSON is a thing to remember to decode
in every reader.

Gemini's shape is genuinely different rather than a renaming — the assistant is
`model`, a tool result is a *user* turn carrying a `functionResponse`, and there
is no id on a call at all, so ids are synthesized on the way back. Workers AI
speaks OpenAI, so that direction is nearly a pass-through.

## Attachments

A message may carry bytes as well as words, and until there was something to
attach it could not: both writers emitted text parts and nothing else, so a
workspace could pick a vision model and have no way to put a picture in front
of it. The shape is one key, `attachments`, on the turn the bytes belong to —
not a message of its own, because "look at this and tell me what it says" is
one thing a person said and splitting it would be two turns the model has to
put back together.

`data` is base64 and `mime` is the type the provider is told, and both writers
inline it rather than sending a URL: a presigned link is a second round trip
from somebody else's network into a file that is private, and the one thing
worse than paying for the bytes twice is a model that cannot fetch them and
says so vaguely.

Neither direction is where permission lives. A transcript is text and bytes;
what a tool may read is decided in `chat/toolbox.py`, before any of this.
"""

import json

#: The keys Gemini's `functionDeclarations` accepts in a parameter schema.
#: Anything else — `additionalProperties` above all, which JSON Schema tooling
#: emits by habit — is rejected with a 400 that names no field.
GEMINI_SCHEMA_KEYS = {
	"type", "description", "properties", "required", "items", "enum", "format",
	"nullable", "anyOf",
}


# --------------------------------------------------------------------------- #
# Out: our transcript -> a provider's request
# --------------------------------------------------------------------------- #

def to_google(messages: list[dict]) -> list[dict]:
	"""`contents`, with tool results folded into user turns.

	Consecutive parts are not merged. Gemini accepts a run of same-role turns,
	and merging them would lose which call each result answered in the one case
	where several tools ran at once.
	"""
	contents = []
	for message in messages:
		role = message.get("role")

		if role == "tool":
			contents.append({
				"role": "user",
				"parts": [{"functionResponse": {
					"name": message.get("name") or "tool",
					# An object, always: Gemini rejects a bare string here, and
					# a tool that returned JSON has already been serialized.
					"response": {"result": message.get("content") or ""},
				}}],
			})
			continue

		parts = []
		if message.get("content"):
			parts.append({"text": message["content"]})
		# After the words, which is the order that reads best to a model: the
		# question, then the thing it is about.
		for one in _attached(message):
			parts.append({"inlineData": {"mimeType": one["mime"], "data": one["data"]}})
		for call in message.get("tool_calls") or []:
			parts.append({"functionCall": {
				"name": call["name"],
				"args": call.get("arguments") or {},
			}})
		if not parts:
			continue

		contents.append({
			"role": "model" if role == "assistant" else "user",
			"parts": parts,
		})
	return contents


def to_google_tools(declared: list[dict]) -> list[dict]:
	return [{"functionDeclarations": [
		{
			"name": one["function"]["name"],
			"description": one["function"]["description"],
			"parameters": gemini_schema(one["function"]["parameters"]),
		}
		for one in declared
	]}]


def gemini_schema(schema):
	"""The same schema with the keys Gemini does not know dropped, recursively.

	`properties` is the trap: its keys are the tool's argument names, not schema
	words, so filtering them the way the level above is filtered deletes every
	argument and sends a tool that takes nothing. The values under it are
	schemas and are filtered; the names are copied through.
	"""
	if isinstance(schema, list):
		return [gemini_schema(one) for one in schema]
	if not isinstance(schema, dict):
		return schema

	out = {}
	for key, value in schema.items():
		if key not in GEMINI_SCHEMA_KEYS:
			continue
		if key == "properties" and isinstance(value, dict):
			out[key] = {name: gemini_schema(one) for name, one in value.items()}
		else:
			out[key] = gemini_schema(value)
	return out


def _attached(message: dict) -> list[dict]:
	"""The bytes on this turn, as `{mime, data}`, or nothing.

	Defensive about the shape because a caller assembling one of these is
	reading a file off disk and a half-read file is an empty string: a part
	with no data is a 400 from the provider naming nothing.
	"""
	return [
		one for one in (message.get("attachments") or [])
		if isinstance(one, dict) and one.get("data") and one.get("mime")
	]


def to_openai(messages: list[dict]) -> list[dict]:
	"""The same transcript with arguments re-encoded as the string OpenAI wants.

	A turn carrying bytes becomes the multi-part `content` array OpenAI added
	for vision — a text part and an `image_url` per attachment, the URL being a
	`data:` URI rather than a link. Every other turn keeps its plain string,
	because a model handed `[{"type": "text", …}]` for a one-line question is a
	model being handed a shape for no reason.
	"""
	out = []
	for message in messages:
		attached = _attached(message)
		if attached:
			out.append({
				"role": message.get("role") or "user",
				"content": [
					*([{"type": "text", "text": message["content"]}]
					  if message.get("content") else []),
					*[{"type": "image_url",
					   "image_url": {"url": f"data:{one['mime']};base64,{one['data']}"}}
					  for one in attached],
				],
			})
			continue
		if message.get("role") != "assistant" or not message.get("tool_calls"):
			out.append({k: v for k, v in message.items()
			            if k not in ("tool_calls", "attachments")})
			continue
		out.append({
			"role": "assistant",
			"content": message.get("content") or "",
			"tool_calls": [{
				"id": call["id"],
				"type": "function",
				"function": {
					"name": call["name"],
					"arguments": json.dumps(call.get("arguments") or {}),
				},
			} for call in message["tool_calls"]],
		})
	return out


# --------------------------------------------------------------------------- #
# Back: a provider's response -> text and calls
# --------------------------------------------------------------------------- #

def from_google(payload: dict) -> tuple[str, list[dict]]:
	text, calls = "", []
	for candidate in payload.get("candidates") or []:
		for part in (candidate.get("content") or {}).get("parts") or []:
			if part.get("text"):
				text += part["text"]
			called = part.get("functionCall")
			if called:
				calls.append({
					# Gemini names no id. The index is one, and it only has to
					# be unique within the turn that produced it.
					"id": f"call_{len(calls)}",
					"name": called.get("name") or "",
					"arguments": called.get("args") or {},
				})
	return text, calls


def from_openai(result: dict) -> tuple[str, list[dict]]:
	"""Workers AI, which reports a call in either of two shapes.

	Its OpenAI-compatible models return `{id, function: {name, arguments}}` with
	the arguments as a string; its own models return `{name, arguments}` with
	the arguments already parsed. Both arrive on the same field.
	"""
	text = result.get("response") or result.get("text") or ""
	calls = []
	for raw in result.get("tool_calls") or []:
		inner = raw.get("function") or raw
		arguments = inner.get("arguments")
		if isinstance(arguments, str):
			try:
				arguments = json.loads(arguments)
			except (TypeError, ValueError):
				arguments = {}
		calls.append({
			"id": raw.get("id") or f"call_{len(calls)}",
			"name": inner.get("name") or "",
			"arguments": arguments or {},
		})
	return text, calls
