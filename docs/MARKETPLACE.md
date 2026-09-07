# The Marketplace, and where a customer administers their own workspace

Four questions asked together, because they turn out to be one seam: what the
operator console should become, which of the customer's own settings belong in
the workspace rather than on the control plane, how a private app like RUA is
discovered and claimed, and whether enabling one runs a migration.

Read `docs/ONEADMIN.md` §4 for the console as it stands and
`docs/APPS-AND-SPACES.md` for what decides which apps are on a site. This
document is the part that decides *who does the enabling, and where they stand
when they do it*.

---

## 1. The short answers

**Does enabling an app run a migration?** Sometimes, and the machinery for it
already exists. A space declares `requires_apps`; a tenant's site installs the
union of what its granted spaces need rather than everything on the bench. So:

* the app is already on the site → the grant is a row and a role, and takes
  effect on the next sync. No migration, seconds.
* the app is on the bench but not the site → `registry.grant` queues an
  **Install App** job (`install_app` → `await_agent` → `finalise_install`),
  which runs that app's patches against a live database. Minutes, and it can
  fail, which is why it is a provisioning job with its own state rather than a
  function call.
* the bench cannot carry it → refused outright, with the app named.
  `apps.assert_can_carry` is the check, and it runs *before* the entitlement
  row is written.

RUA needs `erpnext,hrms`. Most sites that would claim it already have them, so
most claims are the first case. The marketplace has to be honest about the
second one anyway: a card that says "enabled" while patches are still running
is a card that lies for four minutes.

**Is the operator console already "our pattern"?** Largely, yes — this is worth
knowing before planning an overhaul. It is a Space declared in
`entitlements/operator.py`: 23 screens over its own doctypes, plus three
`component` screens that genuinely are not lists (Readiness, Frappe Cloud,
Workspace). The rework left is narrower than "overhaul" suggests, and §3 says
what it actually is.

**Should the customer's self-service move into workspace settings?** Partly,
and the split is not arbitrary. `entitlements/account.py` argues its own case in
its docstring and the argument is sound for half its screens and wrong for the
other half. §2.

---

## 2. Where the customer's own administration belongs

`entitlements/account.py` is a Space on the **control plane** with seven
screens: Overview, Apps, Billing, Plan, People, Roles, Domain. Its docstring
makes the case for staying there:

> A tenant site's HMAC secret proves it is *itself* and nothing more, so a
> tenant can never show you the other two tenancies you own. The control plane
> is the one place that knows a person owns three, which is why the account area
> belongs here — not as a stepping stone to putting it inside a workspace, but
> as the destination.

That is correct, and it is correct about **billing**. It is not an argument
about People or Domain, and reading it as one is how all seven ended up in the
same place.

The dividing question is not "is this administration?" but **whose fact is it?**

| Screen | Whose fact | Where it belongs |
|---|---|---|
| Billing | The account's — one card pays for three workspaces | Control plane. Unmovable, and for the stated reason. |
| Plan | The account's, mostly — a plan is bought, and a person with three workspaces compares them | Control plane, with the workspace's own quota reading shown in Storage where it already is. |
| Overview | The account's — it is the list of workspaces | Control plane. It is the thing you are switching *between*. |
| People | The workspace's — who is in *this* workspace | **Workspace settings.** |
| Roles | The workspace's — a role is built out of that workspace's own doctypes | **Workspace settings.** It is already half there: the workspace's role builder is a tenant-side surface. |
| Domain | The workspace's — one workspace, one domain | **Workspace settings**, beside Branding and Sign-in, which are the same kind of fact. |
| Apps | Both — a catalogue is the platform's, an entitlement is this workspace's | **Split.** §4. |

Four of the seven are facts about one workspace, and a person editing them has
no reason to leave it. Three are facts about an account that owns several, and
moving those into a workspace would mean each workspace claiming to speak for
the others — which is exactly the boundary the HMAC secret exists to hold.

So the answer to "should we move self-service so they do not change URL" is
**yes for People, Roles and Domain, and no for Billing, Plan and Overview** —
and the reason it is not "yes for all seven" is worth keeping written down,
because the pull is always toward one more.

The tenant settings dialog already has the shape for the three that move: a
Workspace section with Branding, Sign in, Regional, Books, Printing and the
rest. People, Roles and Domain are three more tabs in it, and their servers are
whitelisted methods on the control plane called through the tenant — which is
the same seam `sync` already crosses.

---

## 3. What the operator rework actually is

The console follows the pattern already. What it does not yet have is the
three things this document's other half needs, plus one debt:

**A. Somewhere to run the marketplace from.** Making a space claimable, minting
a claim code, and seeing who claimed one are operator actions over data that
does not exist yet (§4). Two screens and one declared action.

