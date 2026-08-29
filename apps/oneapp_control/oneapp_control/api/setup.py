"""Setup readiness.

The control plane is useless until it is configured, and the failure modes of a
half-configured one are indirect: provisioning jobs that fail on their third
step, tenants that come up unable to reach us, mail that silently never routes.

So the admin UI asks this first and refuses to let you provision until the
blocking checks pass. Each check says what is missing and where to set it,
because "not configured" without that is just a dead end.
"""

import frappe
from frappe import _

BLOCKING = "blocking"
BILLING = "billing"
OPTIONAL = "optional"


def _settings():
	return frappe.get_single("OneApp Control Settings")


def _secret(settings, field) -> bool:
	return bool(settings.get_password(field, raise_exception=False))


def checks() -> list[dict]:
	s = _settings()

	shards = frappe.get_all(
		"Shard",
		filters={"status": "Active", "accepts_new_tenants": 1},
		fields=["name", "domain_mode", "press_release_group", "press_version"],
	)
	per_tenant = [x for x in shards if x.domain_mode == "Per-tenant"]

	result = [
		{
			"key": "press_credentials",
			"group": BLOCKING,
			"label": "Frappe Cloud API",
			"ok": bool(s.press_api_key) and _secret(s, "press_api_secret"),
			"detail": "Creates and manages tenant sites. Nothing can be provisioned without it.",
			"where": "OneApp Control Settings → Frappe Cloud",
		},
		{
			"key": "control_plane_url",
			"group": BLOCKING,
			"label": "Control plane URL",
			"ok": bool(s.control_plane_url),
			"detail": (
				"Injected into every tenant site so it can call back. A tenant "
				"provisioned without it is orphaned — it cannot sync entitlements "
				"or spend credits."
			),
			"where": "OneApp Control Settings → Frappe Cloud",
		},
		{
			"key": "shard",
			"group": BLOCKING,
			"label": "At least one shard with headroom",
			"ok": bool(shards),
			"detail": (
				"Tenants are placed on a shard. With none accepting, provisioning "
				"refuses rather than putting a tenant nowhere."
			),
			"where": "Shard list",
		},
		{
			"key": "shard_version",
			"group": BLOCKING,
			"label": "Shards declare a bench version",
			"ok": all(x.press_version for x in shards) if shards else False,
			"detail": (
				"Frappe Cloud matches the bench by (server, version, apps). Without "
				"a version it silently falls back to its public path and fails with "
				"an error naming the wrong cause."
			),
			"where": "Shard → press_version",
		},
		{
			"key": "cloudflare_dns",
			"group": BLOCKING if per_tenant else OPTIONAL,
			"label": "Cloudflare DNS",
			"ok": bool(s.cf_zone_id) and _secret(s, "cf_dns_token"),
			"detail": (
				"Per-tenant domain mode creates a CNAME per tenant. "
				+ ("Required: {0} shard(s) use it.".format(len(per_tenant))
				   if per_tenant else "Not needed while every shard is on Wildcard mode.")
			),
			"where": "OneApp Control Settings → Cloudflare DNS",
		},
		{
			"key": "plans",
			"group": BILLING,
			"label": "Plans have Stripe prices",
			"ok": bool(frappe.get_all("Plan", filters={"is_active": 1,
			                                           "stripe_price_id_monthly": ("is", "set")})),
			"detail": "Checkout cannot start without a Stripe Price ID on the plan.",
			"where": "Plan list",
		},
		{
			"key": "stripe_gateway",
			"group": BILLING,
			"label": "Stripe secret key",
			"ok": bool(frappe.db.exists("Stripe Settings", {})),
			"detail": "Configured in the payments app, so there is one place to rotate it.",
			"where": "Stripe Settings (payments app)",
		},
		{
			"key": "stripe_webhook",
			"group": BILLING,
			"label": "Stripe webhook secret",
			"ok": _secret(s, "stripe_webhook_secret"),
			"detail": (
				"Without it the webhook endpoint rejects everything, so payments "
				"never grant credits or activate subscriptions."
			),
			"where": "OneApp Control Settings → Stripe",
		},
		{
			"key": "r2",
			"group": OPTIONAL,
			"label": "R2 storage",
			"ok": bool(s.r2_account_id and s.r2_bucket and s.r2_access_key)
			      and _secret(s, "r2_secret_key"),
			"detail": "Tenant sites fall back to local disk until this is set.",
			"where": "OneApp Control Settings → Tenant bench config",
		},
		{
			"key": "email_outbound",
			"group": OPTIONAL,
			"label": "Outbound email",
			"ok": _secret(s, "cf_email_token") and bool(s.mail_domain),
			"detail": "Cloudflare Email Service over SMTP. Tenants cannot send mail without it.",
			"where": "OneApp Control Settings → Tenant bench config",
		},
		{
			"key": "email_inbound",
			"group": OPTIONAL,
			"label": "Inbound email routing",
			"ok": bool(s.cf_kv_namespace_id) and _secret(s, "cf_kv_token"),
			"detail": (
				"Tenants provisioned before this exists are missing from the routing "
				"map; cloudflare.kv.resync_all backfills them."
			),
			"where": "OneApp Control Settings → Cloudflare KV",
		},
		{
			"key": "ai",
			"group": OPTIONAL,
			"label": "AI gateway",
			"ok": bool(s.cf_account_id and s.ai_gateway) and _secret(s, "google_ai_key"),
			"detail": "AI features return an error to tenants until this is configured.",
			"where": "OneApp Control Settings → Tenant bench config",
		},
	]

	return result


@frappe.whitelist()
def readiness() -> dict:
	"""What is configured, what is missing, and whether provisioning may start."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	items = checks()
	blocking = [c for c in items if c["group"] == BLOCKING]

	return {
		"can_provision": all(c["ok"] for c in blocking),
		"can_bill": all(c["ok"] for c in items if c["group"] == BILLING),
		"checks": items,
		"summary": {
			"blocking": {"done": sum(c["ok"] for c in blocking), "total": len(blocking)},
			"billing": {
				"done": sum(c["ok"] for c in items if c["group"] == BILLING),
				"total": len([c for c in items if c["group"] == BILLING]),
			},
			"optional": {
				"done": sum(c["ok"] for c in items if c["group"] == OPTIONAL),
				"total": len([c for c in items if c["group"] == OPTIONAL]),
			},
		},
	}


def assert_ready_to_provision():
	"""Raise unless the blocking checks pass.

	Enforced server-side as well as in the UI: a half-configured provision fails
	partway through, having already created a real site on Frappe Cloud.
	"""
	failed = [c for c in checks() if c["group"] == BLOCKING and not c["ok"]]
	if failed:
		frappe.throw(
			_("Setup is incomplete: {0}").format(
				", ".join(c["label"] for c in failed)
			)
		)
