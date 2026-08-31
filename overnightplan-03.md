# Overnight plan 03 — add-ons, credit packs and promo codes

**Status: done.** A–G are built, tested and pushed. `DECISIONS.md` §2 is
rewritten (add-ons are monthly, not permanent) and gains §2a for promo codes;
`ARCHITECTURE.md` §7 names the pack catalogue and the operator's grant.


Three things to sell that the product does not sell yet, and one that it half
sells already.

| | |
| --- | --- |
| **Add-ons** | Extended file storage and extended database storage, **per month**, on the existing subscription. |
| **Credit packs** | One-time purchases of AI credits. Roll over, never expire. |
| **Promo codes** | A discount on any of the three, including 100% off — which is how a demo or training instance gets spun up for nothing. |

## What is already here

More than the ask assumes, and it changes the shape of the work.

**Credit packs are built end to end.** `checkout.start_credit_pack` opens a
`mode="payment"` session; `handle_checkout_completed` routes `kind=credit_pack`
to `grant_credit_pack`, which posts a `Purchase` ledger row with no expiry —
`ledger.open_grants` already orders `expires_on IS NULL` last, so purchased
credits are spent after granted ones, exactly as `ARCHITECTURE.md` §7 says. The
ERPNext mirror (`books.record_credit_pack`) is wired. `PackCard.vue` renders
them on the account's Billing screen.

What is missing is that the catalogue is six dictionaries in
`api/customer.py:164-176`, so changing a price is a deploy; and packs use
inline `price_data` rather than Stripe Products and Prices, so there is no
price history and nothing to grandfather.

**Storage is sold as a permanent one-off.** `Tenant.extra_storage_gb`,
`grant_storage_pack`, `STORAGE_PACKS`, `customer.buy_storage`. That is what
`DECISIONS.md` §2 currently commits to — "purchased explicitly, and it does not
expire". The decision is now **per month**, so this path is retired and §2 is
rewritten. `extra_storage_gb` survives as what it should always have been: a
grant an operator makes by hand, not something with a price on it.

**Promo codes do not exist.** No coupon, discount, voucher or promotion code
anywhere. But the ground is prepared better than that suggests:

* `stripe_client.create_checkout_session(**kwargs)` forwards anything, so
  `allow_promotion_codes` and `discounts` are one parameter away.
* `_reconcile_plan` keys on the **price id**, not the amount, and its comment
  already names "a coupon applied in the dashboard" as a drift source it
  tolerates. A discounted subscription reconciles correctly today.
* `handle_signup_paid` already accepts `payment_status == "no_payment_required"`
  — which is exactly what Stripe returns for a fully discounted checkout. The
  free-signup path is live and untested rather than absent.
* `api/signup.py` says so out loud: "Trials can come later by allowing an
  Account Request to reach Paid without a charge."

**Trials are vestigial.** `Tenant.trial_ends_on` is read by nothing.
`Subscription.status` includes `Trialing` and every code path treats it as live,
but nothing ever creates one. Left alone: a 100%-off promo is a better demo
instance than a trial, because it does not expire into a broken site.

---

## The one blocker

`change_plan` (`checkout.py:160-166`) and `_reconcile_plan`
(`webhooks.py:266-271`) both do this:

```python
items = (stripe_subscription.get("items") or {}).get("data") or []
if len(items) != 1:
    frappe.throw("This subscription has {n} items; change it in Stripe.")
```

A recurring add-on is a second item. So the moment anybody buys one, changing
their plan throws and plan reconciliation stops silently — the worse of the two,
because it fails by logging and moving on.

The fix is not to relax the count. It is to **find the plan's item** rather than
assume there is only one: `plans.plan_for_price(price_id)` already resolves a
Stripe price to a Plan, including grandfathered prices. The item whose price
resolves to a Plan is the plan item; everything else is an add-on. Two items
resolving to plans is still an error worth throwing on, because that genuinely
cannot be reasoned about.

While in `quotas.py`: `blockers()` reads `plan_terms` and
`Tenant.storage_used_bytes` and never adds `extra_storage_gb`, while
`Tenant.storage_quota_bytes` does. So a workspace holding purchased storage is
refused a plan change it would actually fit. That is a bug today, and add-ons
make it worse.

---

## Part 1 — One price history for every catalogue

`Plan Price` is a child table of eight fields — interval, Stripe price id, unit
amount, currency, `is_current`, created, archived — and the machinery in
`plans.py` that keeps exactly one row current per interval and archives the rest
is the whole of grandfathering. Add-ons need identical behaviour, and credit
packs need the archive-on-reprice half of it.

