"""Client for the control plane, from a tenant site.

Identity comes from site_config.json, which the provisioning engine injected
when the site was created:

    oneapp_tenant       our tenant name
    oneapp_control_url  base URL of the control plane
    oneapp_hmac_secret  shared secret, scoped to this tenant alone

A site missing these is orphaned — running, but unable to prove who it is.
"""

import json

import frappe
import requests

TIMEOUT = 15

SIGNATURE_HEADER = "X-OneSpace-Signature"
TIMESTAMP_HEADER = "X-OneSpace-Timestamp"
TENANT_HEADER = "X-OneSpace-Tenant"


class ControlPlaneError(Exception):
	pass


class NotProvisioned(ControlPlaneError):
	"""Site config is missing its tenant identity."""


def config() -> dict:
	conf = frappe.conf
	return {
		"tenant": conf.get("oneapp_tenant"),
		"url": (conf.get("oneapp_control_url") or "").rstrip("/"),
		"secret": conf.get("oneapp_hmac_secret"),
	}


def is_provisioned() -> bool:
	c = config()
	return bool(c["tenant"] and c["url"] and c["secret"])


def _sign(secret: str, body: str) -> tuple[str, str]:
	import hashlib
	import hmac
	import time

	timestamp = str(int(time.time()))
	signature = hmac.new(
		secret.encode("utf-8"),
		f"{timestamp}.{body}".encode("utf-8"),
		hashlib.sha256,
	).hexdigest()
	return signature, timestamp


def call(method: str, payload: dict | None = None) -> dict:
	"""POST a signed request to a control-plane endpoint."""
	c = config()
	if not is_provisioned():
		raise NotProvisioned(
			"This site has no oneapp_tenant / oneapp_control_url / oneapp_hmac_secret "
			"in site_config.json."
		)

	# Must match the control plane's canonicalisation exactly, or the signature
	# will not verify.
	body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
	signature, timestamp = _sign(c["secret"], body)

	url = f"{c['url']}/api/method/oneapp_control.api.tenant.{method}"

	try:
		response = requests.post(
			url,
			data=body,
			headers={
				"Content-Type": "application/json",
				SIGNATURE_HEADER: signature,
				TIMESTAMP_HEADER: timestamp,
				TENANT_HEADER: c["tenant"],
			},
			timeout=TIMEOUT,
		)
	except requests.RequestException as e:
		raise ControlPlaneError(f"Control plane unreachable: {e}") from e

	if response.status_code != 200:
		raise ControlPlaneError(
			f"{method} failed ({response.status_code}): {response.text[:300]}"
		)

	return response.json().get("message") or {}


def sync() -> dict:
	return call("sync")


def report_usage(storage_used_bytes: int, user_count: int,
                 database_used_bytes: int = 0) -> dict:
	return call(
		"report_usage",
		{
			"storage_used_bytes": storage_used_bytes,
			"user_count": user_count,
			"database_used_bytes": database_used_bytes,
		},
	)


def reserve_credits(credits: float, purpose: str) -> dict:
	return call("reserve_credits", {"credits": credits, "purpose": purpose})


def commit_credits(reservation: str, credits: float, remarks: str | None = None) -> dict:
	return call(
		"commit_credits",
		{"reservation": reservation, "credits": credits, "remarks": remarks},
	)


def release_credits(reservation: str, reason: str = "released") -> dict:
	return call(
		"commit_credits", {"reservation": reservation, "release": True, "reason": reason}
	)
