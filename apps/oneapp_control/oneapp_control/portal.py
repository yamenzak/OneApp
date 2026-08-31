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

# Signing up is its own small surface, on its own route, because it is the one
# page somebody reaches before they have an account — `/one` sends a Guest to
# sign in, correctly, and this cannot. Mirrors `frontend/src/router.js`.
PREFIX = "/signup"

SIGNUP = PREFIX
WELCOME = f"{PREFIX}/welcome"

# The account is a Space now, rendered by OneSpace on this site rather than by a
# second SPA. `onespace-account` is what `entitlements/account.py` declares, and
# the screen is a query rather than a path segment because that is the shape
# `oneapp`'s router uses — see its `/space/:spaceCode` route.
ACCOUNT_SPACE = "onespace-account"
ACCOUNT = f"/one/space/{ACCOUNT_SPACE}"


def landing(user: str | None = None) -> str:
	"""Where a signed-in person lands on the control site.

	`one`, for everybody. An operator and a customer are two Spaces in the same
	shell now, and which one opens is decided by the roles they hold —
	`visible_spaces` filters on `role_name`, and the launcher shows what is
	left. So this no longer has to know the difference.

	Still a function rather than the `home_page` string, because `oneapp`
	declares one too and Frappe takes the *last* app's — which app that is
	depends on the order they were installed in. Frappe checks this hook before
	either `home_page` or `role_home_page`, so this is the whole answer.
	"""
	return "one"


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
	"""A screen in the customer's account.

	`section` is a screen of the account Space — overview, billing, domain — and
	is a query parameter rather than a path segment, because that is how
	`oneapp`'s router addresses a screen: the path names the space and the query
	names the screen.

	`workspace` is carried the same way. The account Space picks which workspace
	it is showing from shared state with a switcher, and this is how a link out
	of Stripe or an email says which one it meant.
	"""
	found = dict(query)
	if section:
		found["screen"] = section
	if workspace:
		found["workspace"] = workspace
	return _build(ACCOUNT, found)


def _build(path: str, query: dict) -> str:
	url = f"{base_url()}{path}"
	# Stripe's {CHECKOUT_SESSION_ID} placeholder must survive verbatim, so the
	# query string is assembled by hand rather than url-encoded.
	pairs = [f"{k}={v}" for k, v in query.items() if v is not None]
	return f"{url}?{'&'.join(pairs)}" if pairs else url
