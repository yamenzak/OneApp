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

```python
from oneapp_control.press.client import PressClient

PressClient().apply_patch(
    release_group="<bench group>",
    app="oneapp_control",
    patch=open("fix.patch").read(),
    build_assets=False,   # True only if the diff needs the asset bundler
)
```

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
