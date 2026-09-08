"""What else a model takes, and who is allowed to answer it.

A model that reads text aloud has a language and a pace. The list is the
provider's, so it arrives with the catalogue rather than living in our code —
which makes the interesting cases the ones where the declaration and the answer
disagree: an answer to an option the model no longer has, a value outside a
range, a declaration that is the wrong shape because the control plane is a
version ahead or behind.
"""

import json
import types

import pytest


@pytest.fixture
def options(stub_frappe):
	from oneapp.onespace.ai import options as module

	return module


TTS = {
	"model_key": "workers-ai:melotts",
	"capability": "Text to Speech",
	"options": [
		{"key": "lang", "label": "Language", "type": "select", "default": "EN",
		 "options": [{"value": "EN", "label": "English"},
		             {"value": "ES", "label": "Spanish"}]},
		{"key": "speed", "label": "Speed", "type": "number",
		 "default": 1, "min": 0.5, "max": 2},
		{"key": "denoise", "label": "Clean it up", "type": "switch", "default": False},
	],
}

PLAIN = {"model_key": "google-ai-studio:flash", "capability": "Text Generation"}


def row(**answers):
	"""A `OneSpace AI Feature Setting` as the settings code holds it."""
	return types.SimpleNamespace(model_options=json.dumps(answers))


# --------------------------------------------------------------------------- #
# Reading a declaration
# --------------------------------------------------------------------------- #

def test_a_model_that_declares_nothing_is_not_an_error(options):
	assert options.declared(PLAIN) == []
	assert options.declared(None) == []
	assert options.resolved(row(), PLAIN) == {}


def test_an_option_the_control_plane_wrote_badly_is_dropped_not_raised_on(options):
	"""The catalogue is cached JSON from another site, one version either way.

	A settings page that will not render is a worse answer to that than one
	option fewer.
	"""
	declared = options.declared({"options": [
		{"key": "voice", "type": "select"},          # a select offering nothing
		{"key": "", "type": "number"},               # no key
		{"key": "steps", "type": "dial"},            # a type this does not have
		"a string where an object should be",
		{"key": "speed", "label": "Speed", "type": "number"},
	]})

	assert [option["key"] for option in declared] == ["speed"]


def test_an_option_with_no_label_is_labelled_by_its_key(options):
	assert options.declared({"options": [{"key": "speed", "type": "number"}]})[0]["label"] == "speed"


# --------------------------------------------------------------------------- #
# What gets sent
# --------------------------------------------------------------------------- #

def test_what_is_sent_is_the_models_defaults_with_the_workspaces_over_them(options):
	"""An option nobody answered is still sent, and sent as the model said.

	The alternative is leaving it out and letting the provider decide, which
	makes the same call mean different things on different days.
	"""
	assert options.resolved(row(lang="ES"), TTS) == {
		"lang": "ES", "speed": 1, "denoise": False,
	}


def test_an_answer_for_an_option_the_model_no_longer_has_is_not_sent(options):
	"""Changing the model is how a workspace stops using its options.

	Kept in the row rather than deleted, so changing back is not a re-typing
	exercise — but never sent to a model that has no such option.
	"""
	kept = row(lang="ES", voice="Aoede")

	assert options.answered(kept, TTS) == {"lang": "ES"}
	assert "voice" in options.stored(kept)


def test_answers_that_are_not_json_read_as_no_answers(options):
	assert options.stored(types.SimpleNamespace(model_options="{oh dear")) == {}
	assert options.stored(types.SimpleNamespace(model_options="[1, 2]")) == {}
	assert options.stored(None) == {}


# --------------------------------------------------------------------------- #
# What a browser is allowed to send back
# --------------------------------------------------------------------------- #

def test_a_value_outside_the_models_range_is_refused_not_clamped(options):
	"""Refused, because a clamp is a number the workspace did not choose.

	It would then sit in the settings page reading as their answer.
	"""
	with pytest.raises(Exception, match="between"):
		options.checked({"speed": 9}, TTS)


def test_a_choice_the_model_does_not_offer_is_refused(options):
	with pytest.raises(Exception, match="not a Language"):
		options.checked({"lang": "KLINGON"}, TTS)


def test_a_number_that_is_not_a_number_is_refused(options):
	with pytest.raises(Exception, match="has to be a number"):
		options.checked({"speed": "quickly"}, TTS)


def test_an_unknown_key_is_dropped_rather_than_refused(options):
	"""A page open while an operator retires an option must still save.

	Refusing would leave the workspace unable to change anything else on the
	panel until they reloaded, and the option is going to be ignored anyway.
	"""
	assert options.checked({"lang": "EN", "gone": "x"}, TTS) == {"lang": "EN"}


def test_a_switch_takes_whatever_a_browser_calls_true(options):
	assert options.checked({"denoise": 1}, TTS) == {"denoise": True}
	assert options.checked({"denoise": 0}, TTS) == {"denoise": False}


def test_text_is_bounded_like_every_other_thing_that_reaches_a_model(options):
	long = {"options": [{"key": "avoid", "label": "Avoid", "type": "text"}]}
	assert len(options.checked({"avoid": "x" * 5000}, long)["avoid"]) == options.MAX_TEXT


def test_an_empty_answer_is_how_the_default_is_asked_for(options):
	"""The panel offers "Default — 0.7" as a choice, and it sends "".

	Stored, it would be an answer that pins the workspace to today's default
	and survives the provider changing it. So it is not stored at all.
	"""
	assert options.checked({"lang": "", "speed": None}, TTS) == {}


def test_the_keys_a_model_declares_are_what_a_save_replaces(options):
	assert options.keys(TTS) == {"lang", "speed", "denoise"}
	assert options.keys(PLAIN) == set()


VOICE_PATH = "generationConfig.speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName"

SPEAKS = {
	"model_key": "google-ai-studio:tts",
	"capability": "Text to Speech",
	"options": [
		{"key": "voiceName", "label": "Voice", "type": "select",
		 "path": VOICE_PATH, "default": "Zephyr",
		 "options": [{"value": "Zephyr", "label": "Zephyr — Bright"},
		             {"value": "Puck", "label": "Puck — Upbeat"}]},
	],
}


def test_an_option_can_say_where_in_the_request_it_goes(options):
	"""Not every parameter is a key at the top of something.

	Google's voice sits four objects down, so the declaration carries the path
	and the gateway writes it there. Without this the answer lands somewhere the
	provider ignores and the setting silently does nothing.
	"""
	assert options.placements(SPEAKS) == {"voiceName": VOICE_PATH}
	assert options.placements(TTS) == {}
	assert options.declared(SPEAKS)[0]["path"] == VOICE_PATH
