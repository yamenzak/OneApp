"""Tenant slug validation.

`*.4dl.app` resolves for anything, so a slug is not merely a name — it is a
hostname we are handing out. Names that could be mistaken for our own
infrastructure, or used to phish our users, must never be issuable.
"""

import re

import frappe
from frappe import _

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")

MIN_LENGTH = 3
MAX_LENGTH = 40

# Infrastructure and product surfaces. Anything here would either collide with a
# real hostname or let a tenant impersonate us.
RESERVED_SLUGS = {
    # our own surfaces
    "admin", "api", "app", "apps", "assets", "billing", "blog", "cdn", "control",
    "dashboard", "dev", "docs", "download", "files", "ftp", "git", "help", "one",
    "mail", "media", "ns1", "ns2", "portal", "press", "root", "smtp", "staging",
    "static", "status", "support", "test", "webmail", "www",
    # authentication and payment lures
    "account", "accounts", "auth", "login", "logout", "signin", "signup", "secure",
    "verify", "verification", "password", "reset", "payment", "payments", "pay",
    "checkout", "invoice", "invoices", "stripe",
    # brand
    "4dl", "fourdegreelabs", "oneapp", "frappe", "erpnext",
    # generic traps
    "null", "undefined", "none", "true", "false", "internal", "system", "official",
}


def normalise(slug: str) -> str:
	return (slug or "").strip().lower()


def reserved_slugs() -> set:
	"""Built-in blocklist plus anything added in settings."""
	extra = frappe.db.get_single_value("OneSpace Control Settings", "reserved_slugs") or ""
	extra = {s.strip().lower() for s in re.split(r"[,\n]", extra) if s.strip()}
	return RESERVED_SLUGS | extra


def validate_slug(slug: str) -> str:
	"""Return the normalised slug, or raise a ValidationError explaining why not."""
	slug = normalise(slug)

	if len(slug) < MIN_LENGTH:
		frappe.throw(_("Slug must be at least {0} characters.").format(MIN_LENGTH))
	if len(slug) > MAX_LENGTH:
		frappe.throw(_("Slug must be at most {0} characters.").format(MAX_LENGTH))
	if not SLUG_PATTERN.match(slug):
		frappe.throw(
			_("Slug may only contain lowercase letters, numbers and hyphens, "
			  "and must start and end with a letter or number.")
		)
	if "--" in slug:
		# xn-- is the punycode prefix; consecutive hyphens invite homograph tricks.
		frappe.throw(_("Slug may not contain consecutive hyphens."))
	if slug in reserved_slugs():
		frappe.throw(_("'{0}' is reserved and cannot be used.").format(slug))

	return slug


def is_available(slug: str) -> bool:
	"""Cheap pre-check for signup UX. Press remains the authority on collisions."""
	slug = normalise(slug)
	try:
		validate_slug(slug)
	except frappe.ValidationError:
		return False
	return not frappe.db.exists("Tenant", slug)
