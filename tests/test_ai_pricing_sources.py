"""Reading prices out of the pages the providers actually publish.

The fixtures are those pages, saved verbatim. When a provider changes the shape
of its price table these tests fail, which is the point: the alternative is a
parser that quietly returns fewer rates and a catalogue that quietly stops
charging for something.

The assertions are about *properties* — that a unit was understood, that a
multimodal cell produced one rate per modality, that nothing was invented — not
about the numbers, which will drift.
"""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sources():
	from oneapp_control.ai import sources as module

	return module


@pytest.fixture
def workers(sources):
	return sources.parse_workers_pricing((FIXTURES / "workers-ai-pricing.md").read_text())


@pytest.fixture
def gemini(sources):
	return sources.parse_gemini_pricing((FIXTURES / "gemini-pricing.md").read_text())


# --------------------------------------------------------------------------- #
# Workers AI
# --------------------------------------------------------------------------- #

def test_the_whole_price_page_is_read(workers):
	"""A parser that reads three models out of sixty looks like it works."""
	assert len(workers) > 50


def test_text_models_are_priced_per_million_tokens(workers):
	rates = workers["@cf/meta/llama-3.2-1b-instruct"].prices
	kinds = {(r.kind, r.unit, r.per_units) for r in rates}
	assert ("Input", "Token", 1_000_000) in kinds
	assert ("Output", "Token", 1_000_000) in kinds


def test_a_cached_input_rate_is_not_read_as_an_input_rate(workers):
	"""They sit in the same cell and one is thirty times cheaper."""
	rates = workers["@cf/deepseek-ai/deepseek-v4-pro-0813"].prices
	by_kind = {r.kind: r.cost_usd for r in rates}
	assert by_kind["Cached Input"] < by_kind["Input"]


def test_images_are_billed_in_tiles_and_steps_not_tokens(workers):
	"""The unit that made a text-shaped price table impossible."""
	rates = workers["@cf/black-forest-labs/flux-1-schnell"].prices
	assert {r.unit for r in rates} == {"Tile", "Step"}
	assert all(r.modality == "Image" for r in rates)


def test_speech_is_billed_per_audio_minute(workers):
	rate = workers["@cf/openai/whisper"].prices[0]
	assert (rate.modality, rate.unit, rate.per_units) == ("Audio", "Minute", 1)


def test_speech_synthesis_is_billed_per_thousand_characters(workers):
	rate = workers["@cf/deepgram/aura-2-en"].prices[0]
	assert (rate.unit, rate.per_units) == ("Character", 1000)


def test_a_compound_unit_is_refused_rather_than_guessed(workers):
	"""'per input 512x512 tile, per step' is tiles times steps. Storing it as
	either one would be wrong by the factor of the other."""
	parsed = workers["@cf/black-forest-labs/flux-2-dev"]
	assert not parsed.prices
	assert any("per step" in phrase for phrase in parsed.unparsed)


def test_the_same_model_on_two_transports_is_not_billed_twice(workers):
	"""Nova-3 is listed for HTTP and again for WebSocket in identical rows."""
	rates = workers["@cf/deepgram/nova-3"].prices
	assert len(rates) == 1
	assert workers["@cf/deepgram/nova-3"].notes


def test_a_websocket_row_does_not_invent_a_model(workers):
	assert "@cf/deepgram/nova-3 (WebSocket)" not in workers


def test_nothing_is_priced_at_zero(workers):
	for model, parsed in workers.items():
		for rate in parsed.prices:
			assert rate.cost_usd > 0, f"{model} has a free rate"


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #

def test_every_gemini_model_on_the_page_is_read(gemini):
	assert len(gemini) > 30


def test_nothing_on_the_gemini_page_defeats_the_parser(gemini):
	"""Anything here would hold a model back from sale, so it should be empty
	rather than merely small."""
	assert {k: v.unparsed for k, v in gemini.items() if v.unparsed} == {}


def test_a_dated_rate_change_is_two_rows_not_one(gemini):
	"""'$0.75 through December 31, 2026. $1.50 starting January 1, 2027.'"""
	inputs = [r for r in gemini["gemini-3.7-flash"].prices
	          if r.kind == "Input" and r.tier == "Standard"]
	assert len(inputs) == 2
	assert {r.effective_to for r in inputs} == {"2026-12-31", None}
	assert {r.effective_from for r in inputs} == {"2027-01-01", None}


