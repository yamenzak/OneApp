"""What a workspace buys, and what it owes.

Plans, add-ons, credit packs and promo codes are catalogues with one shared
price history. A subscription names items from them; the ledger records what was
spent, and the reservation what is about to be.
"""

from .spec import READONLY_PERMS, column, doctype, f, section


# --------------------------------------------------------------------------- #
# Plan — quotas only. Never feature flags.
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Catalogue Price — every Stripe Price anything we sell has ever had.
#
# Stripe Prices are immutable in amount and currency, so changing what something
# costs means minting a new Price and leaving the old one billing whoever is
# already on it. That is how price grandfathering works, and it only works if
# the old ids survive: this table is both the history an operator reads and the
# reverse lookup a webhook needs to answer "which of ours is this price?" when a
# subscription changes underneath us.
#
# One table for plans, add-ons and credit packs rather than three near-identical
# ones. Every row already carries `parenttype`, so the lookups say which
# catalogue they mean and a plan's price can never resolve to an add-on.
# --------------------------------------------------------------------------- #
doctype(
    "Catalogue Price",
    istable=1,
    fields=[
        # `One-off` is what a credit pack is: bought once, so it has no cadence.
        # Said rather than left blank, because a price with no interval and a
        # price whose interval nobody filled in are different problems.
        f("interval", "Select", options="Monthly\nYearly\nOne-off", reqd=1, in_list_view=1),
        f("stripe_price_id", label="Stripe Price ID", in_list_view=1, read_only=1),
        f("unit_amount", "Currency", in_list_view=1, read_only=1,
          description="What Stripe charges. Ours to display, Stripe's to enforce."),
        f("currency", "Data", read_only=1),
        column("cb_price_state"),
        f("is_current", "Check", default="0", in_list_view=1, read_only=1,
          description="The price new subscriptions are sold at. Exactly one per "
                      "interval; the rest are grandfathered."),
        f("created_on", "Datetime", read_only=1),
        f("archived_on", "Datetime", read_only=1,
          description="Archived in Stripe, so it cannot be sold again. Existing "
                      "subscriptions keep billing on it — that is the point."),
    ],
)


