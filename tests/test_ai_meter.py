"""Counting what a call used.

Every number the meter produces is either one the provider returned or one we
sent. Nothing is derived from the length of a string, and when neither source
exists the meter raises rather than inventing a figure — that refusal is the
behaviour most of these tests are pinning.
"""

import pytest


@pytest.fixture
def meter():
	from oneapp.oneapp_core.ai import meter as module

	return module


def units_by(units, kind, modality):
	return next((u for u in units if u["kind"] == kind and u["modality"] == modality), None)


# --------------------------------------------------------------------------- #
# Gemini: everything, including pictures and speech, comes back as tokens
# --------------------------------------------------------------------------- #

def test_a_plain_text_call_is_metered_from_the_reported_tokens(meter):
	units = meter.gemini({"usageMetadata": {
		"promptTokenCount": 812,
		"candidatesTokenCount": 96,
		"totalTokenCount": 908,
	}})
	assert units_by(units, "Input", "Text")["count"] == 812
	assert units_by(units, "Output", "Text")["count"] == 96


def test_generated_pictures_are_metered_as_image_tokens(meter):
	"""A 1024x1024 image is 1,120 tokens, which is how Google bills it."""
	units = meter.gemini({"usageMetadata": {
		"promptTokensDetails": [{"modality": "TEXT", "tokenCount": 20}],
		"candidatesTokensDetails": [
			{"modality": "TEXT", "tokenCount": 8},
			{"modality": "IMAGE", "tokenCount": 1120},
		],
	}})
	assert units_by(units, "Output", "Image")["count"] == 1120
	assert units_by(units, "Output", "Text")["count"] == 8


def test_generated_speech_is_metered_as_audio_tokens(meter):
	units = meter.gemini({"usageMetadata": {
		"promptTokensDetails": [{"modality": "TEXT", "tokenCount": 40}],
		"candidatesTokensDetails": [{"modality": "AUDIO", "tokenCount": 3000}],
	}})
	assert units_by(units, "Output", "Audio")["count"] == 3000


def test_cached_tokens_are_not_also_charged_at_the_full_rate(meter):
	"""promptTokenCount is documented as the total effective prompt, cached part
	included. Billing both lines as written charges the cache twice."""
	units = meter.gemini({"usageMetadata": {
		"promptTokenCount": 5000,
		"cachedContentTokenCount": 4000,
		"promptTokensDetails": [{"modality": "TEXT", "tokenCount": 5000}],
		"cacheTokensDetails": [{"modality": "TEXT", "tokenCount": 4000}],
		"candidatesTokenCount": 10,
	}})
	assert units_by(units, "Input", "Text")["count"] == 1000
	assert units_by(units, "Cached Input", "Text")["count"] == 4000


def test_thinking_tokens_are_not_free(meter):
	"""They bill at the output rate and are absent from candidatesTokensDetails,
	so a meter that only reads that list gives reasoning away."""
	units = meter.gemini({"usageMetadata": {
		"promptTokenCount": 10,
		"candidatesTokensDetails": [{"modality": "TEXT", "tokenCount": 50}],
		"thoughtsTokenCount": 900,
	}})
	assert sum(u["count"] for u in units if u["kind"] == "Output") == 950


