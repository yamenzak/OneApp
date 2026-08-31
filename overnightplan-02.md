# Overnight plan 02 — OneAdmin becomes a Space

**Status: A, B, C, D, E, F, G, I and J are built, tested and pushed.**

**H and K are deliberately not done**, and the reason is this plan's own:

* **K** retires `/admin` and `/portal` and deletes the control app's frontend.
  Part 11 says to do it "long after the operator Space is the thing you
  actually use", because until then `/admin` is a working fallback that costs
  nothing to keep. The operator Space is hours old and nobody has used it. That
  gate is time and use, and one night cannot supply either.
* **H** moves the control plane's settings into `oneapp`'s settings dialog. Its
  only consumer is K, and it would mean changing `require_owner` — the gate on
  a customer-facing surface — for a batch nothing is waiting on.

Everything built is additive: `/admin` and `/portal` are untouched and still
where an operator and a customer go.

## The decision

**One shell, two sites, Spaces everywhere.**

| | |
| --- | --- |
| `oneapp` | The shell and the Space runtime. Installed on **every** site — tenant and control. Owns no control-plane domain logic. |
| `oneapp_control` | Control-plane domain logic, and it **declares Spaces**. No SPA of its own. |
| Space source | Pluggable: `sync_from_control_plane` on a tenant, a local provider on the control site. |
| Tenant workspace | `acme.4dl.app/one` — unchanged. |
| Operator console | The control site's `/one`, an operator Space. Replaces `/admin`. |
| Customer account | The control site's `/one`, an account Space. Replaces `/portal/account`. |
| Between them | A rail entry that **navigates**. A link, with a redirect back. |

Two hostnames, one product.

### Why not the alternatives

**Merging the apps** stays rejected, for the reasons `ARCHITECTURE.md` §9 already
gives: every control-plane change would ship as a tenant-app version and trigger
`bench migrate` across every tenant site, and `Credit Ledger Entry`, `Tenant` and
the Frappe Cloud credentials would become real tables on customer-administered
sites. Nothing below requires it. The two apps stay separate deployment
artifacts and the control doctypes stay off tenant sites entirely, so §9 needs
no revision — only §9's *frontend* assumption changes, and that should be
written into it when this lands.

**An iframe of the portal inside the workspace** fails at the first request.
Frappe hardcodes `samesite="Lax"` on the `sid` cookie (`frappe/auth.py:416`), so
a cross-site iframe never receives a session and renders the login page in every
browser, permanently. Even patched to `SameSite=None; Secure` it would still be
a separate login against a separate User table, blocked by Safari's ITP, with no
shared theme, toasts, breakpoints or back button — and, fatally, its contents
would be the old bespoke SPA forever. An iframe is for when you cannot deploy
code into the other side. We own both sides.

**Keeping everything separate** is defensible and has a running cost:
`oneapp_control/frontend` is ~6,000 lines of Vue duplicating what `oneapp`
already does better, and everything in `overnightplan-01` — plus saved views,
realtime, the record pane and the mobile work — either gets built twice or never
reaches the console and the account area at all.

### What is explicitly deferred

