"""AI cost to credits.

Getting this wrong is expensive in one direction and embarrassing in the other,
so the properties are pinned rather than the exact numbers, which will drift as
providers reprice.
"""

import pytest


@pytest.fixture
def pricing():
	from oneapp.oneapp_core.ai import pricing as module

	return module


def test_known_model_is_priced(pricing):
	assert pricing.price_for("google-ai-studio", "gemini-2.5-flash") != pricing.DEFAULT_PRICING


def test_unknown_model_falls_back_rather_than_free(pricing):
	"""An unpriced model must never be free, or a typo gives away compute."""
	assert pricing.price_for("google-ai-studio", "not-a-model") == pricing.DEFAULT_PRICING
	assert pricing.cost_usd("nope", "nope", 1_000_000, 1_000_000) > 0


def test_output_costs_more_than_input(pricing):
	for provider, models in pricing.MODEL_PRICING.items():
		for model, (inp, out) in models.items():
			if out:
				assert out >= inp, f"{provider}/{model} output cheaper than input"


def test_cost_scales_with_tokens(pricing):
	small = pricing.cost_usd("google-ai-studio", "gemini-2.5-flash", 1000, 1000)
	large = pricing.cost_usd("google-ai-studio", "gemini-2.5-flash", 100000, 100000)
	assert large > small * 50


def test_markup_is_applied(pricing):
	plain = pricing.credits_for("google-ai-studio", "gemini-2.5-pro", 100000, 100000, markup=1.0)
	marked = pricing.credits_for("google-ai-studio", "gemini-2.5-pro", 100000, 100000, markup=2.0)
	assert marked == pytest.approx(plain * 2, rel=0.02)


def test_any_usage_costs_something(pricing):
	"""Rounding up matters: high-volume tiny calls must not become free."""
	assert pricing.credits_for("google-ai-studio", "gemini-2.5-flash", 10, 10) > 0


def test_zero_usage_is_free(pricing):
	assert pricing.credits_for("google-ai-studio", "gemini-2.5-flash", 0, 0) == 0


def test_estimate_exceeds_typical_actual(pricing):
	"""The reservation must be pessimistic — under-reserving lets concurrent
	requests overdraw, which is the failure that costs money."""
	prompt = "x" * 4000  # ~1000 input tokens
	estimate = pricing.estimate_credits("google-ai-studio", "gemini-2.5-flash", len(prompt), 1024)
	actual = pricing.credits_for("google-ai-studio", "gemini-2.5-flash", 1000, 200)
	assert estimate > actual


def test_cheap_tier_is_actually_cheaper(pricing):
	"""The point of a local model tier is cost; if it is not cheaper it is pointless."""
	frontier = pricing.cost_usd("google-ai-studio", "gemini-2.5-pro", 100000, 100000)
	cheap = pricing.cost_usd("workers-ai", "@cf/meta/llama-3.1-8b-instruct", 100000, 100000)
	assert cheap < frontier
