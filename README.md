# OneApp

A single Frappe application presenting a unified SPA over multiple bespoke solutions, with
ERPNext underneath. Customers never see Frappe or ERPNext — the SPA is their only access point.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the decisions this is built on,
and [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased build plan.

## Layout

This is a monorepo containing two Frappe apps.

```
apps/
├── oneapp/            # installed on every tenant site
└── oneapp_control/    # installed only on the control-plane site
docs/
.github/workflows/     # mirror pipeline
```

Frappe Cloud builds a bench group from `(repo URL, branch)` pairs and requires the repository
root to be the app root, so each app is published to a standalone mirror repository by
`.github/workflows/mirror-apps.yml`:

| Source | Mirror | Consumed by |
| --- | --- | --- |
| `apps/oneapp` | `yamenzak/oneapp-app` | tenant bench groups |
| `apps/oneapp_control` | `yamenzak/oneapp-control` | control-plane bench |

**All work happens here.** The mirrors are generated build artifacts — never commit to them.
Branch names are preserved, so pushing `canary` here updates `canary` on both mirrors and a
canary bench group can track it.

## Local development

Symlink both apps into a bench rather than cloning the mirrors:

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

Editing the monorepo then updates the bench directly, with no sync step.

## First-time setup

1. Create the two mirror repositories, empty.
2. Create a fine-grained PAT with **Contents: Read and write**, scoped to those two
   repositories only.
3. Add it here as the repository secret `MIRROR_TOKEN`.
4. Push, or run the **Mirror apps** workflow manually, to seed both mirrors.
5. Point the Frappe Cloud bench groups at the mirrors.

## License

MIT
