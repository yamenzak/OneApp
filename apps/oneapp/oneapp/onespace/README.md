# OneSpace — the engine

The desk. Everything that turns a **declaration** into a working screen: a
space manifest arrives from the control plane, and what a person gets is a
rail, a list, a record, a board, a calendar, filters they can save, actions
they can press and permissions that hold.

Nothing in here knows what a quotation is. That is the whole claim: a space is
data, and the engine renders data. `onecrm/` and `onehr/` are behaviour over
somebody else's schema; this is what draws both.

`docs/ONESPACE.md` is the product — spaces, screens, the four view bodies, the
record, roles, collaboration, printing. `docs/ARCHITECTURE.md` is the map. This
file is the module.

## The two rules that make it safe to hand a customer

**The manifest is the allowlist, twice over.** A screen can only be reached
through a space the workspace is entitled to, and can only name a doctype that
space's permission manifest already granted. A screen is not a way to read
something the entitlement did not include.

**Permission is Frappe's, not ours.** Every read and write goes through the
ordinary DocPerms `sync_permissions` writes from that same manifest. The engine
reports what a user may do so the UI can hide what it must; it does not decide
it.

## What is in here, in three groups

**The resolver** — `spaceview/`, 24 files and the largest thing in the
repository. Its own `__init__` carries the layer map, and the order is the
import order: a module may use the ones above it and never the ones below,
which is what stops it becoming one 4,000-line module again.

**The tenancy** — `sync`, `control_client`, `site`, `spacelife`, `account`,
`expiry`, `restore`, `backup`, `retention`, `jobs`, `plans/`. A tenant site's
whole relationship with the control plane.

**The features that are not the engine** — `printing`, `notifications` and
`alerts`, `importer/`, `books`, `collab`, `link_preview`, `basemap`, `finding`.
Each is a candidate to leave, and `docs/CLEANUP.md` §3b is where that is
tracked. `finding` is the one that could not: it is a search *over the
manifests*, so it belongs wherever the manifests are read.

**The three screens the engine itself draws** — `homepage`, `configuration` and
`singles`. Any space may name one, and they are keyed with no space code in
front for that reason: keying them per space would be the same entry once per
app, which is the shape `docs/UNIFICATION.md` F1 is about.

## The decisions that cost something

**One box searches the screens, not the site — `finding.py`.** Frappe keeps
`__global_search` and we do not read it, which needed an argument and got a
measurement: on the dev site that index is 1,348 rows of which 1,022 are
`DocType`, 223 are `Report` and 55 are `Module Def`. It is the desk's own
metadata. Two things would be wrong with it even full — `MATCH … AGAINST`
matches whole words, so `Meri` does not find `Meridian`, and a hit is a doctype
and an id with no idea which screen shows it. Here a record is only ever
reachable *through* a screen, so a hit that does not name one is a row nobody
can open.

So the screens are the index. One `like` per screen the reader can open, which
sounds slow and was measured before it was written: 68 ms across all 146
doctypes the shipped manifests name, because one `get_list` with a `like` is
about half a millisecond. It inherits the list's three rules rather than
re-deciding them — the screen's own filters apply with `@me` resolved, only
fields the screen shows are searched, and every query is `get_list` under the
reader's own permissions.

And the other half needs no server at all: `api.session` already carries every
space with its screens, so **where to go** is filtered in the browser on the
keystroke. That is why the box is useful the instant it opens.

**A Single is a screen — `singles.py`.** A doctype with exactly one document
has no list, no record id and no New button, so every mechanism above passed
straight over one and it was reachable from the desk alone. A space declares
`"component": "single"` with a `document_type` and a `fields` list, and gets
the doctype's own form drawn by the component a record page uses.

Two things are checked rather than trusted, and both are because a screen key
arrives from a browser. The **doctype and the writable fields are the
manifest's**, so this is not a second way to open a doctype or to write a field
nobody put on the page. And a **verb beyond Save is named in `VERBS`**, keyed
by doctype and holding the whole dotted path — module, class, method — which is
checked against the document before it is called: a manifest that could name a
method would be a manifest that can call anything, and a bare method name would
survive an upgrade that moved the class.

It was OnePeople's first, for six HRMS Singles nobody could open. It moved here
in `docs/ONEBOOK.md` stage 2, when OneBook wanted the same page over ERPNext's
Opening Invoice Creation Tool: a doctype with one document, read and written,
has nothing to do with people. What stayed in OnePeople is the half that does —
find the people these filters describe, then do it to the ones that were
ticked.

**A screen is resolved against *this site's* metadata.** A space declares
little more than a doctype and a list of fieldnames; what each field is called,
what type it is, what a Select offers and whether this person may create come
from the tenant. The control plane could not know any of it without keeping a
copy that would be wrong the first time a field changed.

**A space's roles are the four, and `role_name` is a prefix.** `docs/CLEANUP.md`
§2. `seats.py` is the tenant half of the naming and
`oneapp_control/spaces/roles.py` is the other; the sync payload carries the
prefix and never the seats, which is why it is written down in exactly two
places.

**`_filters` returns both halves together**, in `spaceview/mail.py` and again
in OneMail, because a caller that took one half would be asking for every row
on the site. The shape makes the dangerous call impossible to write by
accident.

**A link is not a grant.** `get_list`, not `get_all`.

**The rail is the seat, not the space.** `navigable` narrows a space's screens
to the ones this reader can open, and a screen whose doctype *no* seat grants
stays visible on purpose — hiding it would turn a manifest mistake somebody can
see into one nobody can.

**A twin is `@me`.** `mine.py` resolves it, and the same resolution answers a
screen's filters, OneCalendar's `about` and OnePeople's assistant tools, so
**My leave** as a screen cannot come apart from "my leave" asked any other way.

## What is not built

1. **The phone answer.** `docs/DESKTOP.md` stage 7. The dock is desktop-only
   and a phone gets a different shape — which is also why the finder has no way
   in on a phone: no dock, and no Ctrl.
2. **A workflow builder.** A workflow is part of what an app *is*, so it ships
   with whoever owns the doctype. The runtime honours what it finds.
3. **The engine as a second desk.** `docs/CLEANUP.md` §6 — declarative enough
   that a tenant could build a space, which is the direction the whole arc
   points.
