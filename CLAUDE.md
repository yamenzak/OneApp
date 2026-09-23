# Working on One

## How to answer me

I am the only person reading this and I already know what we are building.

* **Lead with the answer.** One or two sentences that would satisfy me if I read
  nothing else.
* **Under 150 words.** 300 if it is genuinely long.
* **No headers, no bold-label lists, no tables** unless I asked for a comparison
  or there are three-plus parallel items.
* **Say the thing, not the shape of the thing.** "The bell writes a
  `Document Follow` row" — not "**The control.** A bell beside the heart…".
* **Plain words, the way you would say them out loud.** Write it like you are
  explaining it to me at my desk. No aphorisms. No "it is not X, it is Y". No
  sentence that is there because it sounds good. If I have to read a line twice
  to get it, it failed — and a whole answer of clever lines is unreadable even
  when every fact in it is right.
* **The concrete thing first, the principle after** — and only if I need it.
  Name the file, the field, the button. "The photo has no GPS in it" beats
  "the photo answers who, never where".
* **One caveat, not five.** The one that would change what I do.
* **Do not restate work I just watched you do.** A commit hash and one line is a
  complete report.
* **Never re-explain a decision I already agreed to.**

Long form goes in commit messages, `docs/` and code comments. `/bro` means it
did not land — re-explain it simply.

## How fast a change should be

A one-line change should cost seconds, not a coffee. When it does not, it is
almost always one of these four, in this order of how much they cost:

* **Waiting on a background task by asking whether it is done.** Every check is
  a full round trip, and forty of them cost more than the thing being waited
  for. Start it in the background and *stop* — the harness sends a notification
  when it exits. Never poll a loop that greps for its own command line either:
  `pgrep -f "vite build"` matches the shell running the `pgrep`.
* **Believing a command that has not exited is still working.** It may have
  finished and be holding the pipe open for a child it accidentally adopted —
  which is what `dev.sh migrate` did for an hour after running the migration in
  ninety seconds. Before waiting any longer, look: `cat /proc/PID/wchan`. If it
  says `do_wait` the work is over and something else is keeping it alive.
* **Running the browser suite at all.** Don't. `yarn e2e` is 840 tests across
  two viewports — **fifty-one minutes**, measured — and even the narrowed
  `dev.sh e2e desktop` is tens of minutes. I am not paying that on a change,
  and no answer it gives is worth the wait. The gates are
  `python3 -m pytest -q`, `npx vitest run`, `npx eslint src e2e` and
  `npx vite build`, which are minutes between them, plus looking at the thing:
  `dev.sh watch oneapp &` and `yarn shot`.

  The specs stay in the repo. Run one, by name, only if I ask for it —
  `npx playwright test theme.spec.js --project=desktop` is seconds. Never
  `e2e`, never `e2e all`, never in the background "just to be sure": a run
  nobody asked for is the cost whether or not it passes. `scripts/affected.py`
  answering `all` is not a reason to start one; it is a reason to say which
  shared file widened it and move on.

* **Building to look at something.** `scripts/dev.sh watch oneapp &` once, and
  every edit is rebuilt into `public/frontend` — thirteen seconds against
  twenty-two for a cold `vite build`, and no step to remember. Only pay it when
  frontend source actually changed; a manifest or a Python edit does not.
* **Running a browser pass with no worker behind it.** `dev.sh up` starts a web
  server and nothing else, and the framework enqueues on its own — every
  notification, every `delete_doc` link sweep. Half an hour of Playwright fills
  the queue, Frappe refuses to enqueue past six hundred, and from then on
  everything that writes fails: the seed dies mid-way and leaves the fixture
  dirtier than it found it, `set_favourite` answers 503, and eight specs fail
  on assertions that have nothing to do with it. `dev.sh seed` and `dev.sh e2e`
  now refuse and name the fix, which is `scripts/dev.sh worker` in another
  shell, left running.
* **Writing a Playwright script to take a screenshot.** There is a command:
  `cd apps/oneapp/frontend && yarn shot '/one/space/rua?screen=projects'`.
  About four seconds, and `--wait=SELECTOR` is the flag worth knowing.

The loop, then: `dev.sh watch` in the background, edit, `yarn shot`, look. For a
manifest, a screen or a theme, `dev.sh seed --manifest` between the edit and the
look — one second rather than the full fixture's three.

Two things that are **not** the problem, measured rather than assumed: the
fixture (`dev.sh seed` is three seconds end to end) and the seeder's sweeps. And
one that cannot be fixed by trying harder: this box has four cores and the web
server is one GIL-bound Python process, so four Playwright workers buy about
1.4x, not 4x. Parallelism is not where the time is.