**B. The self-service screens that move lose their operator counterpart.**
People and Roles exist twice today — once in the account Space, once in the
workspace. When they move, the account's copies go, and the operator's view of
a tenant's members stays where it is, on the Workspace screen, because an
operator looking at somebody else's workspace is a different question from a
customer looking at their own.

**C. Install App has no surface.** `docs/ONEADMIN.md` §4 lists five doctypes an
audit found with no surface and says they were given one; the Install App job
runs as a `Provisioning Job`, which does have a screen. What is missing is the
*customer's* view of it: a claim that is three minutes from finishing should say
so on the card that started it.

**The debt**: the three `component` screens are the escape hatch, and the
escape hatch has been used three times in twenty-six. That is a healthy ratio
and not something to overhaul. An overhaul that turned Readiness into a list
would make it worse.

So: not an overhaul. Two new screens, one action, three tabs moved out, and one
progress surface.

---

## 4. The marketplace

### What already exists

Nearly all of the model. `OneSpace Space.availability` is `General` or
`Restricted`; `Restricted` means "only via `Space Entitlement`", which is
precisely a private app. `registry.grant` and `revoke` write that row and
reconcile the site's apps. `spaces_for_tenant` is what the launcher renders.
The customer-facing `customer.apps` endpoint already separates *what every plan
carries* from *what was granted to this workspace specifically* — "why do we
have this?" already has an answer.

What is missing is the **discovery half**: today a space arrives because an
operator granted it. Nothing offers one.

### What a marketplace adds

A rail icon and a mobile app-switcher entry, opening a catalogue of spaces this
workspace could have but does not. Three kinds of row, and the difference
between them is the whole design:

1. **Enabled** — a space they have. Opens it.
2. **Available** — `General`, not yet enabled. One button, and pressing it is a
   grant they may make themselves.
3. **Private** — `Restricted`. Not listed at all unless either an operator has
   exposed it to this workspace, or the person has a claim code.

RUA is the third. "Not listed at all" is the important part: a marketplace that
shows a locked card for every private app tells every customer the names of
every bespoke solution we have built for every other customer. The catalogue a
workspace is shown must be the catalogue it is entitled to *see*, which is a
narrower thing than the catalogue that exists.

### The claim code

A code is a row, not a coupon. `Promo Code` is Stripe-backed and about money;
this is about entitlement and should not borrow it.

```
Space Claim Code
    code            the string somebody types
    app             which space it claims
    uses_allowed    0 for unlimited
    uses_spent
    expires_on
    enabled
```

Redeeming is `registry.grant(tenant, app)` with the checks it already makes,
plus the two a code adds: it exists and has uses left. Every refusal already
has its sentence — `assert_can_carry` names the app the bench lacks.

The operator's other lever is the one that exists: entitle the workspace
directly, and the private space appears in their marketplace as available with
no code needed. That is the "explicitly exposed to a tenant from admin panel"
half, and it is `registry.grant` with `enabled = 0` — entitled to *see*, not yet
enabled — which is one field this model does not have yet and needs.

### What a card must say

The migration answer is a UI requirement. A card has four states, not two:
**available**, **installing** (an Install App job is running — with what it is
doing and roughly how long), **enabled**, and **unavailable** (the bench cannot
carry it, said with the app named). Collapsing the middle one is the difference
between a marketplace that is honest and one that appears to hang.

---

## 5. Stages

Ordered so each is worth having on its own.

1. **Three tabs move.** People, Roles and Domain become workspace settings tabs
   calling the control plane through the seam that already exists. The account
   Space keeps Overview, Billing and Plan, and its docstring is corrected to say
   which half of its argument survived.
2. **`Space Entitlement` gains "entitled to see".** One field. An operator can
   expose a private space to one workspace without enabling it.
3. **The marketplace screen**, reading the catalogue narrowed to what this
   workspace may see, with the four card states. Rail icon and app-switcher
   entry.
4. **`Space Claim Code`**, its two operator screens, and redemption.
5. **Install App, visible to the customer** — the card that started it says
   what is happening, and the space appears when it finishes.

Stage 1 is independent of the rest and is the one a customer notices tomorrow.
Stages 2–4 are the marketplace. Stage 5 is the one that must not be skipped,
because it is the only one that is about the thing being slow.

---

## 6. What this does not decide

* **Whether a customer may enable a `General` space without asking.** The model
  allows it and the marketplace assumes it. If any General space should cost
  money or need a word first, that is a `Plan`/`Add-on` question and this
  document does not answer it.
* **Uninstalling.** `revoke` disables the entitlement and leaves the app on the
  site, which is right — the data is theirs — but nothing reclaims the space an
  unused ERPNext takes. That is its own piece of work.
* **Who may claim.** Redeeming a code changes what a workspace carries, so it
  is an owner's action rather than a member's; which role exactly is a question
  for whoever writes stage 4.
