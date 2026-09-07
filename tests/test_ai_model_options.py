"""What else a model takes, read off the provider's own documentation.

The declaration a tenant renders under its model picker is not typed by anyone:
providers add voices and drop them without telling us, and a hand-kept list is
wrong within a month for the same reason a hand-kept price is. So it is parsed,
from the two places a provider actually publishes it — Google's speech page and
Cloudflare's per-model input schema.

The fixture is the real page, saved on the day it was read. A parser tested
against a document somebody wrote to make it pass is a parser that has been
tested against itself.
"""

import pathlib

import pytest

from oneapp_control.ai import model_options

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def speech() -> str:
	return (FIXTURES / "gemini-speech.md").read_text()


# --------------------------------------------------------------------------- #
# Google, from the page
# --------------------------------------------------------------------------- #

def test_every_voice_google_publishes_is_read(speech):
	"""Thirty, which is what the page says there are, in its own words."""
	voices = model_options.google_voices(speech)

	assert len(voices) == 30
	assert "30 voice options" in speech
	assert {"value": "Zephyr", "label": "Zephyr — Bright"} in voices
	assert {"value": "Sulafat", "label": "Sulafat — Warm"} in voices


def test_a_voice_carries_what_google_says_it_sounds_like(speech):
	"""Thirty names and nothing else is a list nobody can choose from."""
	assert all(" — " in voice["label"] for voice in model_options.google_voices(speech))


def test_a_voice_goes_where_our_own_request_builder_puts_one(speech):
	"""The path is ours, not the provider's documentation shape.

	Google documents TTS on its Interactions API; `gateway._google_speech` calls
	`generateContent`, which nests the voice four objects down. The declaration
	has to say where *this* codebase writes it or the answer lands somewhere
	the provider ignores.
	"""
	declared = model_options.for_google("Text to Speech", speech)

	assert [option["key"] for option in declared] == ["voiceName"]
	assert declared[0]["path"] == (
		"generationConfig.speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName"
	)


def test_only_the_capability_google_publishes_a_list_for_gets_options(speech):
	assert model_options.for_google("Text Generation", speech) == []
	assert model_options.for_google("Image Generation", speech) == []


def test_a_page_that_stopped_saying_it_derives_nothing():
	"""Empty is "the page changed", and the caller keeps what it had."""
	assert model_options.for_google("Text to Speech", "# Speech\n\nNo table here.") == []


# --------------------------------------------------------------------------- #
# Cloudflare, from the schema
# --------------------------------------------------------------------------- #

SCHEMA = {"input": {"properties": {
	"prompt": {"type": "string"},
	"lang": {"type": "string", "enum": ["en", "fr"], "default": "en",
	         "description": "The speech language."},
	"steps": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4},
	"seed": {"type": "integer"},
	"enhance": {"type": "boolean", "default": False},
	"negative_prompt": {"type": "string"},
}}}


def test_a_list_a_number_and_a_switch_are_read_and_the_ask_is_not():
	declared = {o["key"]: o for o in model_options.from_workers_schema(SCHEMA)}

	assert declared["lang"]["type"] == "select"
	assert declared["lang"]["options"] == [
		{"value": "en", "label": "en"}, {"value": "fr", "label": "fr"},
	]
	assert declared["steps"]["type"] == "number"
	assert (declared["steps"]["min"], declared["steps"]["max"]) == (1, 8)
	assert declared["enhance"]["type"] == "switch"

	# The prompt is the ask. So is the negative prompt: a free string with no
	# shape is a text box that reaches a provider with no rules.
	assert "prompt" not in declared
	assert "negative_prompt" not in declared


def test_a_number_with_one_end_is_not_a_dial():
	"""A box that refuses numbers for a reason the workspace cannot see."""
	assert "seed" not in {o["key"] for o in model_options.from_workers_schema(SCHEMA)}


def test_a_payload_that_is_not_what_we_expected_derives_nothing():
	"""This reads someone else's API. The failure that matters is an exception
	in the middle of a catalogue sync, not a missing option."""
	assert model_options.from_workers_schema(None) == []
	assert model_options.from_workers_schema("{oh dear") == []
	assert model_options.from_workers_schema({"input": {"properties": []}}) == []
	assert model_options.from_workers_schema({"input": {"properties": {"a": "b"}}}) == []


def test_a_schema_given_as_json_reads_the_same_as_one_given_as_a_dict():
	import json
	assert (model_options.from_workers_schema(json.dumps(SCHEMA))
	        == model_options.from_workers_schema(SCHEMA))
