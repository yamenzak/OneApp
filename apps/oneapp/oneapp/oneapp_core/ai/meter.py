"""Counting what a call used, from what the provider said it used.

This is the file that makes "never estimate" true. Every number here is either
returned by the provider or is a parameter we ourselves sent; nothing is derived
from the length of a string.

The two providers report differently, and the difference is the whole reason the
price schema is unit-aware:

  * **Gemini counts everything in tokens, by modality.** `usageMetadata` carries
    `promptTokensDetails`, `cacheTokensDetails` and `candidatesTokensDetails`,
    each a list of (modality, tokenCount). Generated pictures and generated
    speech come back as IMAGE and AUDIO token counts, so a multimodal call is
    exactly meterable with no special case.

  * **Workers AI reports tokens for text and nothing at all for the rest.** Flux
    returns a base64 picture; Whisper returns a transcript. Those are billed per
    512x512 tile, per diffusion step, per audio minute or per thousand input
    characters — all of which are things *we* set on the way in. Counting the
    request is not estimating the response; it is reading the same number
    Cloudflare will bill against.

When neither is possible the call is unmetered and this raises. The alternative
is inventing a figure and charging for it.
"""

import math

# Gemini's modality enum -> ours.
MODALITIES = {
	"TEXT": "Text",
	"IMAGE": "Image",
	"AUDIO": "Audio",
	"VIDEO": "Video",
	"DOCUMENT": "File",
	"MODALITY_UNSPECIFIED": "Text",
}

# A 512x512 tile is Cloudflare's unit for image work.
TILE = 512


class Unmetered(Exception):
	"""The provider returned no usage and the request implies no count."""


def _line(kind, modality, unit, count):
	return {"kind": kind, "modality": modality, "unit": unit, "count": int(count)}


def _details(rows) -> dict[str, int]:
	out: dict[str, int] = {}
	for row in rows or []:
		modality = MODALITIES.get(str(row.get("modality") or "").upper(), "Text")
		out[modality] = out.get(modality, 0) + int(row.get("tokenCount") or 0)
	return out


def gemini(payload: dict, model: dict | None = None,
           request: dict | None = None) -> list[dict]:
	usage = payload.get("usageMetadata") or {}
	if not usage:
		# Not every Google model counts tokens. Lyria answers on the
		# Interactions API and is billed per song, so there is nothing to count
		# in the response — the number of generations we asked for is the same
		# number Google bills, and `from_request` reads it off the model's own
		# rate rows.
		units = from_request(model or {}, request or {})
		if units:
			return units
		raise Unmetered("Gemini returned no usageMetadata.")

	units = []
	cached = _details(usage.get("cacheTokensDetails"))
	prompt = _details(usage.get("promptTokensDetails"))
	output = _details(usage.get("candidatesTokensDetails"))

	# promptTokenCount is documented as the *total effective* prompt, cached part
	# included. Billing both lines as written would charge the cached tokens
	# twice, once at the full rate.
	if not prompt:
		total = int(usage.get("promptTokenCount") or 0)
		prompt = {"Text": total} if total else {}
	for modality, count in prompt.items():
		count -= cached.get(modality, 0)
		if count > 0:
			units.append(_line("Input", modality, "Token", count))

	for modality, count in cached.items():
		if count > 0:
			units.append(_line("Cached Input", modality, "Token", count))

	if not output:
		total = int(usage.get("candidatesTokenCount") or 0)
		output = {"Text": total} if total else {}
	for modality, count in output.items():
		if count > 0:
			units.append(_line("Output", modality, "Token", count))

	# Thinking tokens bill at the output rate and are counted separately, so they
	# are absent from candidatesTokensDetails and would otherwise be free.
	thoughts = int(usage.get("thoughtsTokenCount") or 0)
	if thoughts:
		units.append(_line("Output", "Text", "Token", thoughts))

	tool_use = int(usage.get("toolUsePromptTokenCount") or 0)
	if tool_use:
		units.append(_line("Input", "Text", "Token", tool_use))

	if not units:
		raise Unmetered("Gemini reported zero tokens in every modality.")
	return units


def workers(payload: dict, model: dict, request: dict) -> list[dict]:
	"""Workers AI: tokens when it reports them, the request when it does not."""
	result = payload.get("result")
	usage = (result or {}).get("usage") if isinstance(result, dict) else None

	units = []
	if usage:
		if int(usage.get("prompt_tokens") or 0):
			units.append(_line("Input", "Text", "Token", usage["prompt_tokens"]))
		if int(usage.get("completion_tokens") or 0):
			units.append(_line("Output", "Text", "Token", usage["completion_tokens"]))
		if units:
			return units

	units = from_request(model, request)
	if not units:
		raise Unmetered(
			f"{model.get('model_id')} reported no usage and the request carried "
			"nothing countable."
		)
	return units


def from_request(model: dict, request: dict) -> list[dict]:
	"""Counts we set ourselves, in whichever units this model is billed in.

	Driven by the model's own price rows rather than by its capability: what
	Cloudflare charges for is the only thing worth counting, and it differs
	between two models that do the same job.
	"""
	rates = {(p["kind"], p["modality"], p["unit"]) for p in model.get("prices") or []}
	units = []

	images = int(request.get("images") or 0)
	if images:
		width = int(request.get("width") or 1024)
		height = int(request.get("height") or 1024)
		tiles = math.ceil(width / TILE) * math.ceil(height / TILE) * images

		if ("Output", "Image", "Tile") in rates:
			units.append(_line("Output", "Image", "Tile", tiles))
		if ("Output", "Image", "Step") in rates:
			units.append(_line("Output", "Image", "Step",
			                   int(request.get("steps") or 4) * images))
		if ("Output", "Image", "Image") in rates:
			units.append(_line("Output", "Image", "Image", images))

	seconds = float(request.get("audio_seconds") or 0)
	if seconds:
		# Providers bill a started minute, so this rounds up rather than down.
		for kind in ("Input", "Output"):
			if (kind, "Audio", "Minute") in rates:
				units.append(_line(kind, "Audio", "Minute", math.ceil(seconds / 60)))
			elif (kind, "Audio", "Second") in rates:
				units.append(_line(kind, "Audio", "Second", math.ceil(seconds)))

	# Models billed per generation rather than per unit of what they generate.
	# The count is what we asked for, which is what the provider charges for.
	generations = int(request.get("outputs") or 0)
	if generations:
		for kind, modality, unit in rates:
			if kind == "Output" and unit == "Request":
				units.append(_line("Output", modality, "Request", generations))

	characters = int(request.get("characters") or 0)
	if characters:
		for kind in ("Input", "Output"):
			if (kind, "Text", "Character") in rates:
				units.append(_line(kind, "Text", "Character", characters))

	if ("Input", "Image", "Image") in rates and int(request.get("input_images") or 0):
		units.append(_line("Input", "Image", "Image", request["input_images"]))

	return units