## Where things are

* **`docs/ARCHITECTURE.md`** — the map. Which directory owns what, where a
  change goes, and the rules the tests keep. Read this one first.
* **`docs/ONESPACE.md`** — the product. Spaces, screens, the four view bodies,
  the record, roles, collaboration, printing, the UI rules, what is not built.
* **`docs/ONEADMIN.md`** — the platform. Tenancy, the control plane, the
  operator console, billing, credits, storage, the lifecycle, configuration,
  bring-up, and how to work on this repo.
* **`docs/APPS-AND-SPACES.md`** — which Frappe apps a site carries, what a
  Space declares, and why per-customer schema is safe. Read it before touching
  provisioning or the space manifest.
* **`docs/EMAIL.md`** — mail. What Cloudflare gives us and what it does not, what
  the framework already ships, why Frappe Mail is not the answer, and the seven
  stages.
* **`docs/DRIVE.md`** — files. What Frappe Drive is (built on core `File`, which
  is what we already extend), the one part of it we must not copy, and the seven
  stages to one file manager every attach surface is a view onto.
* **`docs/WRITER.md`** — documents. Why a document is a `File` like a sheet is,
  what `frappe/writer` gave us and what its collaboration would cost, and why a
  version of a workbook and a version of a document are one doctype.
* **`docs/SHEETS.md`** — spreadsheets. Why every Python formula engine is
  copyleft and what follows from that, what RUA's Google Sheets integration
  actually did, and the seven stages to a sheet that feeds a document.
* **`docs/DOCUMENT-MAIL.md`** — the mail that belongs to a *record*. What links a
  message to a document today (almost nothing), what Frappe's own linking can and
  cannot reach, and where the AI lane earns its cost.
* **`docs/COLLABORATION.md`** — two people in one file. Why Yjs needed no
  second runtime after all, what the relay inside Frappe's own socketio
  refuses, what converges and what stays the stored form, and the five stages.
* **`docs/MARKETPLACE.md`** — where a customer administers their own workspace,
  and how a private app is discovered and claimed. Which of the account's seven
  screens belong in workspace settings and which cannot move, what the operator
  rework actually is (less than it sounds), and why enabling an app is sometimes
  a migration.
* **`docs/LEGAL.md`** — the agreements. Why each module writes its own clauses,
  how a version is `revision.hash` and what the guard that reads it back is for,
  who agrees to what and why it is asked twice.
* **`docs/ONEADMIN-SIMPLIFICATION.md`** — the operator console, audited screen
  by screen against one test: what does a person do here that a machine could
  not have. Why twenty of twenty-nine rail entries are places to go looking for
  a problem, what Frappe Cloud already knows that we ask to be typed, and the
  six stages to a console with one entry per question.
* **`docs/WORK.md`** — projects, tasks and the calendar over them, studied as
  one question rather than three arcs. What a task is and what an assignment is
  and why they stay two things, why the task doctype has to be ours rather than
  ERPNext's, why a board is a project, and how one calendar merge answers
  "mine", "the company's" and "this project's" without a second store. **Read
  it before touching OneTask, OneProject or the diary.**
* **`docs/ERP-SPACES.md`** — ERPNext, cut into three. Why OneProject, OneCRM
  and OneHR are three spaces rather than one, the rules a space over somebody
  else's schema follows, what each of the three is made of, the four fields
  added and the two hundred doctypes left out — and what opening every screen
  found.
* **`docs/HORILLA.md`** — the closest thing to a direct competitor, read against
  OneHR. Why its licence means ideas and not code, the four decisions about where
  things live that it gets right and we do not, what it has that we should build
  and what we should not, and what we have that it has nothing like.
* **`docs/DESK.md`** — following the framework, and the plan for it. What
  pulling `origin/develop` found: `@framework/ui`, a Vue/TS component library
  shipped inside frappe — `FormLayout`, `Fields`, `experimental/List`,
  `Filter`, `ConditionBuilder`, `ActivityTimeline`, `useDoctypeMeta` — which is
  the 22,000-line screen engine we wrote, and the island contract that says it
  has two hosts, the desk and a frappe-ui app. Which of our 109,000 lines it
  replaces, which 58,000 stay ours, the audit's terms of reference, the three
  guards, `frappe.watch`, and twelve stages. **Read it before writing any
  screen, field, list or record UI** — the answer is usually that the framework
  already ships it.
* **`docs/ALTERNATIVES.md`** — what else is out there. Two repositories that
  look like they do our job in a tenth of the code, why neither replaces what we
  have, where the impression that they are simpler comes from, and the four
  things worth taking from them.
