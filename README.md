# OneSpace

A Frappe application presenting one SPA over multiple bespoke solutions, with
ERPNext underneath. Customers never see Frappe or ERPNext — the SPA is their
only access point, and there is no desk for anybody.

Two documents cover it: [`docs/ONESPACE.md`](docs/ONESPACE.md) is the product a
customer uses; [`docs/ONEADMIN.md`](docs/ONEADMIN.md) is the platform behind it
— tenancy, billing, the lifecycle, configuration and how to work on this repo.

**OneApp is the repository name and is never product-facing.** The product is
OneSpace; the operator console is OneAdmin.

## Layout

```
apps/oneapp/           installed on every tenant site
apps/oneapp_control/   installed only on the control-plane site
docs/                  two documents, and two reference tables
scripts/               generators, and the local development loop
tests/                 ~1,580 tests, no bench required
.github/workflows/     the mirror pipeline
```

Frappe Cloud builds a bench group from `(repo URL, branch)` pairs and requires
the repository root to be the app root, so each app is published to a standalone
mirror by `.github/workflows/mirror-apps.yml`:

| Source | Mirror | Consumed by |
| --- | --- | --- |
| `apps/oneapp` | `yamenzak/oneapp-app` | tenant bench groups |
| `apps/oneapp_control` | `yamenzak/oneapp-control` | control-plane bench |

**All work happens here.** The mirrors are build artifacts — never commit to
them. Branch names are preserved, so pushing `canary` updates `canary` on both.

## Local development

Symlink both apps into a bench rather than cloning the mirrors, so an edit is
live with no sync step:

```bash
git clone https://github.com/yamenzak/OneApp ~/src/OneApp

cd ~/frappe-bench
ln -s ~/src/OneApp/apps/oneapp          apps/oneapp
ln -s ~/src/OneApp/apps/oneapp_control  apps/oneapp_control

./env/bin/pip install -e apps/oneapp -e apps/oneapp_control
echo -e "oneapp\noneapp_control" >> sites/apps.txt

bench --site tenant.localhost  install-app oneapp
bench --site control.localhost install-app oneapp_control
```

Then `scripts/dev.sh up` — the loop, and the four things that cost an hour each,
are in `docs/ONEADMIN.md`.

## Mirrors, first time only

1. Create the two mirror repositories, empty.
2. Create a fine-grained PAT with **Contents: Read and write**, scoped to those
   two repositories only, and add it as the repository secret `MIRROR_TOKEN`.
3. Push, or run the **Mirror apps** workflow by hand, to seed both.
4. Point the Frappe Cloud bench groups at them.

MIT.
