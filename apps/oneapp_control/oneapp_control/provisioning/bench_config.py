"""Push shared configuration to bench groups.

Everything identical across tenants — R2 credentials, the Cloudflare email token,
AI keys — lives in the bench group's common site config, not on each site. Frappe
merges common site config into every site's `frappe.conf`, so one push reaches
every tenant on that bench.

Set the values once in OneApp Control Settings, push, and the tenant sites
reconcile whatever is derived from them on their next sync. Rotating a token is
one action, not one per tenant.
"""

import frappe
from frappe import _

from oneapp_control.press.client import get_client


def build_config() -> dict:
	"""The keys tenant sites read out of frappe.conf.

	Names here must match what `oneapp` looks up — see
	`oneapp.oneapp_core.storage.r2.config`, `.email.outbound.config` and
	`.ai.gateway.config`.
	"""
	s = frappe.get_single("OneApp Control Settings")

	config = {
		# R2
		"oneapp_r2_account_id": s.r2_account_id,
		"oneapp_r2_bucket": s.r2_bucket,
		"oneapp_r2_access_key": s.r2_access_key,
		"oneapp_r2_secret_key": s.get_password("r2_secret_key", raise_exception=False),
		"oneapp_r2_public_base": s.r2_public_base,
		# Email
		"oneapp_cf_email_token": s.get_password("cf_email_token", raise_exception=False),
		"oneapp_mail_domain": s.mail_domain,
		"oneapp_mail_hourly_limit": s.mail_hourly_limit,
		# AI
		"oneapp_cf_account_id": s.cf_account_id,
		"oneapp_ai_gateway": s.ai_gateway,
		"oneapp_ai_gateway_token": s.get_password("ai_gateway_token", raise_exception=False),
		"oneapp_google_ai_key": s.get_password("google_ai_key", raise_exception=False),
		"oneapp_cf_api_token": s.get_password("cf_api_token", raise_exception=False),
		"oneapp_ai_markup": s.ai_markup_multiplier,
		# Control plane
		"oneapp_control_url": s.control_plane_url,
	}

	# Never push a blank over a value that is already set on the bench.
	return {k: v for k, v in config.items() if v not in (None, "")}


@frappe.whitelist()
def push_to_shard(shard: str) -> dict:
	"""Push shared config to one shard's bench group."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	release_group = frappe.db.get_value("Shard", shard, "press_release_group")
	if not release_group:
		frappe.throw(_("Shard {0} has no bench group set.").format(shard))

	config = build_config()
	if not config:
		frappe.throw(_("Nothing to push — OneApp Control Settings is empty."))

	get_client().update_bench_config(release_group, config)

	return {
		"ok": True,
		"shard": shard,
		"release_group": release_group,
		"keys": sorted(config),
	}


@frappe.whitelist()
def push_to_all_shards() -> dict:
	"""Push to every shard. Used after rotating a shared credential."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	results, failures = [], []

	for shard in frappe.get_all(
		"Shard", filters={"press_release_group": ("is", "set")}, pluck="name"
	):
		try:
			results.append(push_to_shard(shard))
		except Exception as e:
			# One unreachable bench must not stop the rest from being updated.
			failures.append({"shard": shard, "error": str(e)[:200]})
			frappe.log_error(
				title=f"Bench config push failed for {shard}",
				message=frappe.get_traceback(),
			)

	return {"pushed": results, "failed": failures}
