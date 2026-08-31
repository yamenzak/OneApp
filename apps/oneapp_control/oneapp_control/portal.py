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


def landing(user: str | None = None) -> str:
	"""Where a signed-in person lands on the control site.

	A function rather than the `home_page` string, because `oneapp` is
	installed here too and declares its own. Frappe takes the *last* app's
	`home_page`, so which console opened would depend on the order the two
	apps happened to be installed in — a decision made by a bench rebuild
	rather than by anybody.

	Frappe checks this hook before either `home_page` or `role_home_page`, so
	this is the whole answer.
	"""
	# Imported here rather than at module scope: this file is the URL contract
	# and importing provisioning to read one constant would make every caller
	# of `account_url` pull the signup machinery in with it.
	from oneapp_control.provisioning.signup import CUSTOMER_ROLE

	roles = set(frappe.get_roles(user) if user else frappe.get_roles())
	if CUSTOMER_ROLE in roles:
		return ACCOUNT.lstrip("/")
	# The operator console. One line to change when it becomes a Space.
	return "admin"


def base_url() -> str:
	"""The control plane's public origin, without a trailing slash.

	Configured rather than derived, and with no fallback. The control site also
	answers on its Frappe Cloud hostname, so a link built from whichever host
	served the request would sometimes send customers to the wrong origin — and
	Stripe would accept it, making the mistake visible only to the customer who
	could not get back. Refusing is the safe failure: signup is already gated on
	this setting being present.
	"""
	configured = frappe.db.get_single_value("OneSpace Control Settings", "control_plane_url")
	if not configured:
		frappe.throw(
			"control_plane_url is not set in OneSpace Control Settings, so no "
			"customer-facing link can be built."
		)
	return configured.rstrip("/")


def signup_url(**query) -> str:
	return _build(SIGNUP, query)


def welcome_url(request: str) -> str:
	return _build(WELCOME, {"request": request})


def account_url(workspace: str | None = None, section: str | None = None, **query) -> str:
	"""A page in the customer's account.

	`section` is a sidebar destination — overview, billing, domain — and is part
	of the path rather than a query flag, because each one is its own route.
	"""
	path = ACCOUNT
	if workspace:
		path = f"{path}/{workspace}"
		if section:
			path = f"{path}/{section}"
	return _build(path, query)


def _build(path: str, query: dict) -> str:
	url = f"{base_url()}{path}"
	# Stripe's {CHECKOUT_SESSION_ID} placeholder must survive verbatim, so the
	# query string is assembled by hand rather than url-encoded.
	pairs = [f"{k}={v}" for k, v in query.items() if v is not None]
	return f"{url}?{'&'.join(pairs)}" if pairs else url
