"""Model cost, and how it becomes credits.

Kept as data in one place so re-pricing is an edit here rather than a hunt
through call sites. Figures are USD per million tokens and will drift — treat
them as configuration to review, not constants.

Credits are deliberately abstract. Customers buy credits, not tokens, so
provider price changes and model swaps do not force a pricing announcement.
"""

# provider -> model -> (input USD / 1M tokens, output USD / 1M tokens)
MODEL_PRICING = {
	"google-ai-studio": {
		"gemini-2.5-flash": (0.30, 2.50),
		"gemini-2.5-pro": (1.25, 10.00),
		"gemini-2.0-flash": (0.10, 0.40),
	},
	# Workers AI is billed per neuron, not per token. These are rough token
	# equivalents for metering; the cheap tier exists so bulk work does not run
	# on a frontier model.
	"workers-ai": {
		"@cf/meta/llama-3.1-8b-instruct": (0.03, 0.06),
		"@cf/baai/bge-base-en-v1.5": (0.01, 0.0),
	},
}

DEFAULT_PRICING = (1.00, 5.00)

# Credits per USD of provider cost, before markup. 100 keeps credit numbers
# human-sized: a cent of model spend is one credit.
CREDITS_PER_USD = 100.0

DEFAULT_MARKUP = 1.5


def price_for(provider: str, model: str) -> tuple[float, float]:
	return MODEL_PRICING.get(provider, {}).get(model, DEFAULT_PRICING)


def cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
	inp, out = price_for(provider, model)
	return (input_tokens / 1_000_000 * inp) + (output_tokens / 1_000_000 * out)


def credits_for(provider: str, model: str, input_tokens: int, output_tokens: int,
                markup: float = DEFAULT_MARKUP) -> float:
	"""Round up: a request that costs anything must cost at least one credit,
	or high-volume tiny calls become free."""
	import math

	usd = cost_usd(provider, model, input_tokens, output_tokens)
	credits = usd * CREDITS_PER_USD * markup
	return float(math.ceil(credits * 100) / 100) if credits else 0.0


def estimate_credits(provider: str, model: str, prompt_chars: int,
                     max_output_tokens: int = 1024, markup: float = DEFAULT_MARKUP) -> float:
	"""Upper bound to reserve before the call.

	Deliberately pessimistic — assumes maximum output. Over-reserving briefly
	holds credits the caller gets back; under-reserving lets concurrent requests
	overdraw, which is the failure that actually costs money.
	"""
	# ~4 characters per token is a rough but serviceable approximation.
	input_tokens = max(prompt_chars // 4, 1)
	return credits_for(provider, model, input_tokens, max_output_tokens, markup)
