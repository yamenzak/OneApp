"""Customer-facing URLs.

Every link we hand to Stripe, put in an email, or redirect a browser to has to
land on a route the SPA actually declares. Those routes live in
``frontend/src/router.js``; these builders are the server's half of that
contract, kept in one file so a route rename is a single edit rather than a hunt
through checkout, emails and provisioning.

``tests/test_portal_urls.py`` parses the router and fails if the two drift. A
mismatch is invisible until a paying customer lands on a 404 after checkout, so
it is worth a test rather than care.
"""

import frappe

# Mirrors the `portalRoutes` prefix in frontend/src/router.js.
PREFIX = "/portal"

SIGNUP = f"{PREFIX}/signup"
WELCOME = f"{PREFIX}/welcome"
ACCOUNT = f"{PREFIX}/account"


def base_url() -> str:
	"""The control plane's public origin, without a trailing slash.

	Configured rather than derived, and with no fallback. The control site also
	answers on its Frappe Cloud hostname, so a link built from whichever host
	served the request would sometimes send customers to the wrong origin — and
	Stripe would accept it, making the mistake visible only to the customer who
	could not get back. Refusing is the safe failure: signup is already gated on
	this setting being present.
	"""
	configured = frappe.db.get_single_value("OneApp Control Settings", "control_plane_url")
	if not configured:
		frappe.throw(
			"control_plane_url is not set in OneApp Control Settings, so no "
			"customer-facing link can be built."
		)
	return configured.rstrip("/")


def signup_url(**query) -> str:
	return _build(SIGNUP, query)


def welcome_url(request: str) -> str:
	return _build(WELCOME, {"request": request})


def account_url(workspace: str | None = None, **query) -> str:
	path = f"{ACCOUNT}/{workspace}" if workspace else ACCOUNT
	return _build(path, query)


def _build(path: str, query: dict) -> str:
	url = f"{base_url()}{path}"
	# Stripe's {CHECKOUT_SESSION_ID} placeholder must survive verbatim, so the
	# query string is assembled by hand rather than url-encoded.
	pairs = [f"{k}={v}" for k, v in query.items() if v is not None]
	return f"{url}?{'&'.join(pairs)}" if pairs else url