def test_thinking_tokens_do_not_lose_the_output_rate(gemini):
	"""The row is labelled 'Output price (including thinking tokens)'; matching
	the label exactly drops the output rate of whichever model got a
	parenthesis this month."""
	assert any(r.kind == "Output" for r in gemini["gemini-3.7-flash"].prices)


def test_a_multimodal_cell_becomes_one_rate_per_modality(gemini):
	"""'$0.50 (text/image)' in, '$3 (text and thinking) $60.00 (images)' out."""
	rates = [r for r in gemini["gemini-3.1-flash-image"].prices if r.tier == "Standard"]
	inputs = {r.modality for r in rates if r.kind == "Input"}
	outputs = {r.modality: r.cost_usd for r in rates if r.kind == "Output"}

	assert inputs == {"Text", "Image"}
	assert set(outputs) == {"Text", "Image"}
	assert outputs["Image"] > outputs["Text"]


def test_generated_speech_is_priced_as_audio(gemini):
	rates = [r for r in gemini["gemini-3.1-flash-tts-preview"].prices
	         if r.kind == "Output" and r.tier == "Standard"]
	assert [r.modality for r in rates] == ["Audio"]


def test_batch_and_standard_are_kept_apart(gemini):
	"""Batch is half price. Charging a standard call at it would halve revenue."""
	rates = gemini["gemini-3.7-flash"].prices
	standard = next(r for r in rates if r.kind == "Input" and r.tier == "Standard"
	                and r.effective_to)
	batch = next(r for r in rates if r.kind == "Input" and r.tier == "Batch"
	             and r.effective_to)
	assert batch.cost_usd < standard.cost_usd


def test_a_cache_storage_rate_is_not_read_as_a_token_rate(gemini):
	"""'$0.50 / 1,000,000 tokens per hour (storage price)' is rent on cached
	bytes, not a charge on this call."""
	cached = [r for r in gemini["gemini-3.7-flash"].prices if r.kind == "Cached Input"]
	assert all(r.cost_usd < 1 for r in cached)
	assert any("storage" in note for note in gemini["gemini-3.7-flash"].notes)


def test_a_model_priced_in_units_we_cannot_express_gets_no_rates(gemini):
	"""Veo bills video per second and per resolution. Better to sell nothing
	than to sell it at a rate we made up."""
	assert not gemini["veo-3.1-generate-preview"].prices


def test_a_line_naming_several_models_registers_all_of_them(gemini):
	"""Taking only the first leaves the rest of a family absent entirely."""
	assert "veo-3.1-fast-generate-preview" in gemini
	assert "lyria-3-pro-preview" in gemini


def test_a_models_rates_do_not_leak_onto_the_next_one(gemini):
	"""The failure that silently halves someone's bill."""
	flash = {(r.kind, r.modality) for r in gemini["gemini-3.7-flash"].prices}
	assert ("Output", "Image") not in flash


# --------------------------------------------------------------------------- #
# Capability detection
# --------------------------------------------------------------------------- #

def test_a_task_we_do_not_recognise_is_not_guessed(sources):
	from oneapp_control.ai import capabilities

	assert capabilities.for_task("Text Generation") == "Text Generation"
	assert capabilities.for_task("Text-to-Image") == "Image Generation"
	assert capabilities.for_task("Interpretive Dance") is None


def test_gemini_capability_is_read_from_the_name_and_methods(sources):
	assert sources.gemini_capability("gemini-embedding-2", ["embedContent"]) == "Text Embeddings"
	assert sources.gemini_capability("gemini-3.1-flash-image", ["generateContent"]) == "Image Generation"
	assert sources.gemini_capability("gemini-3.1-flash-tts-preview", []) == "Text to Speech"
	assert sources.gemini_capability("veo-3.1-generate-preview", []) == "Video Generation"
	assert sources.gemini_capability("gemini-3.7-flash", ["generateContent"]) == "Text Generation"


