# The development loop

Frappe Cloud is where tenants run. It is not where you develop.

A push to a mirror repo makes Frappe Cloud create an App Release, build a
**new bench image**, and then — only when you ask it to — move sites onto that
bench. That is minutes per change, and it restarts every site on the bench. It
is the right mechanism for shipping and the wrong one for "does this button
work".

Three loops, fastest first. Use the first one that can answer your question.

---

## 1. Local bench — seconds

Both apps are symlinked into a local bench, so an edit in this repo is live on
the next request. Nothing here touches Frappe Cloud.

```bash
scripts/dev.sh up          # MariaDB, Redis, and the site on :8000
scripts/dev.sh spa         # Vite dev server for the admin SPA (hot reload)
scripts/dev.sh restart     # after a Python edit
scripts/dev.sh migrate     # after adding a doctype, or pulling frappe
scripts/dev.sh shell       # a REPL bound to the site
scripts/dev.sh run FILE    # execute a script against the site
scripts/dev.sh login       # a session cookie for curl
scripts/dev.sh down
```

`ONEAPP_BENCH`, `ONEAPP_SITE` and `ONEAPP_PORT` override the defaults.

**A Python edit needs `restart`. An SPA edit needs nothing** — run
`scripts/dev.sh spa` and Vite hot-reloads, proxying `/api` to the local site
through frappe-ui's plugin, so the session cookie and CSRF token are real.

### Things that will bite you once

- **Frappe derives its log directory from the process working directory**, not
  from `sites_path`. Run from anywhere else and it writes to `<cwd>/../logs`,
  fails on the missing folder, and surfaces as a 500 raised *inside the
  exception handler* — the traceback names a logging path and says nothing
  about the request. `dev.sh` pins the cwd.
- **The site is resolved from the `Host` header.** `localhost:8000` looks for a
  site literally named `localhost` and 404s with "localhost does not exist",
  which reads like the site is broken rather than like the URL is. `dev.sh`
  pins the site instead.
- **`frappe develop` requires Python 3.14 and Node ≥ 24.** On older Node, yarn
  refuses the install with an engine error and leaves `node_modules` empty; the
  build then fails with `MODULE_NOT_FOUND`, pointing at the wrong problem.
- **`scripts/dev.sh build` is only for Frappe's own web assets** — the login
  page and anything server-rendered. Our SPAs never need it: Vite writes
  straight into the app's `public/` directory.

---

## 2. Patch a running Frappe Cloud bench — seconds, no image

`press.api.bench.apply_patch` hands a git diff to the agent, which runs
`git apply` **inside the running container**, optionally rebuilds assets, and
restarts the bench. No image build, no bench move.

```bash
scripts/live.py status     # what the bench runs, and what we have patched onto it
scripts/live.py push       # send everything since the deployed commit
scripts/live.py revert     # back to the deployed image
scripts/live.py watch      # push on every change
```

Credentials come from `ONEAPP_FC_ENV` (a file setting `PRESS_KEY` and
`PRESS_SECRET`); the bench group defaults to `ONEAPP_BENCH_GROUP`.

`push` reverts its own previous patch first, because the container is
cumulative and re-applying an overlapping diff conflicts on context that is
already changed. It reverts through **press's own `revert_patch`**, which
re-runs `git apply --reverse` against the stored patch file. Flipping the diff
by hand looks equivalent and is not — new-file and deleted-file hunks have to be
rewritten, and one mistake leaves the bench in a state where nothing further
applies.

Patch filenames must be unique **per bench, forever** — including ones already
reverted — or press refuses with "Patch already exists for &lt;bench&gt; by the
filename …". `live.py` labels each with a timestamp and a content hash.

For a one-off diff without the state tracking:

```bash
scripts/patch.sh oneapp_control > fix.patch     # everything not yet on origin/main
```

```python
from oneapp_control.press.client import PressClient

PressClient().apply_patch(
    release_group="<bench group>",
    app="oneapp_control",
    patch=open("fix.patch").read(),
)
```

