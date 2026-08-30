"""Turning what a call actually used into what it costs.

Nothing here estimates. Every figure starts from a count the provider returned —
tokens by modality, images, audio seconds — and is multiplied by a rate that was
synced from the provider's own published price. A count with no matching rate
raises; it does not fall back to a default, because a default price is a number
we made up and then billed someone for.

Credits are the customer-facing unit. They are deliberately abstract: customers
buy credits, not tokens, so a provider re-pricing a model or a feature moving to
a cheaper one is our problem rather than a pricing announcement.
"""

import math
from datetime import date

import frappe
from frappe.utils import getdate

# A cent of measured provider cost is one credit, before markup. It keeps credit
# figures human-sized and makes the arithmetic checkable by hand.
CREDITS_PER_USD = 100.0

# Used only when nothing else is configured. Every real deployment sets this in
# OneApp Control Settings.
FALLBACK_MARKUP = 1.5


class Unpriceable(Exception):
	"""A call used something the catalogue has no rate for."""


def _matches(row, kind, modality, unit, on: date) -> bool:
	if (row.kind, row.unit) != (kind, unit):
		return False
	if row.modality not in (modality, "Any"):
		return False
	if row.effective_from and getdate(row.effective_from) > on:
		return False
	if row.effective_to and getdate(row.effective_to) < on:
		return False
	return True


def rate_for(model, kind: str, modality: str, unit: str, tier: str, on: date):
	"""The row in force today, preferring the one that says so explicitly.

	Providers publish dated changes — "$0.75 through December 31, 2026. $1.50
	starting January 1, 2027" — as two rows that both look current if you only
	read the first. Sorting the dated ones first is what makes the switch happen
	on the day rather than whenever someone notices.
	"""
	candidates = [
		row for row in model.prices
		if row.tier == tier and _matches(row, kind, modality, unit, on)
	]
	if not candidates:
		return None
	candidates.sort(key=lambda r: (r.effective_from is None and r.effective_to is None))
	return candidates[0]


def cost_usd(model, units: list[dict], tier: str = "Standard", on: date | None = None) -> float:
	"""What the provider will charge us for these counts."""
	on = on or date.today()
	total = 0.0

	for line in units:
		count = float(line.get("count") or 0)
		if count <= 0:
			continue

		kind = line.get("kind") or "Input"
		modality = line.get("modality") or "Text"
		unit = line.get("unit") or "Token"

		rate = rate_for(model, kind, modality, unit, tier, on)
		if rate is None and tier != "Standard":
			# A model priced only at the standard tier is not free on the others.
			rate = rate_for(model, kind, modality, unit, "Standard", on)
		if rate is None:
			raise Unpriceable(
				f"{model.name} has no {tier} rate for {kind}/{modality}/{unit}."
			)

		total += count * float(rate.cost_usd) / max(int(rate.per_units or 1), 1)

	return total


def markup_for(model) -> float:
	if model.markup_override and float(model.markup_override) > 0:
		return float(model.markup_override)
	configured = frappe.db.get_single_value(
		"OneApp Control Settings", "ai_markup_multiplier")
	return float(configured) if configured and float(configured) > 0 else FALLBACK_MARKUP


def to_credits(usd: float, markup: float) -> float:
	"""Round up. A request that costs anything must cost at least a hundredth of
	a credit, or a million tiny calls are free."""
	credits = usd * CREDITS_PER_USD * markup
	return math.ceil(credits * 100) / 100 if credits > 0 else 0.0


def charge(model_key: str, units: list[dict], tier: str = "Standard") -> dict:
	"""Price one call. The only place a credit figure is produced."""
	model = frappe.get_cached_doc("AI Model", model_key)
	usd = cost_usd(model, units, tier)
	markup = markup_for(model)
	return {
		"model": model_key,
		"provider": model.provider,
		"cost_usd": usd,
		"markup": markup,
		"credits": to_credits(usd, markup),
	}


# --------------------------------------------------------------------------- #
# Ceilings
#
# Something has to be held before the answer exists, and it must not be a guess
# at what the answer will cost. So it is a limit instead: the most the call is
# allowed to consume, priced at the same rates. The hold is released down to the
# measured actual the moment the provider answers.
# --------------------------------------------------------------------------- #

def ceiling_units(model, limits: dict) -> list[dict]:
	"""The most a call may use, in the units this model is billed in."""
	units = []

	max_input = int(limits.get("max_input_tokens") or 0) or int(model.context_window or 0)
	if max_input:
		units.append({"kind": "Input", "modality": "Text", "unit": "Token",
		              "count": max_input})

	outputs = (model.output_modalities or "text").split(",")

	if "text" in outputs or not outputs:
		max_output = (int(limits.get("max_output_tokens") or 0)
		              or int(model.max_output_tokens or 0))
		if max_output:
			units.append({"kind": "Output", "modality": "Text", "unit": "Token",
			              "count": max_output})

	images = int(limits.get("max_images") or 0)
	if "image" in outputs and images:
		# Whichever unit this model is actually billed in — Gemini counts image
		# output in tokens, Workers AI in tiles and diffusion steps.
		for unit, per_image in (("Image", 1), ("Tile", 4), ("Step", 8)):
			if rate_for(model, "Output", "Image", unit, "Standard", date.today()):
				units.append({"kind": "Output", "modality": "Image", "unit": unit,
				              "count": images * per_image})
		if rate_for(model, "Output", "Image", "Token", "Standard", date.today()):
			# 4K output is 2,520 tokens per image, the largest Google publishes.
			units.append({"kind": "Output", "modality": "Image", "unit": "Token",
			              "count": images * 2520})

	# Models billed per generation rather than per token — Lyria charges per
	# song, whatever its length. The count of generations is the only thing to
	# cap, and one is the honest floor: a call produces at least one.
	generations = int(limits.get("max_outputs") or 0) or 1
	for row in model.prices:
		if row.kind == "Output" and row.unit == "Request" and row.tier == "Standard":
			units.append({"kind": "Output", "modality": row.modality,
			              "unit": "Request", "count": generations})

	seconds = int(limits.get("max_audio_seconds") or 0)
	if seconds and "audio" in outputs:
		for unit, count in (("Second", seconds), ("Minute", math.ceil(seconds / 60)),
		                    ("Token", seconds * 25)):
			if rate_for(model, "Output", "Audio", unit, "Standard", date.today()):
				units.append({"kind": "Output", "modality": "Audio", "unit": unit,
				              "count": count})

	return units


def ceiling(model_key: str, limits: dict) -> float:
	"""Credits to hold for a call under these limits.

	An explicit `max_credits` wins: it is a budget an operator set, and holding
	more than the budget allows would be the ceiling arguing with itself.
	"""
	if float(limits.get("max_credits") or 0) > 0:
		return float(limits["max_credits"])

	model = frappe.get_cached_doc("AI Model", model_key)
	units = ceiling_units(model, limits)
	if not units:
		raise Unpriceable(
			f"{model_key}: no ceiling could be built — the feature declares no "
			"limits and the model publishes none."
		)
	return to_credits(cost_usd(model, units), markup_for(model))
