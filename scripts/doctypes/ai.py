"""Models, what they cost, and which features may spend on them.

The catalogue is synced from the providers rather than typed, so a price change
arrives as data. A feature declares what it needs; the workspace decides which
model answers it.
"""

from ai_capabilities import OPTIONS as AI_CAPABILITY_OPTIONS
from .spec import READONLY_PERMS, column, doctype, f, section


# --------------------------------------------------------------------------- #
# AI Model Price — one rate, in the unit the provider actually bills in.
#
# There is no single unit. Gemini bills images and speech in tokens; Workers AI
# bills images per 512x512 tile and per diffusion step, and speech per audio
# minute. A schema with `input_price` and `output_price` can only hold the first
# of those, which is how a text-shaped price table quietly becomes wrong the day
# someone generates a picture.
#
# The rate is stored the way the provider publishes it — cost for N units, not
# cost per unit — because "$0.75 per 1,000,000 tokens" survives a round trip
# through a Float and 0.00000075 does not.
# --------------------------------------------------------------------------- #
doctype(
    "AI Model Price",
    istable=1,
    fields=[
        f("kind", "Select", reqd=1, in_list_view=1,
          options="Input\nCached Input\nCache Write\nOutput\nReasoning\nRequest\nSearch",
          description="What is being charged for. Reasoning is Gemini's thinking "
                      "tokens, which bill at the output rate but are counted "
                      "separately."),
        f("modality", "Select", reqd=1, default="Text", in_list_view=1,
          options="Text\nImage\nAudio\nVideo\nFile\nAny",
          description="Which modality of that kind. A multimodal model has "
                      "several rows here and they do not cost the same."),
        f("unit", "Select", reqd=1, default="Token", in_list_view=1,
          options="Token\nImage\nTile\nStep\nSecond\nMinute\nCharacter\nRequest\nSearch",
          description="What the provider counts."),
        column("cb_price_rate"),
        f("cost_usd", "Float", precision="9", reqd=1, in_list_view=1,
          description="USD for `per_units` of them."),
        f("per_units", "Int", default="1000000", reqd=1, in_list_view=1,
          description="1,000,000 for token rates, 1 for an image or a minute."),
        f("tier", "Select", options="Standard\nBatch\nFlex\nPriority",
          default="Standard", reqd=1,
          description="Only Standard is charged unless a call asks for another."),
        section("sec_price_window"),
        f("effective_from", "Date",
          description="Providers publish dated rate changes. The row in effect "
                      "on the day of the call is the one that prices it."),
        f("effective_to", "Date"),
        column("cb_price_src"),
        f("note", "Data", description="The published wording this row came from."),
    ],
)


