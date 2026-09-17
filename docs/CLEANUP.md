# The cleanup

Nine arcs have shipped and each one was right on its own. Together they have
left a codebase that is 93,000 lines of Python, 105,000 lines of browser code,
34,000 lines of comment, and no single answer to "where does a new space go".
This is the audit and the plan for making one product out of it.

**Nothing is live.** There are no tenants, so there are no migrations, no
patches and no compatibility to keep. Everything below may be deleted and
rewritten rather than adapted, and where a stage says "the old thing goes", it
goes.

Read §1 and §2 before touching anything. They are the terminology and the two
rules the rest of the plan is derived from.

---

## 0. Where we are

**This section is the rail.** It is updated at the end of every stage and it is
the only thing that has to be read to know where the arc stands. A context that
has lost everything else reads §0, §1 and §2 and can carry on.

| # | Stage | State |
| --- | --- | --- |
| 1 | Name the two kinds | **done** — `SPACE` / `SERVICE`; `SOON` is a state; `applet` gone |
| 2 | Four roles per space | **done** — `<prefix>-<Seat>`, one ladder, Audit derived |
| 3 | The directories move | not started |
| 4 | A docs folder per module | not started |
| 5 | The comments go | not started |
| 6 | The record page is extracted | not started |
| 7 | OneBook | not started |
| 8 | OneAdmin | not started |
| 9 | Declarative wiring | not started |
| 10 | The adapters | not started |
| 11 | Cross-integration | not started |
| 12 | Fields become services | not started |
| 13 | The tests | not started |

**Rules for the whole arc**, so a stage done later matches one done today:

* One stage, one commit, pushed. The commit message is the record of what
  landed and why; this table is the record of how far.
* A stage leaves the product working: `python3 -m pytest -q`, `npx vitest run`
  and `npx vite build` all green before the commit.
* Nothing is kept for compatibility. There are no tenants. If a stage says a
  thing goes, delete it rather than deprecating it.
* Where a stage changes a name, change it everywhere in the same commit —
  including the docs, the tests, the seeds and the fixtures. A half-renamed
  thing is worse than the old name.

---

## 1. Spaces and microservices

The word **space** currently means three different things, and that is the root
of several arguments this codebase has with itself.

It called them `SPACE`, `SURFACE` and `SOON` in `lib/shell/apps.js`; the
control plane called all of them `OneSpace Space`; the rail called the first
kind a space and the second an applet; `docs/WORK.md` §12 called OneTask an
applet and `docs/DESKTOP.md` called the same thing a window. Four words, three
of them for one idea, and `SOON` was a *state* wearing a kind's clothes.

From here there are exactly two kinds, and they are not a rendering detail —
they decide roles, storage, config and how a thing is reached:

**A SPACE is a department.** It owns a body of records that belong to one job
of work: OneCRM, OnePeople, OneProject, OneBook, OneAdmin, OneInventory. You
*enter* a space; it has a rail; it is bought, granted and role-scoped as a
unit; it owns doctypes.

**A MICROSERVICE is something every space uses.** OneCloud, OneWriter,
OneWorkbook, OneCode, OneMail, OneCalendar, OneTask, OneAI, OneLegal. You do
not enter it — it opens *over* whatever you are doing, as a window or an
island. Every member of the workspace has it. It owns no departmental records;
it owns a capability, and the records it touches belong to whichever space
opened it.

The test, when something is ambiguous: **can two workspaces have different
people in it?** A space can — the sales desk is not the payroll desk. A
microservice cannot; storage is storage.

Two consequences that fall straight out and are not negotiable later:

* A microservice has no role of its own. It is on for everybody with a seat.
  Where it needs to say no — a private file, somebody else's draft — that is
  the *record's* permission, which is the framework's, not a role of ours.
* A space's roles are the four in §2 and nothing else.

---

## 2. Four roles, everywhere

Every space used to invent its own: OneCRM had `rep` and `manager`, OnePeople
`employee`, `people` and `payroll`, OneMobility `viewer`, `planner` and
`feeds`, OneProject `member` and `manager`, RUA none at all. Eleven role keys
across five spaces, no two of which meant the same thing, and every grant table
had to be read from scratch to find out who could do what.

Every space now has exactly four, named `<SPACE>-<ROLE>`:

| Role | What it is |
| --- | --- |
| **User** | Does the work. Writes the records the space is about. |
| **Manager** | Runs the desk. Owns the tables the work is *measured* by — stages, targets, types, reasons. |
| **Audit** | Reads everything and writes nothing. The one that does not exist today and is asked for constantly. |
| **Admin** | The space's own settings and its people. |

So `HR-User`, `HR-Manager`, `HR-Audit`, `HR-Admin`; `CRM-User` and the rest.
Twenty roles for five spaces, and a person reading one space's grants has
learned all of them. The prefix is the space's `role_name`, which stopped being
a role and became exactly that; there is no bare prefix role.

