# The Marketplace, and where a customer administers their own workspace

Four questions asked together, because they turn out to be one seam: what the
operator console should become, which of the customer's own settings belong in
the workspace rather than on the control plane, how a private app like RUA is
discovered and claimed, and whether enabling one runs a migration.

Read `docs/ONEADMIN.md` §4 for the console as it stands and
`docs/APPS-AND-SPACES.md` for what decides which apps are on a site. This
document is the part that decides *who does the enabling, and where they stand
when they do it*.

**Where this has got to.** Built, all five stages. The marketplace screen, the
claim codes and the visible install are `entitlements/registry.py` with
`Marketplace.vue` and `Space Claim Code`; the split §2 argues for has happened,
so People, Roles and Domain are tabs in the workspace's own settings dialog and
the account Space is down to the four screens that are facts about an account —
Overview, Apps, Billing, Plan. What follows is the argument, kept because it is
why the shape is what it is.

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
    claim_code      the string somebody types, upper-cased on save
    app             which space it puts on their shelf
    uses_allowed    0 for unlimited
    uses_spent
    expires_on
    enabled
```

Redeeming is `registry.offer(tenant, app)` — not `grant`, which the sketch
said and which would have been the wrong verb: a code says "you may see this",
and pressing the card is still theirs to do.

Two things it added that the sketch did not have. **Every refusal is the same
sentence**, because a code is a guessable string and a reply distinguishing "no
such code" from "spent" from "expired" is a way to enumerate which codes exist
and which spaces we have built for other people. The one exception is
`assert_can_carry`, which names the app the bench lacks — and is right to,
because that is about their site rather than about our catalogue. And **a
second press by the same workspace is not a refusal and does not spend a use**:
somebody typing it again is somebody who did not notice it worked, so a one-use
code would otherwise retire itself on a double-click and then tell its own
redeemer it never existed.

The operator's other lever is the one that exists: entitle the workspace
directly, and the private space appears in their marketplace as available with
no code needed. That is the "explicitly exposed to a tenant from admin panel"
half, and it is `registry.offer` — a row with `offered = 1` and `enabled = 0`,
entitled to *see* and not yet turned on. The second flag is what tells that
apart from a revoked row, and `revoke` clears both, because leaving `offered`
on would put the card back in front of them with a button that works.

### What a card must say

The migration answer is a UI requirement. A card has four states, not two:
**available**, **installing** (an Install App job is running — with what it is
doing and roughly how long), **enabled**, and **unavailable** (the bench cannot
carry it, said with the app named). Collapsing the middle one is the difference
between a marketplace that is honest and one that appears to hang.

Building it found a fifth, and it is the one that matters most: **failed**. The
entitlement is written before the app arrives, so an install that fails leaves a
space that is enabled, in the launcher, and empty — which `entitlements/apps.py`
already names as the silent failure the whole mechanism exists to prevent. A
card that read that as "available" would be inviting the press that queues the
same job to fail the same way.

---

## 5. Stages

Ordered so each is worth having on its own.

1. **Three tabs move.** *Done.* People, Roles and Domain are workspace settings
   tabs calling the control plane through the seam that already exists. The
   account Space keeps Overview, Apps, Billing and Plan, and its docstring says
   which half of its argument survived.
2. **`Space Entitlement` gains "entitled to see".** *Done.* `offered`, and
   `registry.offer` beside `grant`: an operator can expose a private space to
   one workspace without installing anything for them.
3. **The marketplace screen**, reading the catalogue narrowed to what this
   workspace may see, with the four card states. Rail icon and app-switcher
   entry. *Done.* `/one/add`, offered in the rail to whoever can act on it.
   Pressing a card enables the space and pulls the manifest in the same
   request, so it is in the launcher rather than fifteen minutes away.
4. **`Space Claim Code`**, its two operator screens, and redemption. *Done.*
   Redeeming is `registry.offer` and not `grant`, which keeps one path through
   the marketplace rather than two: the four card states are the same four
   whether an operator put the space on the shelf or a code did. `Space Claim
   Redemption` is its own doctype rather than a child table, because the
   question an operator asks is "who has RUA and how did they get it", which is
   a list across codes.
5. **Install App, visible to the customer** — the card that started it says
   what is happening, and the space appears when it finishes. *Done.* The card
   reads the newest Install App job per app, looks again every fifteen seconds
   while one is running and not otherwise, and has a fifth state the study did
   not have: **failed**. A grant is written before its app arrives, so a space
   whose install failed is enabled, in the launcher and empty — and a card that
   went quietly back to "available" would invite somebody to press a button
   that queues the same job to fail the same way.

Stage 1 is independent of the rest and is the one a customer notices tomorrow.
Stages 2–4 are the marketplace. Stage 5 is the one that must not be skipped,
because it is the only one that is about the thing being slow.

---

## 6. What this does not decide

* **Whether any `General` space should cost money.** *Decided in part.* A
  customer may switch one on themselves, and every space a workspace has is now
  an entitlement — General spaces reached every launcher unconditionally until
  now, which is why there was nothing to add and nothing to turn off. What is
  still undecided is whether a particular General space should need paying for
  or asking for; that is a `Plan`/`Add-on` question and this document does not
  answer it. `OneSpace Space.on_by_default` is the lever in the meantime: on,
  and a new workspace starts with it; off, and they go and find it.
* **Uninstalling.** *Done.* Two verbs, because they are two acts. `disable`
  switches a space off: the app stays, the records stay, and it is undone in a
  second. `remove_space` also uninstalls whatever nothing else on the site
  still needs, which drops those apps' tables and everything in them. It is
  offered only where it would actually free something, it names which apps, the
  job's first step is a backup with files, the check is made again when the job
  runs rather than only when it was queued, and the confirmation is the
  workspace's own name typed out.

  A one-time code was considered and is the wrong instrument: it proves who is
  at the keyboard, and the risk here is *this* person pressing it without
  reading. Typing the name is the one gesture that cannot be done by accident.

  The one thing not proved: `press.api.site.uninstall_app` is the only call in
  the press client that has never run against a real Frappe Cloud.
* **Who may claim.** Redeeming a code changes what a workspace carries, so it
  is an owner's action rather than a member's; which role exactly is a question
  for whoever writes stage 4.

---

## 7. Looking at any of this on a dev bench

Four surfaces — People, Roles, Domain and the marketplace — reach the control
plane over a signed call, and a dev tenant site is not linked to one: the
fixture writes the manifest cache directly, because a linked site pulls it
every fifteen minutes and two sources of truth in a fixture is a race.

So on an unlinked site all four honestly say they cannot reach the account, and
`scripts/link_dev_control.py` is how you see the other answer. Run it on the
control site; it makes a Tenant the space site can prove it is, writes the two
missing keys into that site's `site_config.json`, and offers it one Restricted
space so the marketplace has a card. Restart the tenant server afterwards.

It is deliberately not part of `dev.sh seed`. Pressing a marketplace card pulls
the manifest, and on a linked dev site that replaces the fixture's own richer
cached copy — `dev.sh seed` puts it back, but a browser suite that ran in
between would have been reading something else.
