# OneSpace Control

Control plane for OneSpace: tenants, shards, plans, subscriptions, credit ledger, app
entitlements and Frappe Cloud provisioning. Installed **only** on the control-plane site,
never on a tenant site.

> **This repository is generated.** It is a read-only mirror of `apps/oneapp_control/` in
> [yamenzak/OneSpace](https://github.com/yamenzak/OneSpace), published automatically so that
> Frappe Cloud can consume it as a standalone Frappe app.
>
> **Do not commit here — changes will be overwritten on the next sync.**
> Open pull requests against the monorepo instead.

## Installation

```bash
bench get-app https://github.com/yamenzak/oneapp-control
bench --site <control-site> install-app oneapp_control
```

## License

MIT
