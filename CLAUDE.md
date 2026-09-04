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
  `yarn e2e` is nine and a half minutes and it is a pre-commit gate, not a
  feedback loop. While iterating run the specs you are changing:
  `npx playwright test theme.spec.js --project=desktop`, which is seconds.
* **Building to look at something.** `scripts/dev.sh watch oneapp &` once, and
  every edit is rebuilt into `public/frontend` — thirteen seconds against
  twenty-two for a cold `vite build`, and no step to remember. Only pay it when
  frontend source actually changed; a manifest or a Python edit does not.
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
* **`docs/EMAIL.md`** — mail. What Cloudflare gives us and what it does not, what
  the framework already ships, why Frappe Mail is not the answer, and the seven
  stages.
* `docs/PRINTING.md` and `docs/WORKSPACE-SETTINGS.md` are reference tables that
  tests read back.

## Two rules that are nowhere else

* **OneApp is the repository name and is never product-facing.** The product is
  OneSpace; the operator console is OneAdmin.
* **`frappe/central`, `frappe/atlas` and `frappe/crm` are AGPL-3.0 and this repo
  is MIT.** Read them for patterns, never copy code. Anything that is really a
  frappe-ui component comes from frappe-ui, which is MIT.
