# Working on OneSpace

## How to answer me

I am the only person reading this and I already know what we are building.

* **Lead with the answer.** One or two sentences that would satisfy me if I read
  nothing else.
* **Under 150 words.** 300 if it is genuinely long.
* **No headers, no bold-label lists, no tables** unless I asked for a comparison
  or there are three-plus parallel items.
* **Say the thing, not the shape of the thing.** "The bell writes a
  `Document Follow` row" — not "**The control.** A bell beside the heart…".
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
* **Running the whole browser suite for a change that touched three files.**
  `yarn e2e` is 263 specs across two viewports — half an hour — and it is a
  pre-commit gate, not a feedback loop. `scripts/dev.sh e2e` runs only the specs
  the change can actually break, worked out from the imports and the names the
  specs use rather than from memory; it answers `all` for a shared file or
  anything it cannot place, which is the direction worth failing in. While
  iterating on one thing, run that one thing:
  `npx playwright test theme.spec.js --project=desktop`, which is seconds.
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
* **`docs/ALTERNATIVES.md`** — what else is out there. Two repositories that
  look like they do our job in a tenth of the code, why neither replaces what we
  have, where the impression that they are simpler comes from, and the four
  things worth taking from them.
* `docs/PRINTING.md` and `docs/WORKSPACE-SETTINGS.md` are reference tables that
  tests read back.

**A module's own document lives beside it**, at
`apps/oneapp/oneapp/<module>/README.md` — one per module, covering both its
server and its browser half. `docs/` keeps only what no single module owns. The
standard those files follow is in `docs/ARCHITECTURE.md`, under "Where a
document goes"; `apps/oneapp/oneapp/onemobility/README.md` is the first written
to it.

## Two rules that are nowhere else

* **OneApp is the repository name and is never product-facing.** The product is
  OneSpace; the operator console is OneAdmin.
* **This repo is AGPL-3.0, and so are `frappe/central`, `frappe/atlas`,
  `frappe/crm`, `frappe/drive` and `frappe/sheets`.** So code may be taken from
  them — the licences match — and taking it carries three obligations that are
  not optional: keep Frappe's copyright notice, say at the top of the file what
  it was derived from, and never move that file back to a permissive licence.
  Prefer writing it ourselves where ours would be better; take theirs where
  theirs is a solved problem we would only be re-solving. Anything that is
  really a frappe-ui component still comes from frappe-ui, which is MIT and
  which we already depend on.
