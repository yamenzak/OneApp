"""What a call costs, and what is held before it runs.

Two rules are load-bearing and both are asserted here rather than trusted:

  * A count with no matching rate raises. It does not fall back to a default,
    because a default price is a number we made up and then billed for.
  * The reservation is a ceiling, not a forecast. It is the most the call may
    consume, priced at the same rates.
"""

import datetime
import types

import pytest


@pytest.fixture
def pricing():
	from oneapp_control.ai import pricing as module

	return module


def rate(kind, modality, unit, cost, per=1_000_000, tier="Standard",
         start=None, end=None):
	return types.SimpleNamespace(
		kind=kind, modality=modality, unit=unit, cost_usd=cost, per_units=per,
		tier=tier, effective_from=start, effective_to=end,
	)


def model(name, prices, **kw):
	return types.SimpleNamespace(
		name=name, prices=prices, markup_override=0,
		context_window=kw.get("context_window", 0),
		max_output_tokens=kw.get("max_output_tokens", 0),
		output_modalities=kw.get("output_modalities", "text"),
	)


GEMINI = model("google-ai-studio:flash", [
	rate("Input", "Text", "Token", 0.75),
	rate("Cached Input", "Text", "Token", 0.075),
	rate("Output", "Text", "Token", 3.75),
], context_window=1_000_000, max_output_tokens=65536)

NANO = model("google-ai-studio:image", [
	rate("Input", "Text", "Token", 0.50),
	rate("Input", "Image", "Token", 0.50),
	rate("Output", "Text", "Token", 3.00),
	rate("Output", "Image", "Token", 60.00),
], output_modalities="text,image", context_window=32768, max_output_tokens=32768)

FLUX = model("workers-ai:flux", [
	rate("Output", "Image", "Tile", 0.0000528, per=1),
	rate("Output", "Image", "Step", 0.0001056, per=1),
], output_modalities="image")

DATED = model("google-ai-studio:dated", [
	rate("Input", "Text", "Token", 0.75, end="2026-12-31"),
	rate("Input", "Text", "Token", 1.50, start="2027-01-01"),
])

MILLION = [{"kind": "Input", "modality": "Text", "unit": "Token", "count": 1_000_000}]


def test_a_call_costs_what_the_published_rate_says(pricing):
	usd = pricing.cost_usd(GEMINI, [
		{"kind": "Input", "modality": "Text", "unit": "Token", "count": 1_000_000},
		{"kind": "Output", "modality": "Text", "unit": "Token", "count": 1_000_000},
	])
	assert usd == pytest.approx(4.50)


def test_a_generated_image_is_priced_as_image_tokens(pricing):
	"""Google publishes a 1024x1024 image as 1,120 tokens at $60/M — $0.067.
	If this drifts, the arithmetic no longer matches their own worked example."""
	usd = pricing.cost_usd(NANO, [
		{"kind": "Output", "modality": "Image", "unit": "Token", "count": 1120},
	])
	assert usd == pytest.approx(0.0672)


def test_an_image_billed_in_tiles_and_steps_adds_both(pricing):
	usd = pricing.cost_usd(FLUX, [
		{"kind": "Output", "modality": "Image", "unit": "Tile", "count": 4},
		{"kind": "Output", "modality": "Image", "unit": "Step", "count": 4},
	])
	assert usd == pytest.approx(0.0006336)


def test_cached_input_is_not_charged_at_the_full_rate(pricing):
	full = pricing.cost_usd(GEMINI, MILLION)
	cached = pricing.cost_usd(GEMINI, [
		{"kind": "Cached Input", "modality": "Text", "unit": "Token", "count": 1_000_000},
	])
	assert cached < full / 5


def test_a_unit_with_no_rate_raises_rather_than_costing_nothing(pricing):
	"""The whole design in one assertion: no default price, ever."""
	with pytest.raises(pricing.Unpriceable):
		pricing.cost_usd(GEMINI, [
			{"kind": "Output", "modality": "Video", "unit": "Second", "count": 5},
		])


