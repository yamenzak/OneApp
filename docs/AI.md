# AI

Everything AI in OneSpace turns on one sentence: **we never invent a price.**

That constraint is what shapes the rest — the catalogue, the unit-aware price
rows, the decorator, the reservation, the reconciliation job. This file records
what is actually true about the providers, because the design only makes sense
against those facts.

---

## What Cloudflare AI Gateway does and does not return

Everything goes through one AI Gateway. That buys caching, retries, rate limits,
spend limits, and a per-request log tagged with the tenant. Provider keys are
stored in the gateway (BYOK), so a tenant site holds a gateway token and never a
Google key.

What it does **not** return is a cost.

* There is no cost header. The response headers are `cf-aig-log-id`,
  `cf-aig-step`, `cf-aig-cache-status` and `cf-aig-dlp` — the
  [header glossary](https://developers.cloudflare.com/ai-gateway/glossary/) is
  the full list.
* A cost appears in the gateway's **log entry**, retrievable through the
  [Logs API](https://developers.cloudflare.com/api/resources/ai_gateway/subresources/logs/methods/list/)
  as `cost`, alongside `tokens_in`, `tokens_out` and `cached`.
* Cloudflare describes that figure as an estimate: *"The cost metric is an
  estimation based on the number of tokens sent and received… refer to your
  provider's dashboard for the most accurate cost details."*
  ([Costs](https://developers.cloudflare.com/ai-gateway/observability/costs/))

So the gateway's number is neither immediate nor exact. What *is* exact is the
usage each model reports in its own response.

## What each provider actually reports

**Gemini** counts everything in tokens, by modality — with one exception noted
below. `usageMetadata` carries
`promptTokensDetails`, `cacheTokensDetails` and `candidatesTokensDetails`, each
a list of `(modality, tokenCount)`, plus `thoughtsTokenCount` for reasoning and
`toolUsePromptTokenCount` for tool calls. Generated pictures and generated speech
come back as IMAGE and AUDIO token counts — Google prices
`gemini-3.1-flash-image` output at "$3 (text and thinking) $60.00 (images)" per
million tokens — so a multimodal call is exactly meterable with no special case.

Two traps, both handled in `oneapp_core/ai/meter.py`:

* `promptTokenCount` is the *total effective* prompt, cached part included.
  Billing the prompt and the cache lines as written charges the cache twice.
* `thoughtsTokenCount` bills at the output rate and is absent from
  `candidatesTokensDetails`, so a meter that reads only that list gives
  reasoning away.

**Lyria**, Google's music generation family, is the exception on both counts. It
answers on the [Interactions API](https://ai.google.dev/gemini-api/docs/music-generation)
(`POST /v1beta/interactions`, model in the body, one `input` instead of a
contents array) and returns a timeline of steps carrying the audio and the
lyrics, with no token counts at all. It is billed per request — $0.04 for a
30-second clip, $0.08 for a full song — so the count is how many generations we
asked for, which is exactly what Google charges for.

**Workers AI** reports `usage.prompt_tokens` and `usage.completion_tokens` for
text and embeddings, and nothing at all for the rest. `flux-1-schnell` returns
`{image: "<base64>"}`; Whisper returns a transcript. Those are billed per
512×512 tile, per diffusion step, per audio minute, or per thousand input
characters — every one of which is a parameter *we* set on the way in. Counting
the request is not estimating the response; it is reading the same number
Cloudflare bills against.

## Why prices are unit-aware

There is no single unit, so the schema does not pretend there is. `AI Model
Price` holds one row per rate:

```
kind      Input | Cached Input | Cache Write | Output | Reasoning | Request | Search
modality  Text | Image | Audio | Video | File | Any
unit      Token | Image | Tile | Step | Second | Minute | Character | Request | Search
cost_usd  USD for `per_units` of them        (1,000,000 for token rates, 1 for a minute)
tier      Standard | Batch | Flex | Priority
effective_from / effective_to
```

Rates are stored the way providers publish them — cost for N units, not cost per
unit — because "$0.75 per 1,000,000 tokens" survives a round trip through a
Float and 0.00000075 does not.

A schema with `input_price` and `output_price` can hold text and nothing else,
which is how a price table quietly becomes wrong the day someone generates a
picture.

## Where the numbers come from

`oneapp_control/ai/catalogue.py`, nightly and on demand from OneAdmin:

| | models and capabilities | prices |
|---|---|---|
| Workers AI | `GET /accounts/{id}/ai/models/search` — `task.name`, `properties` | [the pricing page](https://developers.cloudflare.com/workers-ai/platform/pricing/), whose sections already separate LLM, embeddings, image, audio |
| Gemini | `GET /v1beta/models` — `supportedGenerationMethods`, token limits, `thinking` | [the pricing page](https://ai.google.dev/gemini-api/docs/pricing), whose cells state the modalities and whose header states the unit |

The parsers are in `oneapp_control/ai/sources.py` and have no frappe import, so
they are tested against the real pages saved under `tests/fixtures/`. When a
provider changes the shape of its table those tests fail — which is the point,
because the alternative is a parser that quietly returns fewer rates.

**Anything unparsed holds a model back.** A model with no rate, or with wording
no parser could read, lands as `Needs Review` with that wording in `sync_note`
and cannot be chosen or called. Real examples today:

* `@cf/black-forest-labs/flux-2-dev` — "per input 512x512 tile, per step" is
  tiles *times* steps, a compound unit; storing it as either is wrong by the
  factor of the other.
* `veo-3.1-generate-preview` — video billed per second *and* per resolution
  ("$0.40 (720p and 1080p) $0.60 (4k)"). Nothing in a request says which one a
  generation will land on, so either choice is wrong by a fixed factor on every
  call.

Better to sell nothing than to sell at a rate we made up.

### The unit comes from the table header

Every Gemini table states its unit in the header of the paid column: "Paid Tier,
per 1M tokens in USD". Across the page that reads tokens 77 times, "per second"
once (Veo) and "per request" once (Lyria) — so assuming tokens is right until it
is expensively wrong, and the header is sitting there saying so. A header naming
a unit we cannot count holds its models back rather than falling through to
tokens.

One more attribution rule, which Lyria is the only case of so far: a table can
price several models with a row each, labelled by model name rather than by kind
of charge.

```
|   | Free Tier | Paid Tier, per request in USD |
| Lyria 3 Clip Preview (30s)      | Not available | $0.04 per song |
| Lyria 3 Pro Preview (Full Song) | Not available | $0.08 per song |
```

Applying both rows to both models hands Pro the Clip's rate and bills full songs
at half price, so a row whose label names exactly one model in the section is
attributed to it alone.

The sync creates and refreshes; it does not overrule an operator. It makes
exactly two status decisions on its own: a model it can no longer price comes
off sale, and a model the provider stopped listing is retired. `Needs Review` is
its own verdict and is lifted automatically when the model prices again.
Nothing is deleted — a retired model still has to explain a charge from March.

## Declaring a feature

```python
from oneapp.oneapp_core.ai.features import ai_feature

@ai_feature(
    "invoice.summary",
    label="Invoice summary",
    capability="Text Generation",
    system="You summarise invoices for a small business owner...",
    max_output_tokens=400,
)
def summarise(ai, invoice):
    return ai(f"Summarise this invoice:\n{invoice.as_text()}").text
```

That is the whole registration. The decorator injects `ai` as the first
argument, and calling it resolves the model, composes the prompt, holds credits,
calls the provider, meters the answer and settles the charge.

The app lists its module in `hooks.py`:

```python
ai_features = ["myapp.invoices.ai"]
```

Listed rather than discovered by walking the package: a feature that only
registers when something happens to import its module is a feature missing from
the settings page on a cold worker.

Sites report their registry to the control plane on each sync, which is how
OneAdmin knows what exists without anyone maintaining a list.

`tenant_can_disable=False` marks a feature where AI *is* the process rather than
an assistant beside it. Those keep running when a workspace turns AI off,
because the alternative is a broken workflow with no error to point at. It is
declared in code, by the app that has to keep working, and is deliberately
absent from the operator's editable fields.

## The ceiling, and why it is not an estimate

Something must be held before the answer exists. That hold is a **limit**, not a
forecast: the most the call may consume — `max_input_tokens`, `max_output_tokens`,
`max_images`, `max_outputs`, `max_audio_seconds`, or a flat `max_credits` —
priced at the same catalogue rates. `max_outputs` is for a model billed per
generation rather than per unit of what it generates; it defaults to one,
because a call produces at least one thing and holding nothing would let a call
run against no reservation at all. The hold is released down to the measured actual the moment the
provider answers.

An operator can tighten any of them per feature in OneAdmin without a deploy.

Two edges worth knowing:

* `commit_usage` never charges more than was held, which is the right rule for a
  hold and the wrong one for a bill. A call that overran its ceiling still cost
  us the money, so `ai_settle` posts the remainder as an adjustment and logs it
  rather than absorbing it silently.
* A response that cannot be metered at all releases the hold and charges
  nothing. The customer has their answer; we cannot say what it cost, so we do
  not say.

## Reconciliation, and its limits

Hourly, `oneapp_control/ai/reconcile.py` pulls the gateway's logs by
`cf-aig-log-id` and puts the two figures side by side:

* **Ours** — the exact usage the model reported, priced against published rates.
* **Cloudflare's** — an estimate from token counts, and what the account is
  actually invoiced under Unified Billing.

Small gaps are adjusted: a stale rate we synced a day late is real money and
collecting or refunding it is right. Refunds are always applied — a cache hit
costs the provider nothing and the gateway logs zero.

Large gaps are **not** adjusted. Beyond 25% or 5 credits above our own figure,
the disagreement is not about price but about what happened: a model missing
from Cloudflare's cost table, a rate we mis-parsed, a bug at either end.
Re-billing a customer for a call they already made, on the strength of a number
its own vendor calls an estimate, is not something to do automatically. Those
are flagged on the usage record and logged for a person, and show on the
workspace's Billing tab in OneAdmin.

## What a workspace decides

The AI tab in workspace settings is not written anywhere — it is the feature
registry rendered. Each declared feature becomes a row; its model picker is
filtered to models matching the capability it declared; a critical feature shows
what it is instead of a switch.

A workspace can add to the prompt and read back what it added. It cannot read
ours. `settings.spec()` builds its rows field by field and `feature.system` is
not one of them, so there is no path from a browser to our instructions — and
the model receives ours first, then theirs, because instructions later in a
system prompt qualify what came before rather than replacing it.

## Markup

One multiplier in OneSpace Control Settings, applied to measured provider cost,
with a per-model override on the model's own row. Credits are
`cost_usd × 100 × markup`, rounded up so a million tiny calls are not free.

Credits stay deliberately abstract: customers buy credits, not tokens, so a
provider re-pricing a model is our problem rather than a pricing announcement.
