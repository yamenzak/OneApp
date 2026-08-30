"""Cloudflare DNS — one CNAME per tenant, in Per-tenant domain mode.

Records are created **DNS-only** (`proxied: false`), deliberately. Frappe Cloud
validates a custom domain by resolving the CNAME and then answers an ACME
challenge on the origin. Proxying through Cloudflare makes the name resolve to
Cloudflare's IPs instead, and both the validation and the certificate fail. It is
the single most common way this flow breaks.

Not needed at all in Wildcard mode, where one record covers every tenant.
"""

import frappe
from frappe import _
import requests

API_BASE = "https://api.cloudflare.com/client/v4"
TIMEOUT = 20


class DNSError(Exception):
	pass


class DNSNotConfigured(DNSError):
	pass


def config() -> dict:
	s = frappe.get_single("OneSpace Control Settings")
	return {
		"zone": s.cf_zone_id,
		"token": s.get_password("cf_dns_token", raise_exception=False),
	}


def is_configured() -> bool:
	c = config()
	return bool(c["zone"] and c["token"])


def _request(method: str, path: str, **kwargs):
	c = config()
	if not is_configured():
		raise DNSNotConfigured("Cloudflare DNS is not configured in OneSpace Control Settings.")

	try:
		response = requests.request(
			method,
			f"{API_BASE}/zones/{c['zone']}/{path.lstrip('/')}",
			headers={"Authorization": f"Bearer {c['token']}"},
			timeout=TIMEOUT,
			**kwargs,
		)
	except requests.RequestException as e:
		raise DNSError(f"Cloudflare DNS unreachable: {e}") from e

	body = {}
	try:
		body = response.json()
	except ValueError:
		pass

	if response.status_code >= 400 or not body.get("success", True):
		errors = body.get("errors") or response.text[:300]
		raise DNSError(f"Cloudflare DNS {response.status_code}: {errors}")

	return body


def find_record(name: str) -> dict | None:
	result = _request("GET", "dns_records", params={"name": name, "type": "CNAME"})
	records = result.get("result") or []
	return records[0] if records else None


def upsert_cname(name: str, target: str) -> dict:
	"""Point a tenant hostname at its Frappe Cloud site. Idempotent."""
	payload = {
		"type": "CNAME",
		"name": name,
		"content": target,
		"ttl": 60,
		# Never proxied — see the module docstring.
		"proxied": False,
		"comment": "OneSpace tenant (managed)",
	}

	existing = find_record(name)
	if existing:
		if existing.get("content") == target and not existing.get("proxied"):
			return {"ok": True, "record": existing["id"], "changed": False}
		result = _request("PUT", f"dns_records/{existing['id']}", json=payload)
	else:
		result = _request("POST", "dns_records", json=payload)

	return {"ok": True, "record": (result.get("result") or {}).get("id"), "changed": True}


def delete_cname(name: str) -> dict:
	existing = find_record(name)
	if not existing:
		return {"ok": True, "deleted": False}

	_request("DELETE", f"dns_records/{existing['id']}")
	return {"ok": True, "deleted": True}