# --------------------------------------------------------------------------- #
# AI Model — the catalogue, synced rather than typed.
#
# Providers add models weekly and re-price them without telling anyone. A
# hand-maintained table is wrong within a month and nobody notices until a
# margin does. So this is fetched: Cloudflare's model search API and Google's
# models API for what exists and what it can do, their published price pages for
# what it costs.
#
# A model nothing could price lands as Needs Review and is not sellable. That is
# deliberate: the failure mode of a default price is charging a customer a
# number we made up.
# --------------------------------------------------------------------------- #
doctype(
    "AI Model",
    search_fields="display_name,provider,model_id",
    states=[
        ("Available", "Green"),
        ("Preview", "Light Blue"),
        ("Needs Review", "Orange"),
        ("Deprecated", "Yellow"),
        ("Retired", "Gray"),
    ],
    # Not made by hand: synced from the providers; one typed here would have no prices.
    in_create=1,
    autoname="field:model_key",
    title_field="display_name",
    fields=[
        f("model_key", reqd=1, unique=1,
          description="provider:model_id. Set on sync."),
        f("display_name", in_list_view=1),
        f("provider", "Select", options="workers-ai\ngoogle-ai-studio", reqd=1,
          in_list_view=1, in_standard_filter=1,
          description="The AI Gateway provider slug, used verbatim in the URL."),
        f("model_id", reqd=1,
          description="What goes in the request, e.g. @cf/meta/llama-3.3-70b-instruct-fp8-fast."),
        f("status", "Select", reqd=1, default="Needs Review", in_list_view=1,
          in_standard_filter=1,
          options="Available\nPreview\nNeeds Review\nDeprecated\nRetired",
          description="Only Available and Preview models can be chosen or "
                      "called. Needs Review means the sync could not price it."),
        column("cb_model_cap"),
        f("capability", "Select", reqd=1, default="Text Generation", in_list_view=1,
          in_standard_filter=1, options=AI_CAPABILITY_OPTIONS,
          description="What the model is for. A feature declares the capability "
                      "it needs and only matching models are offered."),
        f("input_modalities", default="text",
          description="Comma-separated: text, image, audio, video, file."),
        f("output_modalities", default="text"),
        f("is_recommended", "Check", default="0",
          description="Pre-selected for features that do not pin a model."),
        section("sec_model_limits", "Limits and features"),
        f("context_window", "Int"),
        f("max_output_tokens", "Int"),
        f("supports_tools", "Check", default="0"),
        column("cb_model_feat"),
        f("supports_json", "Check", default="0", label="Supports Structured Output"),
        f("supports_reasoning", "Check", default="0"),
        f("supports_streaming", "Check", default="0"),
        section("sec_model_price", "Pricing"),
        f("markup_override", "Float", default="0",
          description="Multiplier applied instead of the global one. 0 uses the global."),
        f("prices", "Table", options="AI Model Price"),
        section("sec_model_sync", "Sync"),
        f("source", "Select", default="Manual",
          options="Cloudflare API\nCloudflare Docs\nGoogle API\nGoogle Docs\nManual"),
        f("last_synced", "Datetime", read_only=1),
        f("deprecation_date", "Date", read_only=1),
        column("cb_model_sync"),
        f("sync_note", "Small Text", read_only=1,
          description="Why this model is where it is — including what could not "
                      "be priced."),
        f("description", "Small Text"),
    ],
)


# --------------------------------------------------------------------------- #
# AI Feature — what the apps declare, reported up rather than configured here.
#
# Features live in app code behind @ai_feature, which is the only place that
# knows a feature exists at all. Tenant sites report their registry on sync and
# this is the upsert of it, so an operator sees the whole surface without anyone
# maintaining a list, and can pin a default model or take a feature off the air
# without a deploy.
# --------------------------------------------------------------------------- #
doctype(
    "AI Feature",
    states=[
        ("Active", "Green"),
        ("Withdrawn", "Gray"),
        ("Suspended", "Orange"),
    ],
    # Not made by hand: reported by tenant sites from the decorator, never authored.
    in_create=1,
    autoname="field:feature_key",
    title_field="label",
    fields=[
        f("feature_key", reqd=1, unique=1,
          description="app.module.name, from the decorator."),
        f("label", in_list_view=1),
        f("app", in_list_view=1, in_standard_filter=1),
        f("capability", "Select", reqd=1, default="Text Generation",
          in_list_view=1, in_standard_filter=1, options=AI_CAPABILITY_OPTIONS),
        column("cb_feat_policy"),
        f("status", "Select", reqd=1, default="Active", in_list_view=1,
          in_standard_filter=1, options="Active\nWithdrawn\nSuspended",
          description="Suspended stops every tenant calling it, without a deploy."),
        f("tenant_can_disable", "Check", default="1",
          description="Declared by the decorator. Off means AI is the process, "
                      "not a garnish on it, and a tenant cannot switch it off."),
        f("allow_prompt_addendum", "Check", default="1",
          description="Whether a tenant may append to our system prompt."),
        f("default_model", "Link", options="AI Model",
          description="Used when a tenant has not chosen. Empty falls back to "
                      "the recommended model for the capability."),
        section("sec_feat_ceiling", "Ceiling"),
        f("max_input_tokens", "Int", default="0",
          description="0 falls back to the model's context window, which is the "
                      "most the provider would accept anyway."),
        f("max_output_tokens", "Int", default="0"),
        f("max_images", "Int", default="0"),
        f("max_outputs", "Int", default="0",
          description="Generations per call, for a model billed per generation "
                      "rather than per token — Lyria charges per song whatever "
                      "its length. 0 means one."),
        column("cb_feat_ceiling"),
        f("max_audio_seconds", "Int", default="0"),
        f("max_credits", "Float", default="0",
          description="Hard cap per call, whatever the model. 0 means the "
                      "ceiling is whatever the limits above cost."),
        section("sec_feat_meta"),
        f("description", "Small Text"),
        f("last_seen", "Datetime", read_only=1,
          description="Last sync that reported this feature. A feature that "
                      "stops being reported has been removed from the app."),
    ],
)


