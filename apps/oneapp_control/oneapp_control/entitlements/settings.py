"""The control plane's own settings, in OneSpace's settings dialog.

`/admin` had its own settings shell over the same Single. That is a second
dialog to keep in step with the first, and everything the first one gained —
the mobile tab strip, the fixed header and footer, the geometry — the second
one did not.

So the groups are declared here in the shape `oneapp` already uses and handed
over through `onespace_settings_groups`. Nothing downstream can tell them apart
from the workspace's own; what differs is `roles`, which is what keeps a
customer's account dialog and an operator's out of each other.

Read by `oneapp.oneapp_core.workspace.all_groups`, so this file is the whole of
what an operator can change here.
"""

import frappe

SETTINGS = "OneSpace Control Settings"

# Only a System Manager. A workspace admin owning branding and sign-in has no
# business in the Frappe Cloud credentials — and on this site a customer holds
# `OneSpace Customer`, which is not this.
OPERATOR_ROLES = ("System Manager",)


def _setting(key, label, **kw):
	"""One field on the Single, in `oneapp`'s own Setting shape.

	Imported lazily: this module is read through a hook, and importing the
	tenant app at module scope would make the control plane refuse to load
	wherever `oneapp` is not installed.
	"""
	from oneapp.oneapp_core.workspace import Setting

	return Setting(key, label, targets=[(SETTINGS, key)], **kw)


def groups() -> list[dict]:
	"""Three groups, matching the three panels `/admin` had.

	Grouped by what somebody is doing rather than by which service the value
	belongs to — "I am setting up provisioning" reaches for the shard and the
	press credentials together, and never for the Stripe secret.
	"""
	return [
		{
			"key": "control-cloud",
			"label": "Frappe Cloud",
			"icon": "lucide-cloud",
			"roles": OPERATOR_ROLES,
			"description": (
				"Where tenant sites are created, and what they are called. "
				"Provisioning is refused until these are set."
			),
			"settings": [
				_setting("press_api_url", "Press API URL",
				         hint="https://cloud.frappe.io unless you are on a private Press."),
				_setting("press_api_key", "Press API key"),
				_setting("press_api_secret", "Press API secret", type="Password"),
				_setting("default_shard", "Default shard",
				         hint="Where a new tenant lands when its plan names none."),
				_setting("tenant_domain", "Tenant domain",
				         hint="The suffix every workspace address ends in."),
				_setting("control_plane_url", "Control plane URL",
				         hint="How a tenant site reaches this one. Signed into every payload."),
				_setting("reserved_slugs", "Reserved names", type="Small Text",
				         hint="One per line. Names a customer may not take."),
			],
		},
		{
			"key": "control-billing",
			"label": "Billing",
			"icon": "lucide-credit-card",
			"roles": OPERATOR_ROLES,
			"description": (
				"Stripe, and what a credit is worth. Tenants can be created "
				"without these; nobody can pay you."
			),
			"settings": [
				_setting("stripe_webhook_secret", "Stripe webhook secret", type="Password"),
				_setting("credits_per_currency_unit", "Credits per unit of currency",
				         type="Float",
				         hint="How many AI credits one unit of the plan's currency buys."),
				_setting("ai_markup_multiplier", "AI markup", type="Float",
				         hint="What a model's own cost is multiplied by before it is charged."),
			],
		},
		{
			"key": "control-cloudflare",
			"label": "Cloudflare",
			"icon": "lucide-globe",
			"roles": OPERATOR_ROLES,
			"description": (
				"DNS, storage, email and the AI gateway. Each is a capability "
				"tenants gain; sites work without them."
			),
			"settings": [
				_setting("cf_zone_id", "DNS zone ID"),
				_setting("cf_dns_token", "DNS API token", type="Password"),
				_setting("cf_kv_account_id", "Account ID"),
				_setting("cf_kv_namespace_id", "KV namespace ID"),
				_setting("cf_kv_token", "KV API token", type="Password"),
				_setting("r2_account_id", "R2 account ID"),
				_setting("r2_bucket", "R2 bucket"),
				_setting("r2_public_base", "R2 public base URL"),
				_setting("r2_access_key", "R2 access key"),
				_setting("r2_secret_key", "R2 secret key", type="Password"),
				_setting("r2_admin_token", "R2 admin API token", type="Password"),
				_setting("bucket_max_tenants", "Tenants per bucket", type="Int"),
				_setting("mail_domain", "Mail domain"),
				_setting("cf_email_token", "Email token", type="Password"),
				_setting("mail_hourly_limit", "Emails per hour", type="Int"),
				_setting("cf_account_id", "AI gateway account ID"),
				_setting("ai_gateway", "AI gateway name"),
				_setting("ai_gateway_token", "AI gateway token", type="Password"),
				_setting("cf_api_token", "Cloudflare API token", type="Password"),
				_setting("google_ai_key", "Google AI Studio key", type="Password"),
			],
		},
		{
			"key": "control-lifecycle",
			"label": "Lifecycle",
			"icon": "lucide-clock",
			"roles": OPERATOR_ROLES,
			"description": (
				"How long a workspace that stops being paid for keeps working, "
				"keeps its site, and keeps its data. Every window is in days, "
				"and each is measured from the one before it."
			),
			"settings": [
				_setting("dunning_grace_days", "Grace period", type="Int",
				         hint="Days from the first failed payment to the site "
				              "being switched off. It works throughout."),
				_setting("suspended_days", "Suspended for", type="Int",
				         hint="Days from being switched off to the site being "
				              "removed from Frappe Cloud. Nothing is deleted."),
				_setting("cold_retention_days", "Cold copy kept for", type="Int",
				         hint="Days we hold the copy after the site is removed. "
				              "Never fewer than seven, whatever is typed here."),
				_setting("purge_warning_days", "Warn before deleting", type="Int",
				         hint="Days of notice before the copy is destroyed. "
				              "Deleting refuses on a workspace that was not warned."),
				_setting("overage_grace_days", "Over-quota grace", type="Int",
				         hint="Days a workspace may sit over its limit before "
				              "uploads stop. Usually because a line left their "
				              "subscription rather than anything they did."),
				_setting("auto_purge_enabled", "Delete automatically", type="Check",
				         hint="Whether the sweep may destroy a cold copy once "
				              "every window and warning has passed. Off means "
				              "everything is kept forever, which is a bill "
				              "rather than a policy."),
			],
		},
	]
