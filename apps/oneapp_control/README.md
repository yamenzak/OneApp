# OneAdmin

The control plane: tenants, shards, plans, subscriptions, the credit ledger,
entitlements and Frappe Cloud provisioning. Installed **only** on the
control-plane site, never on a tenant site.

> **This repository is generated.** It is a read-only mirror of
> `apps/oneapp_control/` in
> [yamenzak/OneApp](https://github.com/yamenzak/OneApp), published so Frappe
> Cloud can consume it as a standalone Frappe app.
>
> **Do not commit here — the next sync overwrites it.** Work in the monorepo.

```bash
bench get-app https://github.com/yamenzak/oneapp-control
bench --site <control-site> install-app oneapp_control
```

`oneapp` is installed alongside it, for the shell and the Space runtime — the
operator console and the customer's account area are Spaces on this site.

MIT.