def test_modalities_are_read_off_the_rates(sources, gemini):
	"""The price table is the only place Google states this per model: a cell
	reading '$0.50 (text/image)' is the statement that it takes pictures."""
	prices = gemini["gemini-3.1-flash-image"].prices
	inputs, outputs = sources.gemini_modalities("gemini-3.1-flash-image",
	                                            "Image Generation", prices)
	assert "image" in inputs
	assert "image" in outputs


# --------------------------------------------------------------------------- #
# Units that are not tokens
#
# Google states the unit in the header of every table's paid column. Across the
# whole page that reads "per 1M tokens" 77 times, "per second" once and "per
# request" once — so assuming tokens is right until it is expensively wrong, and
# the header is sitting there saying so.
# --------------------------------------------------------------------------- #

def test_music_is_priced_per_song(gemini):
    """Lyria bills per request whatever the song's length, which is a unit no
    amount of token arithmetic reaches."""
    rates = [r for r in gemini["lyria-3-clip-preview"].prices if r.tier == "Standard"]
    assert len(rates) == 1

    rate = rates[0]
    assert (rate.kind, rate.modality, rate.unit, rate.per_units) == (
        "Output", "Audio", "Request", 1)
    assert rate.cost_usd == 0.04


def test_two_models_in_one_table_do_not_share_a_rate(gemini):
    """Lyria prices Clip and Pro in one table, a row each. Applying both rows to
    both models hands Pro the Clip's rate and bills full songs at half price."""
    clip = gemini["lyria-3-clip-preview"].prices
    pro = gemini["lyria-3-pro-preview"].prices

    assert len(clip) == len(pro) == 1
    assert pro[0].cost_usd == clip[0].cost_usd * 2


def test_a_row_naming_no_model_still_applies_to_all_of_them(gemini):
    """The attribution must not break the ordinary case, where a table prices
    several models together and every row is an "Input price"."""
    rates = {r.kind for r in gemini["gemini-3.7-flash"].prices}
    assert {"Input", "Output", "Cached Input"} <= rates


def test_a_token_table_is_still_read_as_tokens(gemini):
    """77 of the 79 tables. The header change must not disturb any of them."""
    for rate in gemini["gemini-3.7-flash"].prices:
        assert (rate.unit, rate.per_units) == ("Token", 1_000_000)


def test_video_priced_per_resolution_is_still_refused(gemini):
    """Veo bills video per second *and* per resolution — "$0.40 (720p and
    1080p) $0.60 (4k)". Nothing in a request says which one a generation will
    land on, so either choice is wrong by a fixed factor on every call."""
    assert not gemini["veo-3.1-generate-preview"].prices


def test_a_non_token_cell_with_several_rates_is_refused(sources):
    """The rule behind that, stated on its own. Several amounts in one cell is
    normal for tokens — dated changes, a rate per modality — and a warning sign
    anywhere else."""
    table = "\n".join([
        "## Veo",
        "*[`veo-3.1-fast-generate-preview`](https://example.test)*",
        "|   | Free Tier | Paid Tier, per second in USD |",
        "|---|---|---|",
        "| Veo 3.1 Fast Generate Preview | Not available | $0.10 (720p) $0.30 (4k) |",
    ])
    parsed = sources.parse_gemini_pricing(table)["veo-3.1-fast-generate-preview"]
    assert not parsed.prices
    assert parsed.unparsed


def test_a_unit_we_cannot_count_holds_the_model_back(sources):
    """A header naming something we have no way to measure is a reason to sell
    nothing, not a reason to fall back to tokens."""
    table = "\n".join([
        "## Something new",
        "*[`some-future-model`](https://example.test)*",
        "|   | Free Tier | Paid Tier, per furlong in USD |",
        "|---|---|---|",
        "| Output price | Not available | $2.00 |",
    ])
    parsed = sources.parse_gemini_pricing(table)["some-future-model"]
    assert not parsed.prices
    assert parsed.unparsed


def test_music_generation_is_recognised_as_a_capability(sources):
    assert sources.gemini_capability("lyria-3-pro-preview", []) == "Audio Generation"
    assert sources.gemini_modalities(
        "lyria-3-pro-preview", "Audio Generation", [])[1] == "audio"
