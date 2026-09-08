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
        f("options_json", "Code", label="Options", options="JSON",
          description="What else this model takes beyond the ask — a voice, a "
                      "language, a size. A JSON array of "
                      "{key, label, type, default, ...}; see "
                      "`onespace/ai/options.py` for the four types. Sent to "
                      "every tenant with the catalogue and rendered under the "
                      "model picker. Filled by the sync from the provider's "
                      "own list — Cloudflare's input schema, Google's published "
                      "voice table — so it is not a thing anyone transcribes."),
        f("options_locked", "Check", default="0",
          description="The sync leaves the options above alone. Tick it after "
                      "editing them by hand, or the next run writes over them "
                      "with whatever the provider publishes."),
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
        section("sec_feat_run", "A run of several calls"),
        f("max_turns", "Int", default="0",
          description="A conversation is one call per turn, and the ceiling "
                      "above holds for one of them. This is how many turns a "
                      "single ask may take before the loop stops — a model that "
                      "keeps calling tools spends the ceiling again each time. "
                      "0 means the feature is not conversational."),
        column("cb_feat_run"),
        f("max_run_credits", "Float", default="0",
          description="Credits one ask may spend across all its turns. Checked "
                      "on this site between turns, against what the previous "
                      "ones actually settled at. 0 means turns are the only "
                      "limit."),
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
        f("model_options", "Small Text", label="Model Options",
          description="The workspace's answers to whatever the chosen model "
                      "declares — a voice, a language, a size. JSON keyed by "
                      "option, read back only through the model's own "
                      "declaration, so an option that goes away stops being "
                      "sent without anything having to migrate."),
        section("sec_feat_prompt"),
        f("prompt_addendum", "Small Text",
          description="Appended to our instructions. The model receives both; "
                      "this field never contains ours."),
    ],
)


#: How the assistant speaks. A fixed vocabulary rather than free text, because
#: this half goes into the prompt as a word the model has to act on, and "how
#: formal" is a dial with a handful of stops. The character itself is free text
#: — that is `assistant_personality`, which is where the specific goes.
TONES = "\n".join(["Neutral", "Friendly", "Formal", "Direct", "Warm"])


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
        # Who the assistant is, to this workspace.
        #
        # Workspace-level and not per feature: a person talking to it in the
        # chat panel and a person reading something it drafted are meeting the
        # same character, and a name that changed between the two would read as
        # two different products. The name and the picture are what the app
        # shows; the personality and the tone are what the model is told, the
        # same way `prompt_addendum` is — appended to our instructions, never
        # replacing them.
        section("sec_ai_identity", "The assistant"),
        f("assistant_name", default="Assistant",
          description="What it is called wherever it appears."),
        f("assistant_avatar", "Attach Image",
          description="Its picture. Falls back to a mark drawn from the name."),
        column("cb_ai_identity"),
        f("assistant_tone", "Select", options=TONES, default="Neutral",
          description="How it speaks."),
        f("assistant_personality", "Small Text",
          description="Who it is, in a sentence. Say what it knows and how it "
                      "should come across."),
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


# --------------------------------------------------------------------------- #
# What a model wrote, and where.
#
# A row per value: `Sales Invoice` / `ACC-SINV-0001` / `remarks`. A row rather
# than a field on the record, because most records are not ours — a workspace's
# documents are Quotations and Sales Invoices, and marking a field on one would
# mean a custom field on every doctype an app might ever touch. The same shape
# `Document Follow` and `Tag Link` use, for the same reason, and it covers a
# child row too since a child row has a name of its own.
#
# It carries who and what, not only where. "AI wrote this" is an icon; "the
# workspace assistant wrote this with <model>, at Ada's asking, on 3 May" is an
# answer to the question the icon provokes — and it is the same row, so there is
# no reason to store less.
#
# Hash-named, and the triple kept unique by `written.mark` looking first. Frappe
# indexes one field at a time and a name built from the three would overflow the
# 140 characters a name has, so the uniqueness is the module's to keep — which
# it does, because a value written twice is one fact and not two.
# --------------------------------------------------------------------------- #
doctype(
    "AI Written Value",
    app="tenant",
    autoname="hash",
    perms=[
        # Nobody reads this doctype directly, and that is deliberate. A mark
        # reaches a browser only inside the record it is about, from
        # `spaceview.records.record`, which has already decided that reader may
        # see that record. Readable here as well and a person could list every
        # marked field on the site — which names documents they cannot open.
        {"read": 1, "write": 1, "create": 1, "delete": 1, "role": "System Manager"},
    ],
    fields=[
        f("reference_doctype", "Data", "Document Type", search_index=1,
          description="The doctype the value is on. Data and not Link: a "
                      "workspace's records belong to apps we do not own, and a "
                      "Link would refuse a row for a doctype uninstalled since."),
        f("reference_name", "Data", "Document", search_index=1),
        f("fieldname", "Data", search_index=1,
          description="The field. `file_url` on a File is how a generated "
                      "image or a piece of audio is marked, so one mechanism "
                      "covers fields and media rather than two."),
        column("cb_ai_written"),
        f("feature_key", "Data",
          description="Which declared feature wrote it. See `ai/features.py`."),
        f("model_key", "Data", description="Which model, from the catalogue."),
        f("asked_by", "Link", options="User",
          description="Who asked for it. Nothing wrote itself."),
    ],
)