# --------------------------------------------------------------------------- #
# Promo Code — a discount on anything we sell, including all of it.
#
# Ours to declare, Stripe's to enforce. Saving one creates a Stripe **Coupon**
# (the money: percent or amount, and for how long) and a **Promotion Code** (the
# string somebody types, its redemption limit and its expiry). Nobody pastes a
# `promo_...` id between two systems, for the same reason nobody pastes a price.
#
# A coupon's terms are immutable in Stripe once created. So changing a percentage
# mints a new coupon and a new promotion code and deactivates the old one:
# anybody already redeemed keeps what they were given, which is the same
# grandfathering shape a plan price has, for the same reason.
#
# 100% off forever is how a demo or training workspace exists. It is a real
# subscription at zero — real terms, real quotas, real monthly credit grants —
# rather than a comped tenant on a second lifecycle. Stripe asks for no card when
# the total is zero, and `handle_signup_paid` already accepts the
# `no_payment_required` that comes back.
# --------------------------------------------------------------------------- #
doctype(
    "Promo Code",
    search_fields="description,discount_type",
    states=[
        ("Percent", "Blue"),
        ("Amount", "Purple"),
    ],
    autoname="field:promo_code",
    fields=[
        f("promo_code", label="Code", reqd=1, unique=1, in_list_view=1,
          description="What somebody types. Upper-cased on save, because nobody "
                      "types a code the way it was written down."),
        f("description", "Small Text", reqd=1,
          description="What it is for. An operator reads this in six months and "
                      "has to know whether it can be retired."),
        f("is_active", "Check", default="1", in_list_view=1,
          description="Unchecking deactivates the promotion code in Stripe. "
                      "Anybody already redeemed keeps their discount — that is "
                      "Stripe's behaviour and it is the right one."),
        column("cb_promo_money"),
        f("discount_type", "Select", options="Percent\nAmount", default="Percent",
          reqd=1, in_list_view=1),
        f("percent_off", "Float", depends_on="eval:doc.discount_type=='Percent'",
          description="1 to 100. A hundred is free — which is the point."),
        f("amount_off", "Currency", depends_on="eval:doc.discount_type=='Amount'"),
        f("currency", "Link", options="Currency", default="USD",
          depends_on="eval:doc.discount_type=='Amount'",
          description="An amount-off coupon only applies to purchases in its own "
                      "currency. Stripe enforces that, not us."),
        f("duration", "Select", options="Once\nRepeating\nForever", default="Once",
          reqd=1,
          description="How many billing periods it lasts. Irrelevant to a "
                      "one-off purchase, which only ever has one."),
        f("duration_in_months", "Int", depends_on="eval:doc.duration=='Repeating'"),
        section("sec_promo_scope", "What it applies to"),
        f("on_subscriptions", "Check", default="1",
          description="Plans. This is the one a free demo instance needs."),
        f("on_addons", "Check", default="0",
          description="Extra storage, bought per month."),
        f("on_credit_packs", "Check", default="0"),
        column("cb_promo_limits"),
        f("max_redemptions", "Int", default="0",
          description="Total times it may be used, across everybody. Zero for no "
                      "limit."),
        f("expires_on", "Date", description="Stripe stops accepting it after this."),
        f("first_time_only", "Check", default="0",
          description="Only for a customer who has never paid us before."),
        section("sec_promo_stripe"),
        f("stripe_coupon_id", label="Stripe Coupon ID", read_only=1),
        f("stripe_promotion_code_id", label="Stripe Promotion Code ID", read_only=1),
        f("times_redeemed", "Int", default="0", read_only=1, in_list_view=1,
          description="Counted by Stripe, refreshed from it. Not incremented "
                      "here — two systems counting the same thing disagree."),
        f("sync_error", "Small Text", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Credit Pack — AI credits, bought once.
#
# The other half of how credits arrive. A plan grants some every period and they
# expire at the end of it; a pack is bought outright and rolls over, which is
# what makes it worth buying — `ledger.open_grants` spends the soonest-expiring
# grant first and never-expiring purchases last.
#
# One price, not two: a pack is bought once, so it has no cadence. It still
# carries the full price history, because repricing one has to archive the old
# Stripe price like everything else.
# --------------------------------------------------------------------------- #
doctype(
    "Credit Pack",
    search_fields="pack_name,credits",
    autoname="field:pack_code",
    title_field="pack_name",
    fields=[
        f("pack_code", reqd=1, unique=1, description="Stable id, e.g. credits-5k"),
        f("pack_name", reqd=1, in_list_view=1),
        f("credits", "Float", reqd=1, in_list_view=1,
          description="What the buyer receives. Never expires."),
        f("is_active", "Check", default="1"),
        f("sort_order", "Int", default="0"),
        column("cb_pack_price"),
        f("currency", "Link", options="Currency", default="USD"),
        f("amount", "Currency", reqd=1, in_list_view=1),
        f("stripe_product_id", label="Stripe Product ID", read_only=1),
        f("stripe_price_id", label="Stripe Price ID", read_only=1,
          description="The current price. History is in Prices below."),
        f("sync_error", "Small Text", read_only=1,
          description="Why the last sync to Stripe did not finish. Saving again "
                      "retries; the pack stays sellable on whatever price it "
                      "already has."),
        section("sec_pack_copy"),
        f("description", "Small Text",
          description="What a customer reads next to the price."),
        section("sec_pack_prices", "Prices"),
        f("prices", "Table", options="Catalogue Price", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Add-on — extra quota, bought per month on the subscription.
#
# An add-on is a second recurring line on the same Stripe subscription, so the
# customer gets one invoice, one dunning cycle and one card. It is not a plan:
# plans differ only in quotas and every feature is on every one of them, while an
# add-on adds to a quota without changing what plan somebody is on.
#
# Sold per unit. "+50 GB" bought three times is one line with quantity 3, which
# is what lets somebody grow without a new product every time.
# --------------------------------------------------------------------------- #
doctype(
    "Add-on",
    search_fields="addon_name,kind",
    states=[
        ("File Storage", "Blue"),
        ("Database Storage", "Purple"),
    ],
    autoname="field:addon_code",
    title_field="addon_name",
    fields=[
        f("addon_code", reqd=1, unique=1, description="Stable id, e.g. storage-50"),
        f("addon_name", reqd=1, in_list_view=1),
        # A Select and not free text: the quota layer switches on this, and a
        # third kind is a code change either way. Better to fail at save time.
        f("kind", "Select", options="File Storage\nDatabase Storage", reqd=1,
          in_list_view=1, in_standard_filter=1,
          description="Which quota a unit of this adds to."),
        f("unit_gb", "Int", label="Unit GB", default="50", reqd=1, in_list_view=1,
          description="How much one unit buys. Quantity multiplies it."),
        f("max_units", "Int", default="0",
          description="Most units one workspace may hold. Zero for no ceiling."),
        f("is_active", "Check", default="1"),
        f("sort_order", "Int", default="0"),
        column("cb_addon_price"),
        f("currency", "Link", options="Currency", default="USD"),
        # Both cadences, because Stripe requires every recurring line on one
        # subscription to share an interval. A yearly workspace cannot be sold a
        # monthly add-on, so an add-on priced only monthly is simply not offered
        # to them.
        f("price_monthly", "Currency", in_list_view=1),
        f("price_yearly", "Currency"),
        f("stripe_product_id", label="Stripe Product ID", read_only=1),
        f("stripe_price_id_monthly", label="Stripe Price ID (Monthly)", read_only=1,
          description="The current monthly price. History is in Prices below."),
        f("stripe_price_id_yearly", label="Stripe Price ID (Yearly)", read_only=1),
        f("sync_error", "Small Text", read_only=1,
          description="Why the last sync to Stripe did not finish. Saving again "
                      "retries; the add-on stays sellable on whatever prices it "
                      "already has."),
        section("sec_addon_copy"),
        f("description", "Small Text",
          description="What a customer reads next to the price."),
        section("sec_addon_prices", "Prices"),
        f("prices", "Table", options="Catalogue Price", read_only=1,
          description="Every Stripe price this add-on has had. Subscriptions "
                      "holding an older one keep billing on it."),
    ],
)


doctype(
    "Plan",
    search_fields="plan_name,audience",
    states=[
        ("Personal", "Blue"),
        ("Commercial", "Purple"),
    ],
    autoname="field:plan_code",
    title_field="plan_name",
    fields=[
        f("plan_code", reqd=1, unique=1, description="Stable id, e.g. personal-starter"),
        f("plan_name", reqd=1, in_list_view=1),
        f("audience", "Select", options="Personal\nCommercial", reqd=1,
          in_list_view=1, in_standard_filter=1),
        f("is_active", "Check", default="1"),
        f("sort_order", "Int", default="0"),
        column("cb_price"),
        f("currency", "Link", options="Currency", default="USD"),
        f("price_monthly", "Currency", in_list_view=1),
        f("price_yearly", "Currency"),
        # Written by the Stripe sync, never by hand. Saving a plan creates the
        # product and prices it needs; a changed amount mints a new price and
        # archives the old one. Two people typing the same id into two systems
        # is how a page advertises one number while the card is charged another.
        f("stripe_product_id", label="Stripe Product ID", read_only=1),
        f("stripe_price_id_monthly", label="Stripe Price ID (Monthly)", read_only=1,
          description="The current monthly price. History is in Prices below."),
        f("stripe_price_id_yearly", label="Stripe Price ID (Yearly)", read_only=1),
        f("sync_error", "Small Text", read_only=1,
          description="Why the last sync to Stripe did not finish. Saving again "
                      "retries; the plan stays sellable on whatever prices it "
                      "already has."),
        section("sec_quota", "Quotas"),
        f("storage_gb", "Int", default="10", description="Hard cap enforced at upload."),
        f("max_users", "Int", default="3"),
        column("cb_quota"),
        f("monthly_credit_grant", "Float", default="0",
          description="Non-rollover. Expires at the end of each billing period."),
        f("background_workers", "Int", default="1",
          description="Concurrent background jobs. Caps what one workspace can "
                      "take from a shared bench — the fleet cannot preempt, so it "
                      "limits instead."),
        f("database_gb", "Int", default="2",
          description="Database size cap. Separate from files: this is the one "
                      "that constrains how many sites fit on a server."),
        section("sec_backups", "Backups"),
        # Ours, into R2, alongside whatever Frappe Cloud keeps. R2 storage is
        # cheap enough that the frequency is a product lever rather than a cost
        # one — which is why it is a plan term and not a constant.
        f("backups_per_day", "Int", default="1",
          description="How often this plan's workspaces back themselves up to "
                      "R2. The first run of each day takes files as well; the "
                      "rest are database-only, which is what actually changes."),
        column("cb_backups"),
        f("backup_retention_days", "Int", default="7",
          description="How long those backups are kept. The cold copy taken "
                      "when a workspace is suspended is exempt — it lives under "
                      "its own prefix and answers to the lifecycle windows."),
        section("sec_press_plan"),
        f("press_site_plan", label="Press Site Plan",
          description="Overrides the shard default when set."),
        f("description", "Small Text"),
        section("sec_prices", "Prices"),
        f("prices", "Table", options="Catalogue Price", read_only=1,
          description="Every Stripe price this plan has had. Subscriptions sold "
                      "on an older one keep billing on it."),
    ],
)


# --------------------------------------------------------------------------- #
# Subscription Add-on — an add-on line as this subscription actually holds it.
#
# Captured, not looked up. `unit_gb` and the rate are copied at purchase for the
# same reason the plan's terms are: editing the catalogue must change what the
# *next* purchase buys and nothing else. Somebody who bought three lots of 50 GB
# keeps 150 GB when the add-on is redefined as 100 GB a unit.
#
# `stripe_subscription_item_id` is how a quantity change addresses the right
# line. Without it the only way to raise a quantity would be to guess which of
# the subscription's items this row meant.
# --------------------------------------------------------------------------- #
doctype(
    "Subscription Add-on",
    istable=1,
    fields=[
        f("addon", "Link", options="Add-on", reqd=1, in_list_view=1),
        f("kind", "Select", options="File Storage\nDatabase Storage", reqd=1,
          in_list_view=1,
          description="Captured, so a retired add-on's rows still add up."),
        f("quantity", "Int", default="1", reqd=1, in_list_view=1),
        f("unit_gb", "Int", label="Unit GB", default="0", in_list_view=1,
          description="GB per unit at the moment of purchase."),
        column("cb_addon_line"),
        f("stripe_subscription_item_id", label="Stripe Subscription Item ID",
          read_only=1,
          description="The line on the Stripe subscription this row is."),
        f("stripe_price_id", label="Stripe Price ID", read_only=1),
        f("unit_amount", "Currency", read_only=1,
          description="What one unit costs. Grandfathered like a plan price."),
        f("currency", "Data", read_only=1),
        f("added_on", "Datetime", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Subscription — mirrors Stripe. Stripe owns the schedule; this reflects it.
# --------------------------------------------------------------------------- #
doctype(
    "Subscription",
    search_fields="tenant,plan,status",
    states=[
        ("Incomplete", "Yellow"),
        ("Trialing", "Light Blue"),
        ("Active", "Green"),
        ("Past Due", "Orange"),
        ("Canceled", "Red"),
    ],
    # Not made by hand: Stripe owns the schedule; the webhook writes this.
    in_create=1,
    autoname="naming_series:",
    fields=[
        f("naming_series", "Select", options="SUB-.YYYY.-", default="SUB-.YYYY.-",
          reqd=1, hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("plan", "Link", options="Plan", reqd=1, in_list_view=1),
        f("status", "Select",
          options="Incomplete\nTrialing\nActive\nPast Due\nCanceled",
          default="Incomplete", reqd=1, in_list_view=1, in_standard_filter=1),
        f("interval", "Select", options="Monthly\nYearly", default="Monthly", reqd=1),
        column("cb_stripe"),
        f("stripe_customer_id", label="Stripe Customer ID", read_only=1),
        f("stripe_subscription_id", label="Stripe Subscription ID", read_only=1,
          unique=1),
        f("cancel_at_period_end", "Check", default="0"),
        f("last_invoice_id", label="Last Stripe Invoice ID", read_only=1),
        section("sec_period", "Current period"),
        f("current_period_start", "Datetime", read_only=1),
        f("current_period_end", "Datetime", read_only=1,
          description="Non-rollover grants expire here."),
        column("cb_period"),
        f("last_grant_period_end", "Datetime", read_only=1,
          description="Guards against double-granting on webhook replay."),
        # ------------------------------------------------------------------ #
        # The plan's terms as they were when this subscription was sold.
        #
        # Enforcement reads these, not the Plan doc. Quotas read live meant that
        # editing a plan silently re-quotaed everyone already on it — someone who
        # bought 50GB could wake up with 20GB because a price sheet was being
        # tidied. Stripe already grandfathers the price by leaving the old Price
        # on the subscription; this is the same promise for everything the price
        # bought.
        #
        # Same field names as Plan, so the copy is field-for-field and a reader
        # can see at a glance that nothing was reinterpreted on the way across.
        # `oneapp_control.billing.quotas` is the only thing that reads them.
        # ------------------------------------------------------------------ #
        section("sec_terms", "Plan terms at purchase"),
        f("storage_gb", "Int", default="0"),
        f("database_gb", "Int", default="0"),
        f("max_users", "Int", default="0"),
        column("cb_terms"),
        f("monthly_credit_grant", "Float", default="0"),
        f("background_workers", "Int", default="0"),
        f("press_site_plan", label="Press Site Plan"),
        f("backups_per_day", "Int", default="0"),
        f("backup_retention_days", "Int", default="0"),
        f("terms_captured_on", "Datetime", read_only=1,
          description="When these were copied from the plan. Empty means this "
                      "subscription predates the snapshot and still reads the "
                      "plan live."),
        # ------------------------------------------------------------------ #
        # And what was bought on top of the plan.
        #
        # Separate from the terms above rather than folded into them, because
        # they answer different questions: the terms are what this plan gave at
        # purchase and never move, while add-ons are held and released as the
        # workspace grows. `quotas.for_subscription` adds the two.
        # ------------------------------------------------------------------ #
        section("sec_addons", "Add-ons"),
        f("addons", "Table", options="Subscription Add-on",
          description="Extra quota this workspace is paying for, as lines on "
                      "the same Stripe subscription."),
    ],
)


# --------------------------------------------------------------------------- #
# Space Entitlement
# --------------------------------------------------------------------------- #
doctype(
    "Space Entitlement",
    autoname="hash",
    fields=[
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("app", "Link", options="OneSpace Space", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("enabled", "Check", default="1", in_list_view=1),
        column("cb_ent"),
        f("granted_on", "Datetime", read_only=1),
        f("note", "Small Text"),
    ],
)


# --------------------------------------------------------------------------- #
# Credit Ledger Entry — append-only. Balance is a sum, never a stored field.
# --------------------------------------------------------------------------- #
doctype(
    "Credit Ledger Entry",
    search_fields="tenant,entry_type,remarks",
    states=[
        ("Grant", "Green"),
        ("Purchase", "Green"),
        ("Spend", "Blue"),
        ("Refund", "Orange"),
        ("Expiry", "Gray"),
        ("Adjustment", "Purple"),
    ],
    # Not made by hand: the ledger is append-only and balance is a sum of it.
    in_create=1,
    autoname="naming_series:",
    perms=READONLY_PERMS,
    fields=[
        f("naming_series", "Select", options="CLE-.YYYY.-", default="CLE-.YYYY.-",
          reqd=1, hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("entry_type", "Select",
          options="Grant\nPurchase\nSpend\nRefund\nExpiry\nAdjustment",
          reqd=1, in_list_view=1, in_standard_filter=1),
        f("credits", "Float", reqd=1, in_list_view=1,
          description="Signed. Positive adds, negative consumes."),
        column("cb_cle"),
        f("expires_on", "Date", in_list_view=1,
          description="Grants only. Blank means it never expires."),
        f("consumed_from", "Link", options="Credit Ledger Entry",
          description="For Spend and Expiry rows, the grant they draw down."),
        f("reservation", "Link", options="Credit Reservation"),
        section("sec_src", "Source"),
        f("source_doctype", "Link", options="DocType"),
        f("source_name", "Dynamic Link", options="source_doctype"),
        column("cb_src"),
        f("remarks", "Small Text"),
    ],
)


# --------------------------------------------------------------------------- #
# Credit Reservation — reserve/commit so concurrent spend cannot overdraw.
# --------------------------------------------------------------------------- #
doctype(
    "Credit Reservation",
    search_fields="tenant,purpose,status",
    states=[
        ("Open", "Blue"),
        ("Committed", "Green"),
        ("Released", "Gray"),
        ("Expired", "Orange"),
    ],
    # Not made by hand: reserve/commit is the gateway's, and a stray Open row expires.
    in_create=1,
    autoname="naming_series:",
    fields=[
        f("naming_series", "Select", options="CRES-.YYYY.-", default="CRES-.YYYY.-",
          reqd=1, hidden=1),
        f("tenant", "Link", options="Tenant", reqd=1, in_list_view=1,
          in_standard_filter=1),
        f("status", "Select", options="Open\nCommitted\nReleased\nExpired",
          default="Open", reqd=1, in_list_view=1, in_standard_filter=1),
        f("credits_reserved", "Float", reqd=1, in_list_view=1),
        f("credits_committed", "Float", default="0", read_only=1),
        column("cb_res"),
        f("purpose", description="e.g. ai:chat, ai:embedding"),
        f("expires_at", "Datetime", reqd=1,
          description="Swept and released if still Open past this time."),
        f("committed_on", "Datetime", read_only=1),
        f("released_on", "Datetime", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# Stripe Webhook Event — Stripe retries aggressively and delivers out of order.
# Recording every event id makes replay a no-op instead of a double charge.
# --------------------------------------------------------------------------- #
doctype(
    "Stripe Webhook Event",
    states=[
        ("Received", "Gray"),
        ("Processed", "Green"),
        ("Ignored", "Yellow"),
        ("Failed", "Red"),
    ],
    # Not made by hand: a mirror of what Stripe delivered.
    in_create=1,
    autoname="field:event_id",
    perms=READONLY_PERMS,
    fields=[
        f("event_id", reqd=1, unique=1, in_list_view=1),
        f("event_type", in_list_view=1, in_standard_filter=1),
        f("status", "Select", options="Received\nProcessed\nIgnored\nFailed",
          default="Received", reqd=1, in_list_view=1, in_standard_filter=1),
        column("cb_evt"),
        f("tenant", "Link", options="Tenant"),
        f("subscription", "Link", options="Subscription"),
        f("processed_on", "Datetime", read_only=1),
        section("sec_evt"),
        f("payload", "Code", options="JSON"),
        f("error", "Text"),
    ],
)