def test_a_response_with_no_usage_is_refused(meter):
	with pytest.raises(meter.Unmetered):
		meter.gemini({"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})


# --------------------------------------------------------------------------- #
# Workers AI: tokens where it reports them, the request where it does not
# --------------------------------------------------------------------------- #

FLUX = {
	"model_id": "@cf/black-forest-labs/flux-1-schnell",
	"prices": [
		{"kind": "Output", "modality": "Image", "unit": "Tile"},
		{"kind": "Output", "modality": "Image", "unit": "Step"},
	],
}
WHISPER = {
	"model_id": "@cf/openai/whisper",
	"prices": [{"kind": "Input", "modality": "Audio", "unit": "Minute"}],
}
AURA = {
	"model_id": "@cf/deepgram/aura-2-en",
	"prices": [{"kind": "Input", "modality": "Text", "unit": "Character"}],
}
LLAMA = {"model_id": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "prices": []}


def test_text_generation_uses_the_reported_usage(meter):
	units = meter.workers(
		{"result": {"response": "hi", "usage": {"prompt_tokens": 30, "completion_tokens": 7}}},
		LLAMA, {},
	)
	assert units_by(units, "Input", "Text")["count"] == 30
	assert units_by(units, "Output", "Text")["count"] == 7


def test_an_image_is_counted_in_the_units_it_is_billed_in(meter):
	"""Flux returns a base64 picture and no usage at all. A 1024x1024 image is
	four 512x512 tiles, and the step count is the one we sent."""
	units = meter.workers({"result": {"image": "..."}}, FLUX,
	                      {"images": 1, "steps": 4})
	assert units_by(units, "Output", "Image")["count"] == 4          # tiles
	assert [u for u in units if u["unit"] == "Step"][0]["count"] == 4


def test_a_larger_image_costs_more_tiles(meter):
	small = meter.workers({"result": {"image": "."}}, FLUX, {"images": 1, "steps": 4})
	large = meter.workers({"result": {"image": "."}}, FLUX,
	                      {"images": 1, "steps": 4, "width": 2048, "height": 2048})
	tiles = lambda u: [x for x in u if x["unit"] == "Tile"][0]["count"]  # noqa: E731
	assert tiles(large) == tiles(small) * 4


def test_transcription_is_counted_from_the_audio_we_sent(meter):
	units = meter.workers({"result": {"text": "..."}}, WHISPER, {"audio_seconds": 90})
	# A started minute is a billed minute.
	assert units_by(units, "Input", "Audio")["count"] == 2


def test_synthesis_is_counted_from_the_characters_we_asked_for(meter):
	units = meter.workers({"result": {"audio": "..."}}, AURA, {"characters": 1500})
	assert units_by(units, "Input", "Text")["count"] == 1500


def test_a_model_that_reports_nothing_and_counts_nothing_is_refused(meter):
	"""The whole point: no usage and no countable request means we cannot say
	what it cost, so we do not say."""
	with pytest.raises(meter.Unmetered):
		meter.workers({"result": {"image": "..."}}, FLUX, {})


def test_units_follow_the_models_rates_not_its_capability(meter):
	"""Two models that do the same job can be billed differently, so the price
	rows decide what gets counted."""
	per_image = {"model_id": "x", "prices": [
		{"kind": "Output", "modality": "Image", "unit": "Image"}]}
	units = meter.workers({"result": {"image": "."}}, per_image, {"images": 3, "steps": 8})
	assert [(u["unit"], u["count"]) for u in units] == [("Image", 3)]


# --------------------------------------------------------------------------- #
# Models billed per generation
# --------------------------------------------------------------------------- #

LYRIA = {
	"model_id": "lyria-3-pro-preview",
	"prices": [{"kind": "Output", "modality": "Audio", "unit": "Request"}],
}


def test_a_song_is_counted_as_one_generation(meter):
	"""Lyria answers on the Interactions API and reports no tokens. It bills per
	song whatever the length, and the number of songs is what we asked for."""
	units = meter.gemini({"steps": [{"type": "model_output", "content": [
		{"type": "audio", "data": "..."}]}]}, LYRIA, {"outputs": 1})

	assert units == [{"kind": "Output", "modality": "Audio", "unit": "Request",
	                  "count": 1}]


def test_two_generations_cost_two(meter):
	units = meter.gemini({}, LYRIA, {"outputs": 2})
	assert units[0]["count"] == 2


def test_a_token_model_still_meters_from_its_usage(meter):
	"""The fallback must not shadow the reported counts where there are some."""
	units = meter.gemini(
		{"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4}},
		LYRIA, {"outputs": 9},
	)
	assert {u["unit"] for u in units} == {"Token"}


def test_a_generation_count_without_a_rate_for_it_is_refused(meter):
	"""`outputs` is set on every call, so it must only produce a charge where
	the model actually holds a per-request rate."""
	with pytest.raises(meter.Unmetered):
		meter.gemini({}, {"model_id": "x", "prices": []}, {"outputs": 1})
