# Fixtures

Imported on `bench migrate` via the `fixtures` hook.

## `plan.json`

Four plans: two Personal, two Commercial, entry at $22, non-rollover credit
grants. Plans differ only in **quotas** — storage, seats, workers and the monthly
credit grant. Every feature is available on every plan, which is why there are no
feature flags anywhere in the codebase.

**The numbers above the $22 entry point are placeholders.** Review the ladder,
and size `monthly_credit_grant` against measured model cost before going live —
that grant, not infrastructure, is the margin variable.

`stripe_price_id_monthly` and `stripe_price_id_yearly` are blank and must be
filled with real Stripe Price IDs before checkout will work.

## `onespace_space.json`

Intentionally absent. The app registry describes real products, so it is seeded
as those are built rather than invented here. Each entry needs an `space_code`, a
`module` in the `oneapp` app, and a `role_name` — the role is what actually
enforces access.
