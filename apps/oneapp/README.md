# OneSpace

The application surface tenants see. Installed on every tenant site.

> **This repository is generated.** It is a read-only mirror of `apps/oneapp/`
> in [yamenzak/OneApp](https://github.com/yamenzak/OneApp), published so Frappe
> Cloud can consume it as a standalone Frappe app.
>
> **Do not commit here — the next sync overwrites it.** Work in the monorepo.

```bash
bench get-app https://github.com/yamenzak/oneapp-app
bench --site <site> install-app oneapp
```

ERPNext is not required. Every erpnext import is deferred and gated, so a site
without it runs and the workspace's Books panel says there is no accounting app.
Tenant benches carry it regardless.

MIT.