Three near-identical child tables would be the wrong answer in a repository that
guards against exactly that. So `Plan Price` is renamed **`Catalogue Price`**
and attached to all three parents. Frappe already stamps `parenttype` on every
row, so existing rows need no data migration — only `plan_for_price` gains a
`parenttype = "Plan"` filter, which it should have had anyway.

`billing/catalogue.py` takes the price-syncing logic out of `plans.py` and makes
it parent-agnostic: given a doc with `stripe_product_id`, a `prices` table and
an amount per interval, ensure the product, ensure the current price, archive
what it replaced. `plans.py` keeps the plan-specific parts (which field holds
the current id, what a Plan calls its amounts) and calls into it.

---

## Part 2 — The Add-on catalogue

A new **`Add-on`** doctype, sold per unit per month, mirroring `Plan`:

| Field | Type | Why |
| --- | --- | --- |
| `addon_code` | Data, unique, docname | `storage-50`, stable across renames |
| `addon_name` | Data | What a customer reads |
| `kind` | Select: `File Storage`, `Database Storage` | Which quota it adds to |
| `unit_gb` | Int | GB one unit buys |
| `max_units` | Int | 0 for no ceiling |
| `is_active`, `sort_order`, `description` | | |
| `currency`, `price_monthly`, `price_yearly` | | Both, because Stripe requires every recurring item on a subscription to share its interval |
| `stripe_product_id`, `stripe_price_id_monthly`, `stripe_price_id_yearly` | read-only | Written by the sync |
| `sync_error` | read-only | Same contract as Plan: saving never fails on Stripe being down |
| `prices` | Table → Catalogue Price | History |

`kind` and not a free-text field: the quota layer switches on it, and a third
kind is a code change either way.

**Database storage is a real product.** The Frappe Cloud server's disk is ours
in full; the per-tenant database limit is a number we choose and enforce, not
one press imposes. So both add-ons sell without touching the site's press plan.

---

## Part 3 — Add-ons on a subscription

A **`Subscription Add-on`** child table on `Subscription`:

| Field | Why |
| --- | --- |
| `addon` | Link → Add-on |
| `quantity` | Units held |
| `unit_gb` | **Captured**, like plan terms. A later edit to the Add-on does not move an existing customer. |
| `stripe_subscription_item_id` | How a quantity change addresses the right item |
| `stripe_price_id`, `unit_amount`, `currency` | What they are paying, captured |
| `added_on` | |

Captured rather than read live, for the reason `DECISIONS.md` §4 already gives
about plans: quotas are what was sold, not what the catalogue says today.

**The quota layer.** `quotas.for_tenant` and `for_subscription` gain an additive
pass: sum `quantity * unit_gb` per kind across the subscription's add-on rows,
add to `storage_gb` and `database_gb`. Everything downstream —
`Tenant.storage_quota_bytes`, `database_quota_bytes`, the sync payload, the
tenant's `enforce_quota` — already reads through those, so nothing else changes.
`Tenant.extra_storage_gb` keeps adding on top, and gains a sibling
`extra_database_gb`; both are operator grants with no price.

**Buying and changing.** One entry point, because "buy", "add more" and "cancel"
are the same operation at different quantities:

```
set_addon_quantity(tenant, addon, quantity) -> dict
```

* No subscription → refuse. An add-on without a subscription to hang from has
  nowhere to live and no invoice to appear on.
* `quantity == 0` → `deleted: true` on the item.
* New → `items=[{price, quantity}]`, `proration_behavior="create_prorations"`.
* Existing → `items=[{id, quantity}]`, same proration.
* Reducing below what is in use → refused, naming the resource, the same shape
  `change_plan` already refuses a too-small plan with.

Then capture the row and let the invoice arrive on the normal cycle.

`_reconcile_plan` gains a sibling `_reconcile_addons`, so an item added or
removed in the Stripe dashboard lands back on the Subscription rather than
drifting.

---

## Part 4 — Credit packs become a catalogue

A **`Credit Pack`** doctype: `pack_code`, `pack_name`, `credits`, `currency`,
`amount`, `is_active`, `sort_order`, `description`, `stripe_product_id`,
`stripe_price_id`, `sync_error`, `prices`. One price, not two — a pack is bought
once, so there is no interval.

`customer.packs()` reads the doctype; `CREDIT_PACKS` and `STORAGE_PACKS` go. The
amount still never comes from the client — `buy_credits(workspace, pack)` looks
the code up server-side, which is already the shape.

`start_credit_pack` uses the pack's Stripe price rather than inline
`price_data`, so a receipt names a product that exists and a reprice archives
the old price like everything else.

The one-off storage pack — `STORAGE_PACKS`, `buy_storage`,
`start_storage_pack`, `grant_storage_pack`, `kind=storage_pack` — is retired.
`books.record_storage_pack` stays: an operator grant is still worth a line in
the books.

---

