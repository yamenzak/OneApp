"""Email Routing on the zone: turning it on, and pointing it at the worker.

Two calls do the whole of inbound. `POST …/email/routing/enable` adds and locks
the MX and SPF records; `PUT …/rules/catch_all` says that everything arriving
goes to our worker. Both are idempotent, which is what lets the bring-up be a
button somebody presses whenever they are unsure.

**One domain, and the reason is a limit rather than a preference.** Cloudflare
allows a zone 30 domains configured for Email Routing or Email Sending
*combined*, including the apex, and there is no wildcard — every subdomain is
onboarded one at a time. A subdomain per workspace would therefore cap the
platform at about twenty-nine workspaces. So every workspace shares one domain
and the tenant rides in the local part: `acme.ap@4dl.app`. See
`workers/email-inbound/src/routing.js` and `docs/EMAIL.md`.

The one thing here that is not automated is **Email Sending** onboarding, which
Cloudflare exposes in the dashboard and not in its API. `sending_ready()` says
so rather than pretending, and names the screen.
"""

import frappe
from frappe import _

from . import api, workers

CATCH_ALL_NAME = "OneSpace inbound"


def status() -> dict:
	"""What Email Routing thinks of this zone. Never raises for "not set up"."""
	zone = api.zone_id()
	if not zone:
		return {"configured": False, "reason": "No DNS zone id in settings."}

	try:
		found = api.call("GET", f"zones/{zone}/email/routing")
	except api.NotConfigured as e:
		return {"configured": False, "reason": str(e)}
	except api.CloudflareError as e:
		return {"configured": False, "reason": str(e)}

	return {
		"configured": True,
		"enabled": bool(found.get("enabled")),
		"status": found.get("status"),
		"name": found.get("name"),
	}


def enable() -> dict:
	"""Turn Email Routing on, which is also what writes the MX and SPF records.

	Cloudflare locks those records afterwards, so nothing of ours needs to
	create or defend them.
	"""
	zone = _zone()

	try:
		return api.call("POST", f"zones/{zone}/email/routing/enable")
	except api.CloudflareError as e:
		# Already on is the ordinary answer on the second run, and it is not a
		# failure of anything.
		if "already" in str(e).lower():
			return {"already": True}
		raise


def point_catch_all(script: str = workers.SCRIPT_NAME) -> dict:
	"""Everything arriving on the zone goes to our worker.

	A catch-all rather than a rule per address, deliberately: an address is a
	row on a tenant site, and Cloudflare has no business holding a second copy
	of a list that changes whenever somebody in a workspace adds a colleague.
	It also keeps us to one routing rule for ever, against a limit of 200.
	"""
	return api.call(
		"PUT",
		f"zones/{_zone()}/email/routing/rules/catch_all",
		json={
			"name": CATCH_ALL_NAME,
			"enabled": True,
			"matchers": [{"type": "all"}],
			"actions": [{"type": "worker", "value": [script]}],
		},
	)


def catch_all() -> dict:
	try:
		return api.call("GET", f"zones/{_zone()}/email/routing/rules/catch_all")
	except api.CloudflareError:
		return {}


def points_at_worker(script: str = workers.SCRIPT_NAME) -> bool:
	"""Whether the catch-all is on and aimed at us."""
	rule = catch_all()
	if not rule.get("enabled"):
		return False
	for action in rule.get("actions") or []:
		if action.get("type") == "worker" and script in (action.get("value") or []):
			return True
	return False


def domain_is_the_zone() -> dict:
	"""Whether `mail_domain` is the apex of the zone we hold the id for.

	The one misconfiguration that fails silently and late. Email Routing is a
	*zone* feature and its catch-all matches the zone's own apex — so a
	`mail_domain` of `mail.4dl.app` against a zone of `4dl.app` deploys cleanly,
	enables cleanly, and then bounces every message, because no subdomain was
	onboarded and there is no wildcard. Onboarding the apex is the whole point of
	the local-part scheme; see the module docstring.

	A subdomain would not merely be extra work, it would spend one of the thirty
	domains the zone is allowed for nothing.
	"""
	domain = (api.settings().mail_domain or "").strip().lower()
	apex = api.zone_name().strip().lower()

	if not domain:
		return {"ok": False, "detail": _("No mail domain set.")}
	if not apex:
		# Cannot be asked — no token, no zone id, or Cloudflare is down. Not a
		# mismatch, and refusing the bring-up on it would be refusing on
		# ignorance.
		return {"ok": True, "detail": _("Zone apex could not be read; not checked.")}
	if domain != apex:
		return {
			"ok": False,
			"detail": _(
				"The mail domain is {0} but the zone is {1}. Email Routing works on "
				"the zone itself, so mail sent to {0} would never arrive. Set the mail "
				"domain to {1}."
			).format(domain, apex),
		}
	return {"ok": True, "detail": _("{0} is the zone.").format(apex)}


def _zone() -> str:
	zone = api.zone_id()
	if not zone:
		frappe.throw(_("Set the DNS zone id in OneSpace Control Settings first."))
	return zone


# --------------------------------------------------------------------------- #
# The half Cloudflare does not expose
# --------------------------------------------------------------------------- #

#: Where an operator has to go, once, because there is no API for it.
SENDING_SCREEN = "Cloudflare dashboard → Compute → Email Service → Email Sending → Onboard Domain"


def sending_ready() -> dict:
	"""Whether outbound is likely to work, and what to do if not.

	Cloudflare refuses an SMTP `MAIL FROM` on a domain that has not been
	onboarded for Email Sending, and onboarding is a dashboard action with no
	documented API. So this cannot be automated and is not claimed to be: what
	it does is check the two things that *are* visible from here — that a
	sending token exists and that the bounce records Cloudflare writes on
	`cf-bounce` are present — and name the screen otherwise.
	"""
	from . import dns

	s = api.settings()
	domain = s.mail_domain or ""
	has_token = bool(s.get_password("cf_email_token", raise_exception=False))

	if not domain:
		return {"ok": False, "detail": _("No mail domain set."), "where": SENDING_SCREEN}
	if not has_token:
		return {
			"ok": False,
			"detail": _("No Email Sending token."),
			"where": SENDING_SCREEN,
		}

	onboarded = dns.has_record(f"cf-bounce.{domain}", "MX")
	return {
		"ok": onboarded,
		"detail": (
			_("Onboarded — Cloudflare's bounce records are on cf-bounce.{0}.").format(domain)
			if onboarded
			else _("{0} is not onboarded for Email Sending. This is the one step "
			       "with no API.").format(domain)
		),
		"where": SENDING_SCREEN,
	}