**SSO.** Putting the account Space *inside* the tenant workspace needs
person-level identity across sites, and the reason is structural rather than
effortful: the HMAC channel proves a **site**, not a **person**
(`X-OneSpace-Tenant`, signed with that tenant's own secret). A hand-off from a
tenant site can be scoped safely — tenant A asserts only about tenant A, and can
therefore never show you tenancy B — or multi-tenant, in which case tenant A can
mint a session that reaches tenancies A does not own. There is no third option
at the site level, which is precisely why the person has to authenticate
somewhere that knows all their tenancies: the control plane.

That is what makes the account Space living on the control site the correct
destination rather than a stepping stone. SSO, when it comes, only removes a
hostname hop.

---

## Part 1 — The space-provider seam

Today a Space reaches a site exactly one way:
`sync.sync_from_control_plane()` → HMAC call → `OneSpace Site State.spaces_json`
→ `sync.state()` → `_space()`. The control site is not a tenant and has no
control plane to call, so it needs a second source for the same shape.

The seam is deliberately small, and it goes **below** `state()` rather than
beside it, so that everything downstream — `_space`, `_granted_doctypes`,
`visible_spaces`, the rail, the resolver — is untouched.

* A new hook, `onespace_space_providers`, listing dotted paths. Each returns the
  same list of space dicts `registry.spaces_for_tenant` already returns.
* `oneapp` ships none. A site with no provider and no sync is a site with no
  spaces, which is today's behaviour.
* `oneapp_control` registers one: `oneapp_control.entitlements.registry.local_spaces`,
  which is `spaces_for_tenant` without the entitlement join — on the control
  site there is no tenant, and the audience is decided by role.
* `sync.state()` merges provider output into `spaces` after reading the
  singleton. Providers run on the control site only because that is the only
  site where `oneapp_control` is installed; nothing needs to test for which kind
  of site it is.
* Cache: `state()` already caches under `CACHE_KEY` with a TTL, and
  `invalidate()` clears it. A provider's output must invalidate the same way —
  `OneSpace Space` gains an `on_update` that calls it, or the console edits a
  space and does not see it for the length of the TTL.

Permissions come along for free and should be stated so nobody re-solves it:
`visible_spaces()` (`api.py:56`) already filters by `role_name`, so an operator
Space with `role_name: "OneSpace Operator"` and an account Space with
`role_name: "OneSpace Customer"` separate cleanly per user on the same site.

The Custom DocPerms those roles need are written by `sync_permissions(manifest)`
on a tenant. On the control site they are written by `oneapp_control`'s own
install and migrate hooks from the same `OneSpace Space Doctype` child rows —
one function, two callers.

---

## Part 2 — Installing `oneapp` on the control site

`oneapp` no longer hard-requires erpnext (`hooks.py:8`), so it installs. Six
hooks meet `oneapp_control`'s. Each was checked; three are already safe and
three need work.

| Hook | What happens | Verdict |
| --- | --- | --- |
| `scheduler_events` → `sync_from_control_plane` every 15 min | `is_provisioned()` is false, returns `{"ok": False, "reason": "not_provisioned"}` and writes `last_sync_error` | **Safe.** Skip it when a provider is registered, so the singleton stops carrying a misleading error. |
| `doc_events` File `before_insert` → `enforce_quota` | `quota_bytes()` of 0 means unconfigured and returns early | **Safe as written.** |
| `doc_events` `*` `before_insert` → `enforce_database_quota` | reads a cached verdict; an absent verdict reads as "not over" | **Safe as written.** Confirm `refresh_database_verdict` writes no verdict when the quota is 0 before relying on it. |
| `override_doctype_class` File → `OneSpaceFile` (R2) | takes effect on the control site's attachments | **Needs the gate.** Falls back to Frappe when R2 is unconfigured, but the control site has its own storage story and must not silently acquire a tenant's. |
| `home_page` — `"one"` vs `"admin"` | two apps declare one value; resolution is install-order dependent | **Needs deciding.** Set it to `"one"` on the control site once `/admin` retires, and delete the collision rather than relying on ordering. |
| `role_home_page` — `{"OneSpace Customer": ["portal/account"]}` | only `oneapp_control` declares it | **Needs updating** to `one` when the account Space lands, then deleting. |

Two more things travel with the install and are not collisions, only facts to
know: `website_route_rules` gains `/one/<path:app_path>` on the control site
(no clash with `/admin` or `/portal`), and `oneapp`'s `after_install` runs there
— it must be idempotent and must not assume a tenant.

---

## Part 3 — The site_config gate, pointing both ways

The instinct is right; the mechanism should be `site_config.json` rather than an
environment variable. That is already how `oneapp_tenant`, `oneapp_control_url`
and `oneapp_hmac_secret` work: per-site rather than per-bench, managed by Frappe
Cloud, and readable as `frappe.conf`.

One key, two directions:

```
oneapp_role: "tenant" | "control"
```

* **Absent or `"tenant"`** — today's behaviour exactly. Sync runs, the File
  override is live, quotas enforce, no local space provider.
* **`"control"`** — the File override falls back to Frappe's own class, the
  tenant scheduler jobs are skipped, and local space providers run.

Deriving it instead of declaring it (say, "is `oneapp_control` installed?") is
tempting and wrong: it makes the safety property a consequence of an app list
rather than an explicit statement, and the failure mode is silent. A site should
have to say what it is.

`is_provisioned()` stays the separate question it is — a tenant that has not
been handed its identity yet is a third state, and conflating it with "not a
tenant" would make an orphaned site look deliberate.

---

## Part 4 — A permission fix this makes urgent

`_space()` (`spaceview.py`) resolves a space code out of `state()` and **does
not filter by role** — unlike `visible_spaces()`, which does:

```python
for space in sync.state().get("spaces") or []:
    if space.get("space_code") == space_code:
        return space
```

On a tenant site the exposure is limited: every space in state is entitled to
that site, and `_granted_doctypes` plus Frappe's own permissions mean a caller
without the role gets empty lists rather than data. What leaks is the space's
shape — its label, its screens, its nav.

On the control site that becomes a customer enumerating the operator console's
screen list by guessing a space code. Small, but it is the wrong direction, and
it is three lines:

**`_space()` applies the same `role_name` filter as `visible_spaces()`, and both
call one function.** This should land *before* a second audience shares a site,
not after — and it wants a test that a `OneSpace Customer` gets a
`PermissionError` for the operator space code rather than a payload.

---

## Part 5 — `/admin` becomes the operator Space

The control plane has 18 list doctypes, 4 child tables and 1 Single. That maps
cleanly onto screens, child grids and the settings dialog respectively.

**Screens** (`OneSpace Space Screen` rows, `role_name: "OneSpace Operator"`):

| Screen | Doctype | Replaces |
| --- | --- | --- |
| Tenants | `Tenant` | `pages/Tenants.vue`, `pages/Tenant.vue` |
| Provisioning | `Provisioning Job` | `pages/Jobs.vue`, `ops/JobsPanel.vue` |
| Shards | `Shard` | `pages/Shards.vue`, `NewShardDialog`, `EditShardDialog` |
| Standby | `Standby Site` | `ops/StandbyPanel.vue` |
| Signups | `Account Request` | `ops/SignupsPanel.vue` |
| Subscriptions | `Subscription` | `TenantBillingPanel.vue` (part) |
| Credits | `Credit Ledger Entry` | — |
| Reservations | `Credit Reservation` | — |
| Webhooks | `Stripe Webhook Event` | `ops/WebhookEventsPanel.vue` |
| Plans | `Plan` | `settings/PlansSettings.vue` |
| Regions | `Region` | `settings/RegionsSettings.vue` |
| Buckets | `Storage Bucket` | `settings/BucketsSettings.vue` |
| Spaces | `OneSpace Space` | `settings/SpacesSettings.vue`, `SpaceScreensSettings.vue` |
| Entitlements | `Space Entitlement` | `TenantSpacesPanel.vue` |
| AI models | `AI Model` | `settings/CatalogueList.vue`, `CatalogueForm.vue` |
| AI features | `AI Feature` | `settings/AiFeaturesSettings.vue` |
| AI usage | `AI Usage Record` | — |
| Support logins | `Support Login` | — |

**The Single** — `OneSpace Control Settings` — is not a screen. It belongs in
the workspace settings dialog, whose declarative group model
(`oneapp_core/workspace.py`, `GROUPS`) is exactly the right shape. That absorbs
`ControlSettings.vue`, `CloudflareSettings.vue` and `BillingSettings.vue`.

**The prerequisite, and it is a real one.** Four of these screens are unusable
without editable child tables: `Plan` needs `Plan Price`, `OneSpace Space` needs
`OneSpace Space Screen` and `OneSpace Space Doctype`, `Tenant` needs
`Tenant Member`, `AI Model` needs `AI Model Price`. That is **`overnightplan-01`
Batch 6** — the biggest item in the other plan. Plans, Spaces and the AI
catalogue cannot retire their bespoke settings panels until it lands; the other
fourteen screens can go first.

**What stays a `component:` escape hatch.** The manifest is a shortcut, not a
cage, and two surfaces are genuinely not lists:

* **Readiness / Setup** (`pages/Setup.vue`) — a checklist with blockers, not
  records.
* **The Press panel** (`PressPanel.vue`) — a live view of Frappe Cloud's own
  state, fetched from Press rather than stored here.

Both keep working unchanged as named components on operator screens.

---

## Part 6 — `/portal/account` becomes the account Space

Same machinery, `role_name: "OneSpace Customer"`, on the same site.

The account area is mostly not a list either — it is one workspace's overview,
billing, plan and people. So it is a smaller Space with more escape hatches, and
that is the correct answer rather than a compromise:

| Screen | Shape | Replaces |
| --- | --- | --- |
| Overview | component | `AccountOverview.vue` |
| Apps | component | `AccountApps.vue` |
| Billing | component | `AccountBilling.vue` |
| Plan | component | `AccountPlan.vue` |
| People | `Tenant Member` grid | `AccountTeam.vue` |
| Domain | component | `AccountDomain.vue` |

What it gains by being a Space rather than a second SPA: the rail, the mobile
shell, the More sheet, the settings dialog, theming, toasts, the record pane and
every future improvement, without a second implementation of any of them.

**The multi-workspace switch** — `customer.my_workspaces()` already exists and
`AccountResolve.vue` already routes on it. In the Space, the workspace being
looked at is the rail's own selection, which is what the rail is for. This is
the piece that would be impossible on a tenant site and is free here.

**A link, not an iframe.** The tenant workspace gets a rail entry — "Account" —
that navigates to the control site's `/one` and carries a redirect back. Plain
navigation, no cookie problem, no embedding.

---

## Part 7 — What cannot be a Space at all

**Signup.** `/portal/signup` is deliberately open to Guest (`www/portal.py`),
because it is the front door for somebody with no account. `oneapp`'s `/one`
redirects Guest to login (`www/one.py`), and it must keep doing so.

So signup **stays a separate route with its own small bundle**: `www/signup.py`,
`pages/signup/SignupPage.vue`, `SignupWelcome.vue`. It is the one part of
`oneapp_control/frontend` that survives, and it should be cut down to exactly
those two pages rather than left carrying the whole SPA. `role_home_page` sends
a customer to `one` after they finish.

---

## Part 8 — Cleanup, and the anchors that move

Deleting `oneapp_control/frontend` is most of the payoff and most of the risk of
breaking something unrelated, because several guards use it as their reference
copy of frappe-ui.

**Deleted** — `pages/Tenants.vue`, `Tenant.vue`, `Shards.vue`, `Jobs.vue`,
`Setup.vue` (moved to a component screen), `NotFound.vue`, all of
`pages/account/`, all of `components/ops/`, all of `components/settings/`,
`AppShell.vue`, `ConsoleSidebar.vue`, `PortalSidebar.vue`, `UserMenu.vue`,
`ThemeSetting.vue`, `UsageBar.vue`, `EmptyState.vue`, `PackCard.vue`,
`CreateTenantDialog.vue`, `NewShardDialog.vue`, `EditShardDialog.vue`,
`TenantBillingPanel.vue`, `TenantSpacesPanel.vue`, `router.js`, `lib/nav.js`.

**Kept** — `PressPanel.vue` and `Setup.vue` (as component screens, moved into
`oneapp`), the signup pages, and `lib/` where a signup bundle still needs it.

**Anchors that move.** These read the control app's `node_modules` and barrel as
the canonical frappe-ui copy, and each has to be repointed at `oneapp` before
the directory shrinks:

* `tests/frappe_ui_api.py:16` — `UI_SRC`
* `tests/test_frontend_guards.py:183, 213, 233, 330, 367, 458, 644`
* `tests/test_api_calls.py:187`, `tests/test_frappe_ui_calls.py:112`

This collides with `overnightplan-01` Batch 3, which also edits `UI_SRC` (to
reach `experimental/`). **Do the repoint first, in its own commit** — one change
to that constant at a time.

**The generator.** `scripts/gen_frontend.py` `APPS` (line 55) describes two full
SPAs. `oneapp_control` becomes a signup-only entry: `route: "/signup"`, no
`shells`, and its `types` list shrinks to whatever signup reads. `BRAND["admin"]`
stops naming a product surface and survives only as the app title — worth a note
where it is defined, because "OneAdmin" then means an app, not a place.

---

## Part 9 — Tests

| Test | Why it moves |
| --- | --- |
| `test_frontend_guards.py` | Reference paths, and `_local_components()` sweeps both apps |
| `frappe_ui_api.py` | `UI_SRC` |
| `test_api_calls.py`, `test_frappe_ui_calls.py` | `resource.js` path |
| `test_frappe_ui_usage.py` | `APPS` sweep |
| `test_portal_urls.py` | Reads `oneapp_control/frontend/src/router.js`, which is being deleted |
| `test_members.py:215-317` | Asserts against `AccountTeam.vue`, `AccountPlan.vue`, `AccountBilling.vue`, the router and `nav.js` — all deleted. The assertions are about *behaviour that must survive*, so they get rewritten against the account Space, not dropped. |
| `test_billing_plans.py:99` | Reads `PlansSettings.vue` — rewrite against the Plans screen |
| `test_no_desk.py` | `CONTROL_SRC` |
| `test_settings_dialog_geometry.py` | Control settings move into `oneapp`'s dialog |
| `test_press_admin.py` | `PressPanel` becomes a component screen |
| `test_customer_isolation.py` | The one to strengthen, not just move: two audiences now share a site |

**New tests worth having:**

* A `OneSpace Customer` gets `PermissionError` for the operator space code
  (Part 4), from `_space` and from every whitelisted resolver entry point.
* A site with `oneapp_role: "control"` does not use `OneSpaceFile`.
* A site with `oneapp_role: "control"` skips the tenant scheduler jobs.
* The local provider returns the same shape as `spaces_for_tenant` — one
  schema, asserted against both producers.
* Every screen in the operator manifest names a doctype that exists and a role
  that exists.

---

## Part 10 — Order

**Batch A — the seam, with nothing depending on it.** The
`onespace_space_providers` hook, `state()` merging providers, cache
invalidation, and the shape test. `oneapp_control` registers a provider that
returns `[]`. Nothing changes anywhere.

**Batch B — the permission fix.** `_space()` filters by role, shared with
`visible_spaces()`. Ships on its own because it is a fix, not a refactor, and it
is worth having on tenant sites regardless of whether any of this proceeds.

**Batch C — the gate.** `oneapp_role` in `site_config`, the File override
conditional, the scheduler skip, and their tests. Still nothing visible.

**Batch D — `oneapp` on the control site.** Install it, resolve `home_page`,
serve `/one` beside `/admin`. Both consoles exist at once; the new one is empty.
This is the checkpoint — if anything is wrong, `/admin` is still there.

**Batch E — the guard anchors.** Repoint `UI_SRC` and friends at `oneapp`, in
its own commit, before anything is deleted and before `overnightplan-01`
Batch 3 touches the same constant.

**Batch F — fourteen operator screens.** Everything not blocked on child tables.
`/admin` stays live and is compared against, screen by screen.

**Batch G — the two escape hatches.** Readiness and the Press panel move into
`oneapp` as component screens.

**Batch H — the settings dialog.** `OneSpace Control Settings`, Cloudflare and
billing become groups in `oneapp`'s dialog.

**Batch I — the account Space.** Six screens, the workspace switch, and the rail
link from the tenant workspace.

**Batch J — the child-table screens.** Plans, Spaces, AI catalogue, Tenant
members. *Blocked on `overnightplan-01` Batch 6.*

**Batch K — signup gets its own small bundle**, then delete
`oneapp_control/frontend`, retire `/admin` and `/portal`, and rewrite the tests
that pointed at them.

Batches A–C change nothing a user can see and are safe to ship independently.
The point of no return is K.

---

## Part 11 — Risks

**Bootstrapping.** After this, a bug in the space resolver takes out the console
you would use to fix it — and the desk is not an option by policy. Today
`/admin` is bespoke code that does not depend on the resolver, so this is a
genuinely new coupling. Two mitigations, and the first is not optional:

* **Retire `/admin` last** (Batch K), long after the operator Space is the thing
  you actually use. Until then it is a working fallback that costs nothing to
  keep.
* **A break-glass route** afterwards: a minimal server-rendered page listing
  tenants and shards with no SPA and no resolver, reachable by System Manager
  only. Ugly on purpose, and the thing you are grateful for at 2am.

**One site, two audiences.** The control site currently serves operators at
`/admin` and customers at `/portal` behind two different `get_context` guards.
After this both are `/one`, and the separation is entirely role-based — which is
why Part 4 is a prerequisite rather than a nice-to-have, and why
`test_customer_isolation.py` gets strengthened rather than merely moved.

**Deployment coupling.** `oneapp` becomes deployed to the control bench as well
as tenant benches, so a tenant-app release now affects the console too. That is
the trade: it is what makes "build once, get it everywhere" true. It argues for
the control bench tracking the same branch as production tenants rather than
`canary`.

**Fixture growth.** The operator Space is an `OneSpace Space` fixture with ~18
screen rows, and `fixtures` already exports that doctype. A hand-edited fixture
and a console that edits the same rows will fight. Decide once: the operator
Space is **owned by the fixture**, and editing it in the console is a
development-time act that gets exported back, exactly like a doctype.
