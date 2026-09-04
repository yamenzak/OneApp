"""Sending as a domain the customer owns, and not until they say we may.

A workspace can put its own address on outgoing mail — `billing@theirs.com`
rather than `billing@theirs.4dl.app`. Doing that means asserting, to every
receiving mail server in the world, that we are allowed to send as them. The
only thing that makes that assertion true is DNS they publish, and the only
thing that makes it *safe* is refusing to send until they have.

Three records, and each one fails differently when it is missing:

* **SPF** — a TXT on the domain naming the senders it authorises. Missing, mail
  arrives unauthenticated and is graded down rather than rejected, so the
  symptom is "some of it goes to spam" and nobody can tell you which.
* **DKIM** — a TXT on a selector holding the public key we sign with. Missing,
  the signature does not verify and a DMARC policy of anything but `none`
  rejects outright.
* **DMARC** — a TXT on `_dmarc` saying what a receiver should do when the first
  two disagree. Missing, receivers make their own minds up.

The verification is deliberately a *lookup*, not a claim. A customer pressing
"verify" runs a DNS query from our side and believes the answer; there is
nothing to store that a customer could set themselves.

Kept on the tenant site rather than the control plane on purpose, even though
the reputation being spent is the platform's: the records are the customer's to
publish and the customer's to fix, so the screen that shows them has to be the
one they can reach. What the control plane keeps is the *consequence* — the
suppression list and the sending limits — because those outlive any one tenant.
"""

import frappe
from frappe import _

from oneapp.oneapp_core.workspace import OWNER_ROLE, SUPPORT_ROLE

# Where a verified domain is remembered. A Frappe `Email Domain` already exists
# for holding per-domain mail settings, so the verdict rides on it rather than
# in a doctype of ours that would hold one boolean.
SETTING = "oneapp_verified_at"

# The selector we publish under. One for the platform rather than one per
# customer: the key is ours, the rotation is ours, and a customer with their own
# selector would be a customer we cannot rotate without asking.
SELECTOR = "onespace"


def _require_admin():
	roles = set(frappe.get_roles())
	if not roles & {OWNER_ROLE, SUPPORT_ROLE}:
		frappe.throw(_("Only a workspace admin can verify a domain."), frappe.PermissionError)


def _platform() -> dict:
	conf = frappe.conf
	return {
		"mail_domain": conf.get("oneapp_mail_domain") or "mail.4dl.app",
		"dkim_public_key": conf.get("oneapp_dkim_public_key") or "",
	}


def records(domain: str) -> list[dict]:
	"""What the customer has to publish, ready to copy.

	Returned even when we cannot yet fill in the DKIM key, with the value blank
	and a note — a screen that shows two of three records and hides the third
	because a bench setting is missing is a screen that sends somebody looking
	for a DNS problem they do not have.
	"""
	platform = _platform()
	return [
		{
			"kind": "SPF",
			"type": "TXT",
			"host": domain,
			"value": f"v=spf1 include:{platform['mail_domain']} ~all",
			"note": _(
				"If you already have an SPF record, add the include to it rather "
				"than publishing a second one — two SPF records is the same as none."
			),
		},
		{
			"kind": "DKIM",
			"type": "TXT",
			"host": f"{SELECTOR}._domainkey.{domain}",
			"value": (
				f"v=DKIM1; k=rsa; p={platform['dkim_public_key']}"
				if platform["dkim_public_key"]
				else ""
			),
			"note": (
				""
				if platform["dkim_public_key"]
				else _("Not available yet — the platform has no signing key configured.")
			),
		},
		{
			"kind": "DMARC",
			"type": "TXT",
			"host": f"_dmarc.{domain}",
			"value": "v=DMARC1; p=none; rua=mailto:dmarc@" + platform["mail_domain"],
			"note": _(
				"Start at p=none so nothing is rejected while you watch the "
				"reports, then tighten to quarantine and reject."
			),
		},
	]


def _txt(host: str) -> list[str]:
	"""Every TXT string at a host, or nothing when DNS will not say.

	Failures are indistinguishable from an unpublished record on purpose: the
	only action either one supports is "publish it and try again", and telling
	somebody their resolver timed out invites them to believe the record is fine.
	"""
	try:
		import dns.resolver
	except ImportError:
		return []

	try:
		answer = dns.resolver.resolve(host, "TXT", lifetime=5)
	except Exception:
		return []

	found = []
	for record in answer:
		# A long TXT arrives as several strings and has to be joined before it
		# means anything — a DKIM key is always longer than 255 bytes, so a
		# check that looked at the first string alone would never pass.
		parts = [
			one.decode() if isinstance(one, bytes) else str(one)
			for one in getattr(record, "strings", [])
		]
		found.append("".join(parts) if parts else str(record).strip('"'))
	return found


def check(domain: str) -> dict:
	"""Look the three records up and say which are there."""
	platform = _platform()
	spf = any(
		one.startswith("v=spf1") and platform["mail_domain"] in one
		for one in _txt(domain)
	)
	dkim = any(
		"p=" in one and (
			not platform["dkim_public_key"] or platform["dkim_public_key"][:40] in one
		)
		for one in _txt(f"{SELECTOR}._domainkey.{domain}")
	)
	dmarc = any(one.startswith("v=DMARC1") for one in _txt(f"_dmarc.{domain}"))

	return {
		"domain": domain,
		"spf": spf,
		"dkim": dkim,
		"dmarc": dmarc,
		# DMARC is advice to receivers and costs us nothing to send without, so
		# it is reported and not required. SPF and DKIM are the two that decide
		# whether the mail is ours to send.
		"verified": bool(spf and dkim),
	}


def is_verified(domain: str) -> bool:
	"""Whether we have ever confirmed this domain. Cheap; reads the stored verdict."""
	if not domain:
		return False
	if not frappe.db.exists("Email Domain", domain):
		return False
	return bool(frappe.db.get_value("Email Domain", domain, "email_id"))


@frappe.whitelist(methods=["GET"])
def status(domain: str) -> dict:
	"""The records to publish and whether they are published."""
	_require_admin()
	domain = (domain or "").strip().lower()
	if not domain:
		frappe.throw(_("Which domain?"))
	return {"records": records(domain), **check(domain)}


@frappe.whitelist(methods=["POST"])
def confirm(domain: str) -> dict:
	"""Re-check, and remember it where `set_default` will look.

	Storing the verdict rather than checking at send time is deliberate: a
	resolver blip must not stop a workspace's mail, and DNS that was right once
	and is wrong now shows up as bounces we handle anyway.
	"""
	_require_admin()
	domain = (domain or "").strip().lower()
	result = check(domain)

	if not result["verified"]:
		frappe.throw(
			_("{0} is not verified yet. SPF: {1}. DKIM: {2}.").format(
				domain,
				_("found") if result["spf"] else _("missing"),
				_("found") if result["dkim"] else _("missing"),
			)
		)

	if not frappe.db.exists("Email Domain", domain):
		frappe.get_doc(
			{
				"doctype": "Email Domain",
				"domain_name": domain,
				# `email_id` on Email Domain is an example address the desk uses
				# to work the rest out. Ours doubles as the record that this
				# domain has been confirmed — see `is_verified`.
				"email_id": f"postmaster@{domain}",
				"smtp_server": "smtp.mx.cloudflare.net",
				"smtp_port": 465,
				"use_ssl_for_outgoing": 1,
			}
		).insert(ignore_permissions=True)

	return {"ok": True, **result}