# --------------------------------------------------------------------------- #
# The workspace assistant's transcripts.
#
# A conversation is stored because a conversation is a document: it is looked
# at again, it is what "you told me last week" means, and it is the only record
# of what the assistant was asked to read. Storing it also makes the cost
# legible — every turn is a metered call, and `credits` on the session is the
# sum of them.
#
# Per person and not per workspace. Two people asking the assistant about the
# same quotation are having two conversations, and each of them sees only what
# their own roles let them see, so a shared thread would be a thread whose rows
# mean different things to different readers.
# --------------------------------------------------------------------------- #
CHAT_PERMS = [
    {"read": 1, "write": 1, "create": 1, "delete": 1, "role": "System Manager"},
    # Everybody signed in, and only their own. `if_owner` is what makes a
    # transcript private without a role per person.
    {"read": 1, "write": 1, "create": 1, "delete": 1, "role": "All", "if_owner": 1},
]


doctype(
    "OneSpace Chat Session",
    app="tenant",
    perms=CHAT_PERMS,
    autoname="hash",
    title_field="title",
    search_fields="title",
    fields=[
        f("title", in_list_view=1,
          description="The first thing that was asked, trimmed. Named from the "
                      "question rather than by the model: naming a thread is "
                      "a second call, and it would be charged for."),
        f("last_message_on", "Datetime", in_list_view=1, read_only=1),
        column("cb_chat_meta"),
        f("message_count", "Int", default="0", read_only=1),
        f("credits", "Float", default="0", read_only=1,
          description="What this whole conversation has cost, summed as each "
                      "turn settles."),
        f("archived", "Check", default="0"),
    ],
)


# --------------------------------------------------------------------------- #
# OneSpace Chat Message — one turn, including the ones nobody typed.
#
# A separate doctype rather than a child table on the session. A chat grows
# without bound and a child table rewrites every row of the parent on each save,
# so appending the fortieth message would rewrite the other thirty-nine.
#
# `tool` rows are stored alongside the visible ones because they are what the
# next turn is sent: dropping them would leave the model reading its own
# question about a record and no answer to it.
# --------------------------------------------------------------------------- #
doctype(
    "OneSpace Chat Message",
    app="tenant",
    perms=CHAT_PERMS,
    autoname="hash",
    fields=[
        f("session", "Link", options="OneSpace Chat Session", reqd=1,
          in_list_view=1, in_standard_filter=1),
        f("seq", "Int", reqd=1, in_list_view=1,
          description="Order within the session. Not creation time: a turn and "
                      "the tool results that answer it are written in one "
                      "request and can share a timestamp."),
        f("role", "Select", reqd=1, default="user", in_list_view=1,
          options="user\nassistant\ntool",
          description="Frappe has no opinion here; these are the roles a "
                      "provider accepts, and `ai/transcript.py` maps them on."),
        column("cb_chat_msg"),
        f("credits", "Float", default="0", read_only=1,
          description="What the call that produced this turn settled at. Zero "
                      "on anything a person typed."),
        f("stopped", "Data", read_only=1,
          description="Why the loop ended on this turn: answered, turns_spent "
                      "or budget_spent. Empty on a person's own message."),
        section("sec_chat_body"),
        f("content", "Long Text"),
        f("tool_calls", "Code", options="JSON",
          description="What the model asked to run, when this turn asked for "
                      "anything. The arguments as sent, so a transcript says "
                      "which records were read."),
        column("cb_chat_tool"),
        f("tool_call_id", read_only=1,
          description="Which call a `tool` row answers."),
        f("tool_name", read_only=1),
    ],
)
