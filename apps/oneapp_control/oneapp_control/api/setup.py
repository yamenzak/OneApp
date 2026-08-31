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
	return frappe.get_single("OneSpace Control Settings")


def _secret(settings, field) -> bool:
	return bool(settings.get_password(field, raise_exception=False))


def _press_configured(s) -> bool:
	conf = frappe.conf or {}
	key = s.press_api_key or conf.get("press_api_key")
	secret = _secret(s, "press_api_secret") or conf.get("press_api_secret")
	return bool(key and secret)


def _press_host_ok(s) -> bool:
	"""The API host must be the one that keeps the credential.

	frappecloud.com 308-redirects to cloud.frappe.io, and the redirect drops the
	Authorization header — so a control plane configured with it has working
	credentials and no working call, and press blames the key rather than the
	host. Checked separately from the credentials so the answer names the actual
	problem.
	"""
	from oneapp_control.control_plane.doctype.onespace_control_settings.onespace_control_settings import (
		REDIRECTING_PRESS_HOSTS,
	)

	url = (s.press_api_url or (frappe.conf or {}).get("press_api_url") or "").strip()
	if not url:
		return False
	host = url.split("://", 1)[-1].split("/", 1)[0].lower()
	return host not in REDIRECTING_PRESS_HOSTS


def _outgoing_email_ok() -> bool:
	"""Whether this site has somewhere to send mail from.

	Frappe queues a mail with no outgoing account without complaining, so this
	cannot be inferred from a successful send.
	"""
	return bool(
		frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1})
	)


def _r2_client_ok() -> bool:
	from oneapp_control.cloudflare import r2

	return r2.has_client()


def _plans_hint() -> str:
	"""Say which of the two ways this can be unset actually applies."""
	if not frappe.get_all("Plan", filters={"is_active": 1}, limit=1):
		return "One active plan. Saving it creates its Stripe product and prices."

	failed = frappe.get_all(
		"Plan",
		filters={"is_active": 1, "sync_error": ("is", "set")},
		fields=["plan_name", "sync_error"],
		limit=1,
	)
	if failed:
		return "{0} failed to sync: {1}".format(
			failed[0].plan_name, (failed[0].sync_error or "").split("\n")[0][:160]
		)

	return "A monthly price above zero on an active plan, then save it to mint the Stripe price."