def test_a_rate_change_takes_effect_on_its_own_date(pricing):
	before = pricing.cost_usd(DATED, MILLION, on=datetime.date(2026, 8, 30))
	after = pricing.cost_usd(DATED, MILLION, on=datetime.date(2027, 6, 1))
	assert (before, after) == (0.75, 1.50)


def test_an_unpriced_tier_falls_back_to_standard_not_to_free(pricing):
	"""A model priced only at the standard tier is not free on the others."""
	assert pricing.cost_usd(GEMINI, MILLION, tier="Flex") == pytest.approx(0.75)


def test_markup_is_what_turns_cost_into_credits(pricing):
	assert pricing.to_credits(1.0, 1.0) == 100
	assert pricing.to_credits(1.0, 1.5) == 150


def test_any_usage_costs_something(pricing):
	"""Rounding up matters: a million tiny calls must not be free."""
	tiny = pricing.cost_usd(GEMINI, [
		{"kind": "Input", "modality": "Text", "unit": "Token", "count": 1},
	])
	assert pricing.to_credits(tiny, 1.5) > 0


def test_no_usage_is_free(pricing):
	assert pricing.to_credits(0, 1.5) == 0


# --------------------------------------------------------------------------- #
# Ceilings
# --------------------------------------------------------------------------- #

def test_a_ceiling_is_built_from_declared_limits(pricing):
	units = pricing.ceiling_units(GEMINI, {"max_input_tokens": 8000,
	                                       "max_output_tokens": 1024})
	assert {(u["kind"], u["count"]) for u in units} == {("Input", 8000), ("Output", 1024)}


def test_a_feature_that_declares_nothing_is_capped_by_the_model(pricing):
	"""Not unlimited: the context window is the most the provider would accept."""
	units = pricing.ceiling_units(GEMINI, {})
	assert units[0]["count"] == GEMINI.context_window


def test_an_image_ceiling_uses_the_units_that_model_bills_in(pricing):
	"""Same declared limit, two different models, two different unit sets."""
	tokens = pricing.ceiling_units(NANO, {"max_input_tokens": 100, "max_images": 2})
	tiles = pricing.ceiling_units(FLUX, {"max_images": 2})

	assert any(u["unit"] == "Token" and u["modality"] == "Image" for u in tokens)
	assert {u["unit"] for u in tiles if u["modality"] == "Image"} == {"Tile", "Step"}


def test_a_ceiling_covers_a_realistic_call(pricing):
	"""It is a cap, so it has to be above what a call of that shape costs, or
	the hold runs out mid-flight."""
	limits = {"max_input_tokens": 8000, "max_output_tokens": 1024}
	ceiling = pricing.cost_usd(GEMINI, pricing.ceiling_units(GEMINI, limits))
	actual = pricing.cost_usd(GEMINI, [
		{"kind": "Input", "modality": "Text", "unit": "Token", "count": 3120},
		{"kind": "Output", "modality": "Text", "unit": "Token", "count": 210},
	])
	assert ceiling > actual


def test_a_declared_credit_budget_is_the_ceiling(pricing):
	assert pricing.ceiling("anything", {"max_credits": 2.5}) == 2.5


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #

@pytest.fixture
def reconcile():
	from oneapp_control.ai import reconcile as module

	return module


def test_a_refund_is_always_believed(reconcile):
	"""A cache hit costs the provider nothing and the gateway logs zero. Giving
	credits back needs no further justification."""
	assert reconcile.believable(10.0, 0.0)


def test_a_small_extra_charge_is_believed(reconcile):
	"""A stale rate — we synced a price a day after it changed."""
	assert reconcile.believable(100.0, 110.0)


def test_a_wild_extra_charge_is_not(reconcile):
	"""Sixteen times our own measurement is not a price difference. It is a
	disagreement about what happened, and re-billing a customer on the strength
	of a figure its own vendor calls an estimate is not automatic."""
	assert not reconcile.believable(100.0, 1600.0)
