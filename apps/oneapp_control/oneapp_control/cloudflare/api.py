"""One way to talk to Cloudflare, and one place the tokens are chosen.

Four things on the control plane speak to this API — DNS, KV, Workers and Email
Routing — and until now each carried its own request helper and its own idea of
which token to use. This is that, once.

**Two tokens, and the split is a security boundary rather than an oversight.**

`cf_admin_token` is account-wide: it creates the KV namespace, uploads the
worker, enables Email Routing and writes DNS. It can rewrite the routing map for
every tenant on the platform, so it lives here and is **never** pushed to a
bench — `tests/test_secret_boundaries.py` holds that line.

`cf_email_token` is narrow — Email Sending: Edit — and is exactly the one that
*is* pushed, because a tenant site authenticates to Cloudflare's SMTP with it.
A tenant can read its own `frappe.conf`, so anything pushed there is a
credential every tenant holds; that is bearable for sending and would not be
for the admin token.

The older narrow tokens (`cf_kv_token`, `cf_dns_token`) still win where they are
set, so an operator who has already scoped them keeps that. Where they are
blank, the admin token stands in — which is what makes "give it one token" true.
"""

import frappe

API_BASE = "https://api.cloudflare.com/client/v4"
TIMEOUT = 30


class CloudflareError(Exception):
	"""The API answered, and said no."""


class NotConfigured(CloudflareError):
	"""No token or no account — this part of the platform is simply not set up."""


def settings():
	return frappe.get_single("OneSpace Control Settings")


def _secret(s, field: str) -> str:
	return s.get_password(field, raise_exception=False) or ""


def token(purpose: str = "admin") -> str:
	"""The token to use for one kind of call.

	`purpose` is `kv`, `dns` or `admin`. A narrow token wins where the operator
	set one; otherwise the account-wide one does the work.
	"""
	s = settings()
	admin = _secret(s, "cf_admin_token")
	narrow = {"kv": "cf_kv_token", "dns": "cf_dns_token"}.get(purpose)
	return (_secret(s, narrow) if narrow else "") or admin


def account_id() -> str:
	s = settings()
	return s.cf_kv_account_id or s.cf_account_id or ""


def zone_id() -> str:
	return settings().cf_zone_id or ""


def call(method: str, path: str, purpose: str = "admin", **kwargs) -> dict:
	"""One Cloudflare call. Answers `result`, or raises with what it said.

	Cloudflare answers 200 with `"success": false` for a good many failures, so
	the status code alone is not the check — reading `success` is.
	"""
	import requests

	bearer = token(purpose)
	if not bearer:
		raise NotConfigured(
			"No Cloudflare token. Set the account token in OneSpace Control Settings."
		)

	try:
		response = requests.request(
			method,
			f"{API_BASE}/{path.lstrip('/')}",
			headers={"Authorization": f"Bearer {bearer}"},
			timeout=TIMEOUT,
			**kwargs,
		)
	except Exception as e:
		raise CloudflareError(f"Cloudflare unreachable: {e}") from e

	try:
		body = response.json()
	except ValueError:
		raise CloudflareError(
			f"Cloudflare {response.status_code}: {response.text[:300]}"
		) from None

	if response.status_code >= 400 or not body.get("success", False):
		raise CloudflareError(_said(response.status_code, body))

	return body.get("result") or {}


def _said(status: int, body: dict) -> str:
	"""What went wrong, in the words Cloudflare used.

	Their `errors` array is the useful part and the HTTP status usually is not:
	a 400 saying "record already exists" and a 400 saying "invalid token" are
	the same status and very different afternoons.
	"""
	said = "; ".join(
		f"{one.get('code', '')} {one.get('message', '')}".strip()
		for one in (body.get("errors") or [])
	)
	return f"Cloudflare {status}: {said or str(body)[:300]}"