* **`docs/UNIFICATION.md`** — the audit and the plan for making one product
  out of nine arcs. Twenty-two sections, each measuring one thing against the
  real code — the list engine, narrowing, actions, row states, fields,
  breadcrumbs, placement, the shell, URL state, time, feedback, uploads,
  mobile, and every app — then the synthesis: one root cause, six stages with
  a checkpoint each, and thirty-five rails. **Read F1 and F3 before starting
  any UI work**; they are the short parts and they are the ones that say what
  not to do.
* **`docs/CLEANUP.md`** — the audit and the plan for making one product out of
  nine arcs' worth of code. The two kinds (**space** and **microservice**) and
  the four roles every space has; what is measurably wrong and where it ends
  up; the two new spaces, OneAdmin and OneBook; going declarative; and twelve
  stages. **Read §1 and §2 before any structural work** — they are the
  terminology everything else is derived from.
* **`docs/FRAPPE.md`** — the framework under all of it, doctype by doctype. All
  296 Frappe ships, and which of the seven answers each gets: a screen, a
  manifest grant, a service the SPA calls by name, the engine's own,
  `NEVER_GRANTED`, a log named only to be excluded, or nothing. Frappe only —
  ERPNext and HRMS are `docs/ERP-SPACES.md`. `tests/test_frappe_coverage.py`
  reads it back against a snapshot `scripts/frappe_doctypes.py` writes.
* **`docs/ONEFORMS.md`** — the public surface, which is the one thing this
  product has none of. What Frappe v17's `Web Form` already gives (a token per
  recipient, a guest submission, a list scoped to one person's own records),
  what `bwhtech/forms_pro` is and why only its builder is worth taking, why the
  page is ours to draw rather than Frappe's portal, and the seven stages.
* `docs/PRINTING.md` and `docs/WORKSPACE-SETTINGS.md` are reference tables that
  tests read back.

**A module's own document lives beside it**, and every module has seven files:

    apps/oneapp/oneapp/<module>/
      README.md           what this is, the decisions that cost something,
                          and what is not built
      docs/collections.md   the doctypes it owns, and the ones it borrows
      docs/flows.md         what happens, in order, and where the logic lives
      docs/integrations.md  every seam — frappe, erpnext, hrms, and which
                            other spaces and services it reaches
      docs/permissions.md   who may do what, by role, and what guards check
      docs/notifications.md what it sends by default, to whom, on what event
      docs/ai.md            what OneAI does here, and what a tenant configures

**The README is the argument and the six are reference**, which is a split by
kind of reader rather than by subject: you look a thing up in the six, and you
read the README to find out why it is like that. A module with nothing to say
under one of the six writes one line saying so — "this module sends nothing" is
information and an absent file is not.

`docs/CLEANUP.md` §8 is the standard and `tests/test_module_docs.py` enforces
it, including that nothing module-owned is left in the root `docs/`. What stays
there is what genuinely has no single owner: this plan, the map, the product as
a whole, the cross-cutting subjects, and the arcs and audits that are history
rather than reference.

## Three rules that are nowhere else

* **OneApp is the repository name and is never product-facing.** The product is
  **One** — it was OneSpace and is not any more. `onespace` survives as an id
  and only as one: the Frappe module, the directory, the `OneSpace Space`
  doctypes and the controller classes Frappe imports by their doctype's name.
  Same rule as the line below it.
* **An id is not a name, and four of them disagree on purpose.** The products
  are **OneCloud**, **OneWriter**, **OneWorkbook** and **OneHR**; the ids
  under them are `onestorage`, `onedoc`, `onesheet` and `onehr`, and they are
  not going to change — they are Frappe *module* names written into
  `modules.txt` and into every generated doctype, space codes that appear in
  the URL, directory names, and the keys a manifest names a mark by. Same rule
  as the line above it. `ALIAS` in `scripts/gen_brand.py` is the whole of the
  map, and `MARKS[id].name` is the only place a name is written down: never
  type a product name where you could read one.
* **This repo is AGPL-3.0, and so are `frappe/central`, `frappe/atlas`,
  `frappe/crm`, `frappe/drive` and `frappe/sheets`.** So code may be taken from
  them — the licences match — and taking it carries three obligations that are
  not optional: keep Frappe's copyright notice, say at the top of the file what
  it was derived from, and never move that file back to a permissive licence.
  Prefer writing it ourselves where ours would be better; take theirs where
  theirs is a solved problem we would only be re-solving. Anything that is
  really a frappe-ui component still comes from frappe-ui, which is MIT and
  which we already depend on.
