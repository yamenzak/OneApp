"""Outbound mail.

Cloudflare Email Service exposes SMTP, so Frappe sends directly through its own
Email Queue — batching, retries, unsubscribe handling and attachment assembly all
come for free, and none of it is worth reimplementing.

    smtps://smtp.mx.cloudflare.net:465
    username: api_token
    password: <API token with Email Sending: Edit>

What is *not* free, and stays ours regardless of transport, is per-tenant rate
limiting. On a shared sending identity one tenant importing a purchased list
degrades deliverability for every other tenant, so the limit protects the
platform rather than the tenant.
"""

import frappe
from frappe import _

SMTP_SERVER = "smtp.mx.cloudflare.net"
SMTP_PORT = 465
SMTP_USER = "api_token"

DEFAULT_HOURLY_LIMIT = 200

ACCOUNT_NAME = "OneApp Outgoing"


def config() -> dict:
	conf = frappe.conf
	return {
		"api_token": conf.get("oneapp_cf_email_token"),
		"tenant": conf.get("oneapp_tenant"),
		"from_domain": conf.get("oneapp_mail_domain") or "mail.4dl.app",
		"hourly_limit": int(conf.get("oneapp_mail_hourly_limit") or DEFAULT_HOURLY_LIMIT),
	}


def sender_address() -> str:
	"""One sending identity per tenant, on our verified domain.

	Replies go to the tenant's real address via Reply-To. Sending as the
	customer's own domain would need their DKIM, which is the bring-your-own-domain
	path, not this one.
	"""
	c = config()
	return f"t-{c['tenant']}@{c['from_domain']}"


# --------------------------------------------------------------------------- #
# Email Account setup
# --------------------------------------------------------------------------- #

def ensure_email_account():
	"""Create or update the outgoing Email Account for this tenant.

	Called at provisioning and safe to re-run — rotating the token is a re-run.
	"""
	c = config()
	if not c["api_token"]:
		return None

	values = {
		"email_account_name": ACCOUNT_NAME,
		"email_id": sender_address(),
		"smtp_server": SMTP_SERVER,
		"smtp_port": SMTP_PORT,
		"use_ssl_for_outgoing": 1,
		"use_tls": 0,
		"login_id_is_different": 1,
		"login_id": SMTP_USER,
		"password": c["api_token"],
		"enable_outgoing": 1,
		"enable_incoming": 0,
		"default_outgoing": 1,
		"always_use_account_email_id_as_sender": 1,
	}

	if frappe.db.exists("Email Account", ACCOUNT_NAME):
		account = frappe.get_doc("Email Account", ACCOUNT_NAME)
		account.update(values)
		account.save(ignore_permissions=True)
		return account.name

	account = frappe.get_doc({"doctype": "Email Account", **values})
	account.insert(ignore_permissions=True)
	return account.name


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #

class SendRateExceeded(frappe.ValidationError):
	pass


def _rate_key() -> str:
	return f"oneapp_mail_sent:{frappe.utils.now_datetime().strftime('%Y%m%d%H')}"


def sent_this_hour() -> int:
	return int(frappe.cache().get_value(_rate_key()) or 0)


def enforce_send_rate(doc, method=None):
	"""before_insert on Email Queue.

	Frappe queues one Email Queue document per send, so counting them is an
	accurate measure of what actually leaves the site.
	"""
	c = config()
	limit = c["hourly_limit"]
	if not limit:
		return

	recipients = len(doc.get("recipients") or []) or 1
	sent = sent_this_hour()

	if sent + recipients > limit:
		frappe.throw(
			_(
				"This workspace has reached its limit of {0} emails per hour. "
				"Queued messages will resume shortly."
			).format(limit),
			exc=SendRateExceeded,
		)

	# Expires just past the hour so the counter cannot outlive its window.
	frappe.cache().set_value(_rate_key(), sent + recipients, expires_in_sec=3700)


def usage() -> dict:
	c = config()
	return {
		"sent_this_hour": sent_this_hour(),
		"hourly_limit": c["hourly_limit"],
		"sender": sender_address(),
		"configured": bool(c["api_token"]),
	}
