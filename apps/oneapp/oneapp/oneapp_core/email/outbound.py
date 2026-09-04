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

# A day's ceiling as well as an hour's, because they stop different things. The
# hourly one stops a burst — a loop, a bad import, a webhook storm. The daily one
# stops the slow version of the same thing, which an hourly limit alone happily
# permits: two hundred an hour is four thousand eight hundred a day, and a
# workspace grinding steadily through a bought list stays under every hourly
# limit ever set.
DEFAULT_DAILY_LIMIT = 2000

ACCOUNT_NAME = "OneSpace Outgoing"


def config() -> dict:
	conf = frappe.conf
	return {
		"api_token": conf.get("oneapp_cf_email_token"),
		"tenant": conf.get("oneapp_tenant"),
		"from_domain": conf.get("oneapp_mail_domain") or "mail.4dl.app",
		"hourly_limit": int(conf.get("oneapp_mail_hourly_limit") or DEFAULT_HOURLY_LIMIT),
		"daily_limit": int(conf.get("oneapp_mail_daily_limit") or DEFAULT_DAILY_LIMIT),
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

def transport() -> dict:
	"""The SMTP half of an Email Account, shared by every address we send for.

	One definition, used twice: by the platform's own account below and by every
	address a workspace mints (`addresses.create`). The alternative — an address
	with `enable_outgoing` and no server — is an account Frappe will happily
	accept, put in the picker, and fail on at the first send, with an error
	about a connection rather than about the address being half-made.

	The token is the same one for every address because the *domain* is what
	Cloudflare authorises, not the local part. An address on a customer's own
	domain is the same transport again and differs only in having had its DNS
	checked first — see `verify.py`.
	"""
	c = config()
	return {
		"smtp_server": SMTP_SERVER,
		"smtp_port": SMTP_PORT,
		"use_ssl_for_outgoing": 1,
		"use_tls": 0,
		"login_id_is_different": 1,
		"login_id": SMTP_USER,
		"password": c["api_token"],
	}


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
		**transport(),
		"enable_outgoing": 1,
		"enable_incoming": 0,
		"default_outgoing": 1,
		"always_use_account_email_id_as_sender": 1,
	}

	if not frappe.db.exists("Email Account", ACCOUNT_NAME):
		account = frappe.get_doc({"doctype": "Email Account", **values})
		account.insert(ignore_permissions=True)
		return account.name

	account = frappe.get_doc("Email Account", ACCOUNT_NAME)

	# Runs on every sync, so only write when something actually differs —
	# otherwise every site churns its modified timestamp every 15 minutes.
	changed = any(
		account.get(field) != value
		for field, value in values.items()
		if field != "password"
	)
	if account.get_password("password", raise_exception=False) != c["api_token"]:
		changed = True

	if changed:
		account.update(values)
		account.save(ignore_permissions=True)

	_reconcile_workspace_accounts(c["api_token"])
	return account.name


def _reconcile_workspace_accounts(token: str) -> int:
	"""Push a rotated token onto every address the workspace has minted.

	Without this a rotation fixes the platform's own sending and silently breaks
	everybody's: the addresses carry their own copy of the credential, because
	that is how Frappe's Email Account works, and a copy is a thing that goes
	stale. Runs on every sync and writes only where the token differs.
	"""
	if not token:
		return 0

	touched = 0
	for name in frappe.get_all(
		"Email Account",
		filters={"name": ("!=", ACCOUNT_NAME), "smtp_server": SMTP_SERVER},
		pluck="name",
	):
		account = frappe.get_doc("Email Account", name)
		if account.get_password("password", raise_exception=False) == token:
			continue
		account.password = token
		account.save(ignore_permissions=True)
		touched += 1
	return touched


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #

class SendRateExceeded(frappe.ValidationError):
	pass


def _rate_key(window: str = "hour") -> str:
	stamp = frappe.utils.now_datetime().strftime("%Y%m%d%H" if window == "hour" else "%Y%m%d")
	return f"oneapp_mail_sent:{window}:{stamp}"


def sent_this_hour() -> int:
	return int(frappe.cache().get_value(_rate_key("hour")) or 0)


def sent_today() -> int:
	return int(frappe.cache().get_value(_rate_key("day")) or 0)


class SendingSuspended(frappe.ValidationError):
	pass


def _suspended() -> bool:
	"""Whether this workspace may send at all.

	A suspended workspace stops sending *first* and keeps working otherwise,
	which is the opposite order to how it reads: sending is the thing that
	spends the platform's reputation and the thing a suspended customer cannot
	be trusted with, while their own records are theirs and locking them out of
	those is a separate decision with a separate ladder — see
	`docs/ONEADMIN.md`, The lifecycle.
	"""
	from oneapp.oneapp_core import sync

	return (sync.state().get("status") or "").lower() in ("suspended", "cold", "archived")


def enforce_send_rate(doc, method=None):
	"""before_insert on Email Queue.

	Frappe queues one Email Queue document per send, so counting them is an
	accurate measure of what actually leaves the site.

	Three gates, cheapest first, and each one refuses for a different reason a
	person can act on.
	"""
	if _suspended():
		frappe.throw(
			_("This workspace is suspended and cannot send email."),
			exc=SendingSuspended,
		)

	_drop_suppressed(doc)

	c = config()
	recipients = len(doc.get("recipients") or []) or 1

	for window, limit, sent, wording in (
		("hour", c["hourly_limit"], sent_this_hour(),
		 _("This workspace has reached its limit of {0} emails per hour. "
		   "Queued messages will resume shortly.")),
		("day", c["daily_limit"], sent_today(),
		 _("This workspace has reached its limit of {0} emails per day.")),
	):
		if not limit:
			continue
		if sent + recipients > limit:
			frappe.throw(wording.format(limit), exc=SendRateExceeded)

	# Expires just past its own window so a counter cannot outlive it.
	frappe.cache().set_value(_rate_key("hour"), sent_this_hour() + recipients, expires_in_sec=3700)
	frappe.cache().set_value(_rate_key("day"), sent_today() + recipients, expires_in_sec=90000)


def _drop_suppressed(doc):
	"""Take addresses off a message rather than refusing the whole thing.

	A bounce or a complaint is about one recipient, and refusing the message
	because one of forty is on the list would lose the other thirty-nine. If
	every recipient is suppressed there is nothing to send and the send is
	refused — which is honest, and is also the only case where somebody needs
	telling.
	"""
	from oneapp.oneapp_core.email import suppression

	rows = doc.get("recipients") or []
	if not rows:
		return

	kept = [row for row in rows if not suppression.is_suppressed(row.get("recipient"))]
	if len(kept) == len(rows):
		return

	if not kept:
		frappe.throw(
			_("Every recipient of this message has bounced or reported it as spam."),
			exc=SendRateExceeded,
		)

	doc.set("recipients", kept)


@frappe.whitelist(methods=["GET"])
def usage() -> dict:
	c = config()
	return {
		"sent_this_hour": sent_this_hour(),
		"hourly_limit": c["hourly_limit"],
		"sent_today": sent_today(),
		"daily_limit": c["daily_limit"],
		"sender": sender_address(),
		"configured": bool(c["api_token"]),
		"suspended": _suspended(),
	}