## Part 5 — Promo codes

A **`Promo Code`** doctype that owns our half and lets Stripe own the money,
exactly as `Plan` does:

| Field | Why |
| --- | --- |
| `promo_code` | Data, unique, uppercase, docname. The string somebody types. |
| `description` | What it is for. An operator reads this in six months. |
| `is_active` | |
| `discount_type` | Select: `Percent`, `Amount` |
| `percent_off` / `amount_off` + `currency` | |
| `duration` | Select: `Once`, `Repeating`, `Forever` |
| `duration_in_months` | Shown when Repeating |
| `on_subscriptions`, `on_credit_packs`, `on_addons` | Check each. Scope. |
| `max_redemptions`, `expires_on` | Stripe enforces both |
| `first_time_only` | Stripe's `restrictions.first_time_transaction` |
| `stripe_coupon_id`, `stripe_promotion_code_id`, `times_redeemed`, `sync_error` | read-only |

`billing/promos.py` creates the Stripe **Coupon** (the money: percent or amount,
duration) and the **Promotion Code** (the string, redemption limits, expiry) on
save, and never raises — `sync_error` on the doc, same contract as plans.

A coupon's terms are immutable in Stripe once created. So changing a percentage
creates a new coupon and a new promotion code, and deactivates the old promotion
code; anybody already redeemed keeps what they were given. The same
grandfathering shape as a plan price, for the same reason.

**Scope is ours to enforce**, at the point a session is created: a checkout only
gets `allow_promotion_codes` or an explicit `discounts` if the code's scope
allows that kind of purchase. Stripe's own `applies_to.products` is set as well
where every target product is known, but the gate that matters is ours, because
it is the one that decides whether the field is even offered.

**Redemption.** `promo_code` is recorded on `Account Request` and on
`Subscription`, so "which workspaces are on a free code" is a filter rather than
a spreadsheet. `times_redeemed` is refreshed from Stripe when the operator opens
the screen and by the daily job, because Stripe is the one counting.

### The free instance, end to end

1. An operator makes `DEMO100`: Percent, 100, Forever, subscriptions only, five
   redemptions, expiring in a month.
2. Signup takes the code, validates it server-side against the chosen plan, and
   opens the checkout with `discounts=[{promotion_code: …}]` and
   `payment_method_collection="if_required"` — so Stripe asks for no card when
   the total is zero.
3. Stripe returns `payment_status="no_payment_required"`, which
   `handle_signup_paid` **already accepts**. Provisioning runs unchanged.
4. The subscription is real, at £0. `invoice.paid` fires for a zero invoice, so
   `grant_period_credits` runs and the demo gets its monthly AI credits.

The demo instance is not a special case anywhere. That is the point of choosing
this over a comp path: it behaves exactly like a paying workspace, which is what
makes it worth training on.

---

## Part 6 — Surfaces

**Customer**, on the account Space's Billing screen: add-ons as a stepper per
add-on showing what is held and what it costs, replacing the one-off storage
grid; the credit balance and `credit_history`, which is a live endpoint with no
UI today; a promo field where a code applies.

**Operator**, in the console: screens over `Add-on`, `Credit Pack` and
`Promo Code` — ordinary list screens, since all three are catalogues the Space
runtime renders for free — plus a **grant credits** action, because nothing in
the codebase can post a `Grant` by hand today and a goodwill credit currently
requires the desk.

---

## Part 7 — What this corrects on the way

* `quotas.blockers` ignoring `extra_storage_gb` — a plan change refused to a
  workspace that fits.
* `checkout._settings()` is dead code, never called.
* `PackCard.vue` hard-codes `$` and has no currency prop.
* `Credit Ledger Entry.validate_expiry` allows `expires_on` only on `Grant` and
  `Adjustment`, while the field's own description says "Grants only" and
  `Purchase` is the type packs use. An expiring promo credit has to be a `Grant`
  today; the description and the rule are made to agree.
* `Refund` is a valid entry type nothing ever posts.

---

## Part 8 — Order

| Batch | What | Ships alone? |
| --- | --- | --- |
| **A** | The plan item is found, not assumed. `blockers` counts purchased storage. | Yes — a fix, valuable regardless |
| **B** | `Plan Price` → `Catalogue Price`, and `billing/catalogue.py` | Yes — no behaviour change |
| **C** | The `Add-on` doctype and its Stripe sync | Yes — nothing consumes it |
| **D** | `Subscription Add-on`, the quota layer, buy/change/cancel | Needs A, B, C |
| **E** | `Credit Pack` doctype; retire the one-off storage pack | Needs B |
| **F** | Promo codes, and the free-signup path | Needs B |
| **G** | Customer and operator surfaces | Needs C–F |

A and B change nothing a customer can see. The first visible change is D.
