"""Cloudflare KV — the tenant routing map the email worker reads.

The inbound worker looks up `TENANTS.get(<slug>)` to find which site a message
belongs to and which secret to sign the handoff with. A tenant missing from KV
has its mail rejected at SMTP time, so this has to be written as part of
provisioning rather than by hand.

KV rather than a lookup call back to the control plane is deliberate: a
control-plane outage should not bounce customer mail.

The token used here needs Workers KV Storage: Edit and is **never** pushed to
tenant bench config — a credential that can rewrite the routing map for every
tenant does not belong in config that every tenant site can read.
"""

import json

import frappe
import requests

API_BASE = "https://api.cloudflare.com/client/v4"
TIMEOUT = 20


class KVError(Exception):
	pass


class KVNotConfigured(KVError):
	"""No namespace or token set — email routing simply is not in use yet."""


def config() -> dict:
	s = frappe.get_single("OneApp Control Settings")
	return {
		"account_id": s.cf_kv_account_id or s.cf_account_id,
		"namespace": s.cf_kv_namespace_id,
		"token": s.get_password("cf_kv_token", raise_exception=False),
	}


def is_configured() -> bool:
	c = config()
	return all([c["account_id"], c["namespace"], c["token"]])


def _request(method: str, path: str, **kwargs):
	c = config()
	if not is_configured():
		raise KVNotConfigured("Cloudflare KV is not configured in OneApp Control Settings.")

	url = (
		f"{API_BASE}/accounts/{c['account_id']}"
		f"/storage/kv/namespaces/{c['namespace']}/{path.lstrip('/')}"
	)

	try:
		response = requests.request(
			method,
			url,
			headers={"Authorization": f"Bearer {c['token']}"},
			timeout=TIMEOUT,
			**kwargs,
		)
	except requests.RequestException as e:
		raise KVError(f"Cloudflare KV unreachable: {e}") from e

	if response.status_code >= 400:
		raise KVError(f"Cloudflare KV {response.status_code}: {response.text[:300]}")

	return response


def put_tenant(tenant: str) -> dict:
	"""Register or refresh a tenant's routing entry. Idempotent — PUT overwrites."""
	doc = frappe.get_doc("Tenant", tenant)

	# Always the permanent internal address, never the custom domain: the
	# customer owns that DNS and can break it, and mail must keep flowing.
	value = {
		"url": f"https://{doc.site_name}",
		"secret": doc.signing_secret(),
	}

	_request(
		"PUT",
		f"values/{doc.tenant_slug}",
		files={
			"value": (None, json.dumps(value)),
			"metadata": (None, json.dumps({"tenant": doc.name})),
		},
	)

	return {"ok": True, "tenant": doc.name, "key": doc.tenant_slug}


def delete_tenant(tenant_slug: str) -> dict:
	"""Remove a routing entry so an archived tenant stops accepting mail."""
	try:
		_request("DELETE", f"values/{tenant_slug}")
	except KVError as e:
		# A missing key is the state we wanted anyway.
		if "404" not in str(e):
			raise

	return {"ok": True, "key": tenant_slug}


@frappe.whitelist()
def resync_all() -> dict:
	"""Rebuild the whole map. For recovery after a namespace is recreated."""
	if "System Manager" not in frappe.get_roles():
		frappe.throw(frappe._("Not permitted."), frappe.PermissionError)

	done, failed = [], []
	for tenant in frappe.get_all(
		"Tenant", filters={"status": ("in", ("Active", "Provisioning", "Suspended"))}, pluck="name"
	):
		try:
			put_tenant(tenant)
			done.append(tenant)
		except KVError as e:
			failed.append({"tenant": tenant, "error": str(e)[:200]})

	return {"synced": done, "failed": failed}
