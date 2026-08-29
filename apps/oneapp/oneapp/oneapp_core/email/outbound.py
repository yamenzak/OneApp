"""Outbound mail.

If Cloudflare exposes SMTP credentials, configure an ordinary Frappe Email
Account and none of this is needed — Frappe's Email Queue already handles
batching, retries and unsubscribe.

This shim exists for the binding-only case: it posts the rendered message to a
Worker that sends it, and the Worker reports delivery and bounce status back.

Per-tenant rate limiting lives here regardless of transport. On a shared sending
identity, one tenant importing a purchased list degrades deliverability for
every other tenant, so the limit protects the platform, not the tenant.
"""

import hashlib
import hmac
import json
import time

import frappe
from frappe import _
import requests

TIMEOUT = 20
DEFAULT_HOURLY_LIMIT = 200


def config() -> dict:
	conf = frappe.conf
	return {
		"worker_url": conf.get("oneapp_mail_worker_url"),
		"secret": conf.get("oneapp_hmac_secret"),
		"tenant": conf.get("oneapp_tenant"),
		"from_domain": conf.get("oneapp_mail_domain") or "mail.4dl.app",
		"hourly_limit": int(conf.get("oneapp_mail_hourly_limit") or DEFAULT_HOURLY_LIMIT),
	}


def uses_worker() -> bool:
	return bool(config()["worker_url"])


def sender_address() -> str:
	c = config()
	return f"t-{c['tenant']}@{c['from_domain']}"


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #

def _rate_key() -> str:
	return f"oneapp_mail_sent:{int(time.time() // 3600)}"


def check_rate_limit(count: int = 1):
	c = config()
	key = _rate_key()
	cache = frappe.cache()

	sent = int(cache.get_value(key) or 0)
	if sent + count > c["hourly_limit"]:
		frappe.throw(
			_("Hourly email limit of {0} reached. Try again shortly.").format(
				c["hourly_limit"]
			),
			exc=SendRateExceeded,
		)

	cache.set_value(key, sent + count, expires_in_sec=3700)


class SendRateExceeded(frappe.ValidationError):
	pass


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #

def send(to: list[str] | str, subject: str, html: str, text: str | None = None,
         reply_to: str | None = None) -> dict:
	"""Send one message through the Worker."""
	c = config()
	if not uses_worker():
		raise NotConfigured(
			"No mail worker configured. Use a Frappe Email Account for SMTP instead."
		)

	recipients = [to] if isinstance(to, str) else list(to)
	check_rate_limit(len(recipients))

	body = json.dumps(
		{
			"tenant": c["tenant"],
			"from": sender_address(),
			"to": recipients,
			"reply_to": reply_to,
			"subject": subject,
			"html": html,
			"text": text,
		},
		sort_keys=True,
		separators=(",", ":"),
	)

	timestamp = str(int(time.time()))
	signature = hmac.new(
		c["secret"].encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
	).hexdigest()

	try:
		response = requests.post(
			c["worker_url"],
			data=body,
			headers={
				"Content-Type": "application/json",
				"X-OneApp-Signature": signature,
				"X-OneApp-Timestamp": timestamp,
				"X-OneApp-Tenant": c["tenant"],
			},
			timeout=TIMEOUT,
		)
	except requests.RequestException as e:
		raise SendFailed(f"Mail worker unreachable: {e}") from e

	if response.status_code != 200:
		raise SendFailed(f"Mail worker {response.status_code}: {response.text[:300]}")

	return response.json()


class NotConfigured(Exception):
	pass


class SendFailed(Exception):
	pass


# --------------------------------------------------------------------------- #
# Delivery feedback
# --------------------------------------------------------------------------- #

@frappe.whitelist(allow_guest=True, methods=["POST"])
def delivery_status():
	"""Bounce and complaint callback from the Worker.

	A hard bounce disables the recipient in Frappe so we stop mailing an address
	that does not exist — repeatedly sending to dead addresses is exactly what
	damages a sending reputation.
	"""
	from oneapp.oneapp_core.email.inbound import _verify

	payload = _verify()

	event = payload.get("event")
	recipient = payload.get("recipient")

	if event in ("bounce", "complaint") and recipient:
		if frappe.db.exists("Email Group Member", {"email": recipient}):
			frappe.db.set_value(
				"Email Group Member", {"email": recipient}, "unsubscribed", 1
			)

		frappe.log_error(
			title=f"Email {event}: {recipient}",
			message=json.dumps(payload)[:2000],
		)

	return {"ok": True}