def checks() -> list[dict]:
	s = _settings()

	shards = frappe.get_all(
		"Shard",
		filters={"status": "Active", "accepts_new_tenants": 1},
		fields=["name", "domain_mode", "press_release_group", "press_version"],
	)
	per_tenant = [x for x in shards if x.domain_mode == "Per-tenant"]

	# Three sentences at most per check, and each says a different thing:
	# `detail` is what breaks without it, `needs` is exactly what to supply, and
	# `where` is where to put it. The page reads as a checklist that way rather
	# than as documentation someone has to skim to find the one fact they came
	# for — which is what it was.
	result = [
		{
			"key": "press_credentials",
			"group": BLOCKING,
			"label": "Frappe Cloud API",
			# Site config counts, matching PressClient. Reading only the
			# settings here would report "Missing" on a site that provisions
			# perfectly well, which is worse than either answer alone.
			"ok": _press_configured(s),
			"detail": "Nothing provisions without it.",
			"needs": "An API key and secret for a Frappe Cloud user on the team that owns the benches.",
			"where": "Settings → Frappe Cloud, or site config",
		},
		{
			"key": "press_host",
			"group": BLOCKING,
			"label": "Frappe Cloud API host",
			"ok": _press_host_ok(s),
			"detail": "frappecloud.com redirects, and the redirect drops the credential — every call then fails as though the key were wrong.",
			"needs": "https://cloud.frappe.io",
			"where": "Settings → Frappe Cloud → API host",
		},
		{
			"key": "control_plane_url",
			"group": BLOCKING,
			"label": "Control plane URL",
			"ok": bool(s.control_plane_url),
			"detail": "Tenants call back on it. Provisioned without one, a tenant is orphaned: no entitlements, no credits.",
			"needs": "This site's public URL, including https://.",
			"where": "Settings → Frappe Cloud",
		},
		{
			"key": "shard",
			"group": BLOCKING,
			"label": "A shard with headroom",
			"ok": bool(shards),
			"detail": "Tenants are placed on a shard. With none accepting, provisioning refuses rather than putting a tenant nowhere.",
			"needs": "One Shard, Active, with 'accepts new tenants' on.",
			"where": "Shards",
		},
		{
			"key": "shard_version",
			"group": BLOCKING,
			"label": "Shards declare a bench version",
			"ok": all(x.press_version for x in shards) if shards else False,
			"detail": "Frappe Cloud matches a bench by server, version and apps. Without the version it falls back to its public path and fails naming the wrong cause.",
			"needs": "A Frappe version on every shard, e.g. version-15.",
			"where": "Shards → Bench version",
		},
		{
			"key": "cloudflare_dns",
			"group": BLOCKING if per_tenant else OPTIONAL,
			"label": "Cloudflare DNS",
			"ok": bool(s.cf_zone_id) and _secret(s, "cf_dns_token"),
			"detail": (
				"Per-tenant domain mode creates one CNAME per tenant. "
				+ (
					"Required: {0} shard(s) use it.".format(len(per_tenant))
					if per_tenant
					else "Not needed while every shard is on Wildcard mode."
				)
			),
			"needs": "The zone ID, and an API token with Zone → DNS → Edit scoped to that zone.",
			"where": "Settings → Cloudflare",
		},
		{
			"key": "plans",
			"group": BILLING,
			"label": "Plans are synced to Stripe",
			"ok": bool(
				frappe.get_all(
					"Plan",
					filters={"is_active": 1, "stripe_price_id_monthly": ("is", "set")},
				)
			),
			"detail": "Checkout cannot start without a price to charge.",
			# Prices are minted by saving the plan, not pasted in, so the fix is
			# always the same gesture: fix the key, save the plan again.
			"needs": _plans_hint(),
			"where": "Settings → Plans",
		},
		{
			"key": "stripe_gateway",
			"group": BILLING,
			"label": "Stripe secret key",
			"ok": bool(frappe.db.exists("Stripe Settings", {})),
			"detail": "Held by the payments app, so there is one place to rotate it.",
			"needs": "A Stripe secret key (sk_live_… or sk_test_…).",
			"where": "Stripe Settings (payments app)",
		},
		{
			"key": "stripe_webhook",
			"group": BILLING,
			"label": "Stripe webhook secret",
			"ok": _secret(s, "stripe_webhook_secret"),
			"detail": "Without it the endpoint rejects everything, so payments never grant credits or start subscriptions.",
			"needs": (
				"The signing secret (whsec_…) of a Stripe webhook pointed at "
				"/api/method/oneapp_control.billing.webhooks.stripe."
			),
			"where": "Settings → Billing",
		},
		{
			"key": "r2",
			"group": OPTIONAL,
			"label": "R2 storage",
			"ok": bool(s.r2_account_id and s.r2_bucket and s.r2_access_key)
			and _secret(s, "r2_secret_key"),
			"detail": "Tenant sites fall back to local disk until this is set.",
			"needs": "A Cloudflare account ID, a bucket, and an R2 API token's access key and secret.",
			"where": "Settings → Storage buckets",
		},
		{
			# The control plane's *own* ability to send, which is a different
			# thing from the Cloudflare token below — that one is what tenant
			# sites send with. Blocking, and it is the check this list was
			# missing for longest: without it a workspace is suspended,
			# archived and eventually deleted while every notification is
			# swallowed, and the first anybody hears is a customer asking
			# where their business went.
			"key": "control_email",
			"group": BLOCKING,
			"label": "This site can send email",
			"ok": _outgoing_email_ok(),
			"detail": (
				"Signup links and every lifecycle warning are sent from here. "
				"Nothing is suspended, archived or deleted without one, and "
				"the lifecycle refuses to purge a workspace it could not warn."
			),
			"needs": "An Email Account on this site with Default Outgoing set.",
			"where": "Email Account",
		},
		{
			"key": "r2_client",
			"group": OPTIONAL,
			"label": "R2 client library",
			"ok": _r2_client_ok(),
			"detail": (
				"boto3 is not installed on this bench, so nothing can read or "
				"write an object: no attachments, no backups, no cold copies "
				"and no purge. Frappe no longer depends on it, so it comes "
				"from these apps' own requirements."
			),
			"needs": "Redeploy the bench after `boto3` was added to the apps.",
			"where": "Frappe Cloud → bench",
		},
		{
			"key": "email_outbound",
			"group": OPTIONAL,
			"label": "Outbound email",
			"ok": _secret(s, "cf_email_token") and bool(s.mail_domain),
			"detail": "Tenants cannot send mail without it.",
			"needs": (
				"A verified sending domain, and a Cloudflare API token with "
				"Email Sending → Edit — it is the SMTP password."
			),
			"where": "Settings → Cloudflare",
		},
		{
			"key": "email_inbound",
			"group": OPTIONAL,
			"label": "Inbound email routing",
			"ok": bool(s.cf_kv_namespace_id) and _secret(s, "cf_kv_token"),
			"detail": "Tenants provisioned before this exists are missing from the routing map; cloudflare.kv.resync_all backfills them.",
			"needs": "A Workers KV namespace ID, and a token with Account → Workers KV Storage → Edit.",
			"where": "Settings → Cloudflare",
		},
		{
			"key": "ai",
			"group": OPTIONAL,
			"label": "AI gateway",
			"ok": bool(s.cf_account_id and s.ai_gateway) and _secret(s, "google_ai_key"),
			"detail": "AI features return an error to tenants until this is configured.",
			"needs": "A Cloudflare account ID, an AI Gateway name, and a Google AI API key.",
			"where": "Settings → Cloudflare",
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
