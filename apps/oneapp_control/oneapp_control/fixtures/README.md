# Fixtures

Imported on `bench migrate` via the `fixtures` hook.

**`plan.json`** — four plans, $22 to $249. They differ only in quotas: storage,
seats, workers and the monthly credit grant. Every feature is on every plan,
which is why there are no feature flags anywhere in the codebase.

Two things to do before going live. The tiers above $22 are placeholders — size
`monthly_credit_grant` against measured model cost, because that grant is the
margin variable rather than infrastructure. And `stripe_price_id_monthly` /
`_yearly` are blank; saving a plan mints them, and checkout does not work until
it has.

**`region.json`** — one region, Nuremberg. A region is selectable at signup only
while a shard in it has headroom.

**`onespace_space.json`** — deliberately absent. The registry describes real
products, so it is seeded as those are built rather than invented here.