Or paste the same file into the bench's **Patches** tab in the Frappe Cloud
dashboard, which needs no API credentials.

### Getting the base right

`git apply` needs exact context, so the patch has to be diffed from **the commit
the bench is actually running**, not from whatever looks close. Ask press rather
than infer it:

```python
info = PressClient().deploy_information("<bench group>")
# each app carries current_hash; App Release then gives the commit message,
# which is the monorepo subject line the mirror was synced from
```

Do not infer the base from the built asset hash. Two commits produce an
identical bundle whenever neither touched frontend source, so the hash points at
a range, not a commit — guessing wrong there is what makes the patch fail with
nothing useful to read, because the Agent Job output is not exposed to the API.

### Why UI changes cannot be patched yet

`build_assets` does **not** help. It runs `bench build` — Frappe's own esbuild —
which knows nothing about Vite, so our SPA is never rebuilt on the bench.
`update_inplace` uses the same call, so it does not help either. Only the image
build runs our Vite build.

That leaves shipping the built bundle inside the patch, which needs one thing we
did not have: **a committed lockfile**. Without one, Frappe Cloud resolves
dependency versions freshly on every build, so its bundle is not ours —
rebuilding the deployed commit locally produced different content hashes, which
means `www/admin.html` cannot be diffed against what is actually on the bench.

That was a production problem before it was a dev-loop one: two deploys of the
same commit could produce different bundles, and a transitive dependency could
break a release with no code change. `yarn.lock` is committed now (Frappe Cloud
installs with yarn). Until a deploy has run from a locked build, **UI changes
need a normal deploy**; backend changes patch fine.

### The SPA is the part that catches people

`build_assets` runs **Frappe's** bundler, which knows nothing about Vite. A
patch carrying only frontend *source* therefore changes nothing you can see, and
reports success while doing it.

So the built output has to travel inside the patch. `scripts/patch.sh` does
that, and two details there are load-bearing:

- `public/frontend/` and `www/*.html` are gitignored — correctly, they are build
  output — so they have to be forced into the diff explicitly.
- The diff needs `--binary`. The bundle ships woff2 fonts, and without it git
  writes a placeholder instead of the content and `git apply` refuses the whole
  patch with "cannot apply binary patch … without full index line".

Run `npx vite build` in `apps/<app>/frontend` first, or the patch carries a
stale bundle. Paths are rewritten to be relative to the app repo, because the
agent applies from `apps/<app>` in the container and knows nothing of this
monorepo.

`patch_config` is sent as a **nested object, not a JSON string**. Press does not
parse this one — it calls `.get()` on whatever arrives, so a dumped string comes
back as a bare HTTP 500 with `{"exc_type": "AttributeError"}` and nothing naming
the parameter. `bench.update_config` *does* parse its string, which is exactly
what makes this easy to get wrong; `tests/test_press_payloads.py` pins both.

`press.api.bench.update_inplace` is the sibling: it pulls real app releases onto
a running bench without building an image. It validates the hashes, so the
commits have to be pushed releases rather than arbitrary work in progress.

**Both write code that exists in no image, so the next deploy silently reverts
them** — images are built from git. That makes them right for chasing a bug on
a live bench and wrong as a way to ship. A fix that exists only as a patch
disappears the next time anything else deploys, and nothing warns you.

Reverting is the same call with the patch reversed, via the App Patch record.

---

## 3. Full deploy — minutes

What Frappe Cloud does on its own when app code is pushed. Note the two halves,
which are easy to conflate:

| | What it does | What it does not |
| --- | --- | --- |
| **`bench.deploy`** | builds a new image | move any site onto it |
| **`site.update`** | moves a site to the newest bench | build anything |
| **`site.migrate`** | runs patches on the *current* bench | bring new code |

A successful build changes nothing a customer can see until a site is updated
onto it.

We do not drive this. Frappe Cloud handles app updates and bench moves itself.