**The first three are a ladder and Audit is derived.** A `DOCTYPES` row's
fourth element names the *lowest* seat that may do the thing and the seats
above inherit it, so "the manager owns the stages" is said once. No fourth
element is the User rung — which is what an unroled grant already meant, and is
why nearly every grant in the repository survived the change untouched. Audit
is not on the ladder: `registry.laddered` gives it Read on every doctype any
other seat reaches, so a space cannot ship an auditor who can write and cannot
forget to let one look at something.

The four live in `oneapp_control/spaces/roles.py` and a space module declares
no roles at all. The tenant half of the naming is `oneapp/onespace/seats.py`,
restated rather than imported because the sync payload carries the prefix and
never the seats; `test_shipped_roles.py` reads one against the other.

**Every feature is wired to the permission manager.** Not to a role key read in
Python — to Frappe's own permission model, so a custom role a workspace makes
in the One space gets exactly the access its grants say and no code has to
learn about it.

**Custom roles stay possible.** The One space is where a workspace adds its
own, enables features on it, and assigns people. The four are the shipped set,
not the only set.

---

## 3. What is actually wrong, measured

### 3.1 The engine is a monolith with a department inside it

`onespace/` is 28,626 lines — 41% of the app — and `onespace/spaceview/` alone
is 8,324 across 23 files. Inside it are things that are unarguably the engine
(resolving a screen, running a list, checking a permission) and things that are
unarguably a feature (printing, backups, the importer, the AI chat, plans).

`onespace/` should be the engine and nothing else. Everything in it that a
space could live without moves out.

### 3.2 Every space reimplements the same record page

`components/screen/records/` has eight bespoke record views — `PersonRecord`,
`CandidateRecord`, `OpeningRecord`, `DayRecord`, `PayslipRecord`,
`AbsenceRecord`, `BoardingRecord`, `PlaceRecord`. Seven of the eight are
OnePeople's. They share a shape nobody extracted: an eyebrow, a title, a badge,
a fact row, and one block that is specific.

The specific block is the only part worth writing per doctype. The rest is a
component that does not exist yet, and the ninth space will write an eighth
copy unless it does.

### 3.3 Comments outnumber several modules

34,000 lines of comment: 11,491 Python comment lines, ~22,332 in the browser
code. Some of it is load-bearing argument and most of it is narration of what
the line below does.

They all go. Two developers, both of whom can read the code, and a comment that
has drifted from its line is worse than no comment. What is worth keeping is
the *argument* — why a thing is the way it is — and that belongs in `docs/` and
in the module README the architecture doc already asks for.

### 3.4 Ownership is scattered

There is no single answer to where an entity lives:

* A **customer** is written by OneCRM and read by OneBook and OneProject.
* An **employee** is OnePeople's, and OneProject's timesheets point at one.
* **Accounting** happens in OneHR's payroll, OneProject's billing and
  OneCRM's quotations, with no space owning the ledger.
* **Storage** is OneCloud's, and four modules write `File` rows directly.

Nobody owns anything, so everybody half-owns everything.

### 3.5 The tests do not know about roles

71 spec files, 16,758 lines, and the fixtures are one seeded workspace read as
Administrator. There is no test anywhere that a `rep` cannot do a `manager`'s
job, which is the single most important claim §2 makes.

---

## 4. Where things end up

    apps/oneapp/oneapp/
      engine/            the desk: resolve, list, record, views, permissions
      spaces/            one directory per space, self-contained
        onecrm/ onehr/ oneproject/ onebook/ oneadmin/ oneinventory/
      services/          one directory per microservice
        onecloud/ onewriter/ oneworkbook/ onecode/ onemail/
        onecalendar/ onetask/ oneai/ onelegal/
      adapters/          the seams: frappe, erpnext, hrms
      shared/            what genuinely has no owner

A space directory holds everything about that space: its manifest, its
doctypes, its controllers, its verbs, its config page, its seeds, its tests and
its browser screens. Opening one directory tells you what a space is. Adding a
space is adding a directory.

---

## 5. The two new spaces

**OneAdmin** is the operator console, which today is a separate Frappe app with
its own 2,609-line SPA. It becomes a space like any other, with two jobs —
tenancy and accounts — and it is the proof that the space model is real: if the
console cannot be built out of the engine, the engine is not finished.
`docs/ONEADMIN-SIMPLIFICATION.md` already audited its 32 screens down to what a
person actually does; that audit is the screen list.

**OneBook** owns money. Every ledger in the product: OnePeople's payroll,
OneProject's billing, OneCRM's quotations-become-invoices. The other spaces
*raise* things; OneBook is where they are posted, reconciled and reported. The
mark is already drawn and `apps.js` already lists it.

---

## 6. Declarative, and the second desk

The largest single idea here.

Today a screen is declared in a manifest and drawn by an engine, which is
right — and everything *around* the screen is hand-written: the config page,
the actions, the record views, the seeds, the roles, the tests. The manifest
stops at the edge of the list.

The end state is that a space is **entirely declarative**: doctypes, screens,
views, record layouts, actions, roles, config, seeds and fixtures, all
declared, all discovered automatically, with Python only where behaviour
genuinely runs on save. That is what "another Frappe desk" means — not a copy
of their UI, but their move: the interface is data.

