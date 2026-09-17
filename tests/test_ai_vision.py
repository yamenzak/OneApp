"""Looking at a picture: what is refused before a call is made, and why it is
a feature of its own.

`Image Understanding` had been a declared capability with nothing declaring it
since the registry was written — a model row carries `input_modalities`, a
price row has a `modality` column so an image tile bills differently from a
token, and the settings page filters each feature's picker to the capability
it asked for. There was simply no feature asking for this one, so the picker
was never drawn.
"""

import sys
import types

import pytest


@pytest.fixture
def vision(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	seen = []
	said = {"text": "Total: 6,100.00", "credits": 0.2}

	from oneapp.oneai import gateway

	def caller(feature):
		def run(prompt="", **request):
			seen.append({"feature": feature.key, "prompt": prompt, **request})
			return dict(said)

		run.feature = feature
		return run

	monkeypatch.setattr(gateway, "caller", caller)

	from oneapp.oneai import vision as module

	return types.SimpleNamespace(module=module, seen=seen, said=said,
	                             frappe=stub_frappe, monkeypatch=monkeypatch)


def test_it_declares_the_capability_that_had_nobody(vision):
	assert vision.module.read.feature.capability == "Image Understanding"


def test_the_bytes_travel_on_the_turn_that_asked(vision):
	"""One turn, not two. "Look at this and tell me what it says" is one thing
	a person said, and splitting it is two turns the model has to put back
	together."""
	vision.module.read(mime="image/png", data="QUJD", question="What is the total?")

	[call] = vision.seen
	[turn] = call["messages"]
	assert turn["content"] == "What is the total?"
	assert turn["attachments"] == [{"mime": "image/png", "data": "QUJD"}]


def test_no_question_is_a_transcription(vision):
	vision.module.read(mime="image/png", data="QUJD")

	assert "what it says" in vision.seen[0]["messages"][0]["content"]


@pytest.mark.parametrize("mime", ["video/mp4", "application/zip", "text/csv", ""])
def test_a_file_nothing_can_look_at_never_reaches_a_model(vision, mime):
	"""Refused here rather than by the provider: a 400 naming a mime type is
	a call that was paid for and answered nothing."""
	with pytest.raises(ValueError):
		vision.module.read(mime=mime, data="QUJD")

	assert vision.seen == []


def test_a_pdf_goes_whole_and_there_is_no_rasteriser(vision):
	"""The one document format that goes inline as itself. Rendering pages to
	images would be a second library, a second cost and a worse answer — the
	model reading the PDF can see its text layer."""
	vision.module.read(mime="application/pdf", data="QUJD")

	assert vision.seen[0]["messages"][0]["attachments"][0]["mime"] == "application/pdf"


def test_a_picture_too_big_is_refused_rather_than_shrunk(vision):
	"""Resizing it to save a call is a second image nobody can see, and what
	it would answer about is not what the person is looking at."""
	with pytest.raises(ValueError):
		vision.module.read(mime="image/png", data="A" * (vision.module.MAX_BYTES + 1))

	assert vision.seen == []


def test_nothing_at_all_is_refused(vision):
	with pytest.raises(ValueError):
		vision.module.read(mime="image/png", data="")


def test_the_prompt_asks_for_what_it_says_and_not_what_it_looks_like(vision):
	"""The failure this feature is judged on is a paragraph about a
	photograph where a total was wanted."""
	said = vision.module.read.feature.system
	assert "Do not describe the medium" in said
	assert "rather than guessing" in said
	# And the one that keeps a wrong number out of a workspace.
	assert "gap is a question somebody can answer" in said