# --------------------------------------------------------------------------- #
# AI Usage Record — one row per call, and the answer to "where did my credits go".
#
# Also the reconciliation anchor: `gateway_log_id` is what AI Gateway returned
# in cf-aig-log-id, so a job can go back and compare what we charged against
# what Cloudflare says the call cost.
# --------------------------------------------------------------------------- #
doctype(
    "AI Usage Record",
    # Not made by hand: one row per call, written by the gateway.
    in_create=1,
    autoname="naming_series:",
    perms=READONLY_PERMS,
    fields=[
        f("naming_series", "Select", options="AIU-.YYYY.-", default="AIU-.YYYY.-",
          hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("feature", "Data", in_list_view=1, in_standard_filter=1),
        f("model", "Link", options="AI Model", in_list_view=1),
        # The same closed list AI Model carries, because it is the same value:
        # `pricing` copies `model.provider` onto the row. As Data it was a
        # standard filter rendering a free-text box over two possible answers.
        f("provider", "Select", options="workers-ai\ngoogle-ai-studio",
          in_standard_filter=1),
        column("cb_usage_money"),
        f("credits_charged", "Float", in_list_view=1),
        f("cost_usd", "Float", precision="9",
          description="Measured provider cost before markup."),
        f("markup", "Float"),
        f("reservation", "Link", options="Credit Reservation"),
        section("sec_usage_units", "What was counted"),
        f("units", "Code", options="JSON",
          description="The metered units, as reported by the provider."),
        column("cb_usage_log"),
        f("gateway_log_id", label="Gateway Log ID",
          description="cf-aig-log-id. The handle for reconciliation."),
        f("cached", "Check", default="0"),
        section("sec_usage_recon", "Reconciliation"),
        f("reconciled_on", "Datetime", read_only=1),
        f("gateway_cost_usd", "Float", precision="9", read_only=1,
          description="What AI Gateway's log says the call cost."),
        column("cb_usage_recon"),
        f("adjustment", "Link", options="Credit Ledger Entry", read_only=1,
          description="Posted when the gateway disagreed with us."),
        f("recon_note", "Small Text", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace AI Feature Setting — a workspace's answer for one declared feature.
#
# Rows are created from the registry, not typed: the decorator is the only thing
# that knows a feature exists, so a workspace's settings page is whatever its
# installed apps declare. A row for a feature that is no longer declared is
# ignored rather than deleted, so uninstalling and reinstalling an app does not
# lose the customer's wording.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace AI Feature Setting",
    app="tenant",
    istable=1,
    fields=[
        f("feature_key", reqd=1, in_list_view=1),
        f("enabled", "Check", default="1", in_list_view=1),
        f("model_key", label="Model", in_list_view=1,
          description="Empty means whatever the platform recommends for this "
                      "capability, which is also what tracks a better model "
                      "arriving without anyone changing a setting."),
        section("sec_feat_prompt"),
        f("prompt_addendum", "Small Text",
          description="Appended to our instructions. The model receives both; "
                      "this field never contains ours."),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace AI Settings — the workspace's AI switch and its per-feature answers.
#
# The catalogue is cached here from the control plane rather than fetched per
# request: choosing a model must work while the control plane is unreachable,
# and pricing a call must not depend on a network hop in the middle of one.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace AI Settings",
    app="tenant",
    issingle=1,
    fields=[
        f("ai_enabled", "Check", default="1",
          description="Off stops every feature a workspace is allowed to stop. "
                      "Features declared as critical keep running — they are "
                      "the process, not an assistant beside it."),
        f("credit_balance", "Float", read_only=1),
        column("cb_ai_set"),
        f("last_sync", "Datetime", read_only=1),
        section("sec_ai_features", "Features"),
        f("features", "Table", options="OneSpace AI Feature Setting"),
        section("sec_ai_cache", "Cached from the control plane"),
        f("catalogue_json", "Code", options="JSON", read_only=1,
          description="Models the workspace may choose, with prices."),
        f("registry_json", "Code", options="JSON", read_only=1,
          description="Platform policy per feature: what may be disabled, what "
                      "model is pinned, what the ceiling is."),
    ],
)