Two things this buys that are worth the work on their own:

* **Wiring stops being written.** A doctype declared in a space is registered,
  granted, screened, seeded and tested because it was declared, not because
  somebody remembered six files.
* **A workspace can build a space.** Once a space is data, a tenant — or an AI
  acting for one — can make one out of doctypes, custom fields and scripts,
  with no deployment. That is the door this opens and the reason it is worth
  more than the tidiness.

---

## 7. Cross-integration

Each space and microservice is projected onto every other, deliberately, rather
than integrated when somebody notices:

* **Entities live once.** OneCRM owns parties. OnePeople owns people. OneCloud
  owns files. OneBook owns ledgers. Everything else links.
* **Frappe, ERPNext and HRMS are used to the hilt** — their doctypes, with our
  custom fields added through fixtures, never a parallel schema.
* **Opening is in-context.** Managing a project's billing opens OneBook over
  the project, the way a sheet opens OneWorkbook today: an island or a window,
  never a navigation away.
* **The seams are adapters**, one per foreign app, so "what we changed about
  ERPNext" is a directory rather than a search.
* **OneAI is the connective tissue.** A message arrives; OneAI proposes the
  task, the person and the party it concerns; OneTask, OnePeople and OneCRM
  receive it. Each per-action AI behaviour is configurable by the tenant —
  their context, their model — in the AI config manager.

---

## 8. Where a document lives

**Every module owns its documentation, in `docs/` beside its code.** Not a
README — a folder, because one file cannot hold what a module has to say and a
single long file is one nobody edits.

    apps/oneapp/oneapp/<module>/docs/
      collections.md      the doctypes it owns, and the ones it borrows
      flows.md            what happens, in order, and where the logic lives
      integrations.md     every seam: frappe, erpnext, hrms, and which other
                          spaces and services it reaches or is reached by
      permissions.md      who may do what, by role, and what the guards check
      notifications.md    what it sends by default, to whom, on what event
      ai.md               what OneAI does here and what a tenant may configure

Every module has all six. A module with nothing to say under one of them writes
one line saying so, which is information — "this module sends nothing" is worth
knowing and an absent file is not.

**Nothing module-specific lives in the root `docs/` any more.** What stays
there is what genuinely has no single owner: this plan, the arcs and audits
that are history rather than reference, `ARCHITECTURE.md`, and the two
reference tables the tests read back. Everything else moves into the module
that owns it, and `CLAUDE.md`'s index shrinks to match.

The test for where something goes: **if exactly one module would have to change
when this sentence stops being true, it belongs to that module.**

---

## 9. Stages

Each is a checkpoint, each leaves the product working, and each is one commit
or a short series.

1. **Name the two kinds.** `SPACE` and `SERVICE` in the registry, the manifest,
   the tests and the docs. No behaviour, all terminology. *Checkpoint: nothing
   says applet, surface or soon any more.*
2. **The four roles.** Every space's grants rewritten to User / Manager / Audit
   / Admin, wired to the permission manager. *Checkpoint: a `CRM-User` cannot
   edit a stage, and a test says so.*
3. **The directories move.** `engine/`, `spaces/`, `services/`, `adapters/`.
   Imports follow; nothing else changes. *Checkpoint: one space, one
   directory.*
4. **A docs folder per module** — §8. Six files each, and the root `docs/`
   emptied of everything a module owns. *Checkpoint: every module answers all
   six questions, and a guard says so.*
5. **The comments go.** The argument worth keeping is already in §8's files by
   then. *Checkpoint: 34,000 lines lighter, tests unchanged.*
6. **The record page is extracted.** One component, one declared layout, eight
   bespoke views deleted. *Checkpoint: OnePeople's screens are declarations.*
7. **OneBook.** The ledger, and payroll and billing posted into it.
   *Checkpoint: a payslip and a project invoice are in one place.*
8. **OneAdmin.** The console rebuilt as a space; `oneapp_control`'s SPA
   deleted. *Checkpoint: the operator uses the same desk as everybody.*
9. **Declarative wiring.** Discovery replaces registration, everywhere.
   *Checkpoint: adding a doctype to a space is one declaration.*
10. **The adapters.** One directory per foreign app. *Checkpoint: what we
    changed about ERPNext is readable in one place.*
11. **Cross-integration.** Entities owned once, opened in context, OneAI in the
    middle. *Checkpoint: mail proposes a task, a person and a party.*
12. **Fields become services.** Code editor → OneCode, prose → OneWriter, grids
    → OneWorkbook. *Checkpoint: no field type has its own editor.*
13. **The tests.** One fixture, one spec per action per role. *Checkpoint: every
    role's every action is exercised.*

---

## 10. What this is not

* Not a rewrite of what works. The list engine, the view types, the manifest
  idea, the theme system and the window shell all stay; they are being given a
  place to live rather than replaced.
* Not a UI redesign. The desk looks the same on the other side of this.
* Not staged for safety. There are no tenants; stages exist to keep each
  commit readable, not to protect anybody.
