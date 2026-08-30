"""HMAC signing for control-plane <-> tenant-site calls.

Both directions use the same scheme so there is one thing to reason about:

    signature = HMAC-SHA256(secret, f"{timestamp}.{body}")

The timestamp is signed rather than sent alongside, so a captured request cannot
be replayed outside the tolerance window.
"""

import hashlib
import hmac
import json
import time

import frappe
from frappe import _

SIGNATURE_HEADER = "X-OneSpace-Signature"
TIMESTAMP_HEADER = "X-OneSpace-Timestamp"
TENANT_HEADER = "X-OneSpace-Tenant"

# Generous enough for clock drift between hosts, short enough that a captured
# request is not useful for long.
TOLERANCE_SECONDS = 300


def _canonical(body) -> str:
	if isinstance(body, (dict, list)):
		# Sort keys so both ends serialise identically.
		return json.dumps(body, sort_keys=True, separators=(",", ":"))
	return body or ""


def sign(secret: str, body, timestamp: int | None = None) -> tuple[str, str]:
	"""Return (signature, timestamp) for a request body."""
	timestamp = timestamp or int(time.time())
	payload = f"{timestamp}.{_canonical(body)}"
	signature = hmac.new(
		secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
	).hexdigest()
	return signature, str(timestamp)


def verify(secret: str, body, signature: str, timestamp: str) -> bool:
	"""Constant-time signature check with a replay window."""
	if not (secret and signature and timestamp):
		return False

	try:
		ts = int(timestamp)
	except (TypeError, ValueError):
		return False

	if abs(time.time() - ts) > TOLERANCE_SECONDS:
		return False

	expected, _ts = sign(secret, body, ts)
	return hmac.compare_digest(expected, signature)


def headers_for(secret: str, body, tenant: str | None = None) -> dict:
	signature, timestamp = sign(secret, body)
	out = {
		SIGNATURE_HEADER: signature,
		TIMESTAMP_HEADER: timestamp,
		"Content-Type": "application/json",
	}
	if tenant:
		out[TENANT_HEADER] = tenant
	return out


def verify_request_or_throw(secret: str, body) -> None:
	req = frappe.request
	if not req:
		frappe.throw(_("Not an HTTP request."), frappe.PermissionError)

	if not verify(
		secret,
		body,
		req.headers.get(SIGNATURE_HEADER),
		req.headers.get(TIMESTAMP_HEADER),
	):
		frappe.throw(_("Invalid or expired signature."), frappe.PermissionError)
