"""Server-built customer URLs must land on routes a SPA actually declares.

Checkout return URLs, signup links and billing-portal returns are built in
Python but resolved by a Vue router. Nothing fails loudly when they disagree:
Stripe accepts any URL, the redirect succeeds, and the customer lands on a 404
holding a receipt. So the routers are parsed here and compared against the
builders.

There are two of them now, and which one answers is the point of the split.
`/signup` is the one page somebody reaches *before* they have an account, and it
is all that is left of `oneapp_control`'s frontend. Everything after signing in
— the account, its billing, its domain — is a Space, rendered by `oneapp`'s
router on this same site. So a signup link is checked against the control app's
router and an account link against OneSpace's, and an account link is checked
twice: the path has to resolve, and the `screen` it names has to be a screen the
account Space declares.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

SIGNUP_ROUTER = ROOT / "apps/oneapp_control/frontend/src/router.js"
SPACE_ROUTER = ROOT / "apps/oneapp/frontend/src/router.js"


def declared(router: Path) -> set[str]:
	"""Every path a router resolves, including its history base.

	`createWebHistory('/signup')` means the router's own `/welcome` answers on
	`/signup/welcome`, and the builders produce whole paths — so the base has to
	be part of the comparison or every check would pass against the wrong half.
	"""
	source = router.read_text()
	base = re.search(r"createWebHistory\('([^']*)'\)", source)
	assert base, f"{router} does not set a history base — this guard needs updating"
	prefix = base.group(1).rstrip("/")
	found = set()
	for path in re.findall(r"path:\s*'([^']+)'", source):
		joined = f"{prefix}{path}".rstrip("/")
		found.add(joined or "/")
	return found


def matches(url_path: str, routes: set[str]) -> bool:
	"""Whether a concrete path resolves against a declared route.

	Dynamic segments are compared by shape, so /one/space/onespace-account
	matches the declared /one/space/:spaceCode. Catch-all routes are skipped:
	they match everything, which would make this guard vacuous.
	"""
	for route in routes:
		if "pathMatch" in route:
			continue
		pattern = re.sub(r":[A-Za-z_]+", "[^/]+", re.escape(route).replace(r"\:", ":"))
		if re.fullmatch(pattern, url_path):
			return True
	return False


@pytest.fixture
def portal(stub_frappe):
	from oneapp_control import portal as module

	stub_frappe.db.singles[("OneSpace Control Settings", "control_plane_url")] = (
		"https://app.4dl.app/"
	)
	return module


def _path(url: str) -> str:
	"""The path of a built URL, without origin or query string."""
	return "/" + url.split("://", 1)[-1].split("/", 1)[1].split("?")[0].rstrip("/")


def _query(url: str) -> dict[str, str]:
	if "?" not in url:
		return {}
	return dict(pair.split("=", 1) for pair in url.split("?", 1)[1].split("&"))


def test_both_routers_exist():
	for router in (SIGNUP_ROUTER, SPACE_ROUTER):
		assert router.exists(), f"{router} moved — this guard needs updating"


def test_signup_url_resolves(portal):
	assert matches(_path(portal.signup_url()), declared(SIGNUP_ROUTER))


def test_welcome_url_resolves(portal):
	assert matches(_path(portal.welcome_url("req-1")), declared(SIGNUP_ROUTER))


def test_account_url_resolves(portal):
	assert matches(_path(portal.account_url()), declared(SPACE_ROUTER))


def test_workspace_account_url_resolves(portal):
	assert matches(_path(portal.account_url("acme")), declared(SPACE_ROUTER))


def test_billing_section_url_resolves(portal):
	# The URL Stripe actually returns customers to. This is the one that must
	# not 404.
	assert matches(_path(portal.account_url("acme", "billing")), declared(SPACE_ROUTER))


def test_signup_prefix_is_the_routers_base(portal):
	# The constant and the history base are the same fact written twice. If the
	# router's moves and the constant does not, every check above would still
	# pass — against a base nothing is served from.
	base = re.search(r"createWebHistory\('([^']*)'\)", SIGNUP_ROUTER.read_text())
	assert base.group(1).rstrip("/") == portal.PREFIX


def test_the_account_space_is_the_one_that_is_declared(portal):
	# The path segment is a space_code, resolved server-side. A typo here is a
	# 404 that no route pattern would catch, because /one/space/:spaceCode
	# matches any nonsense.
	from oneapp_control.entitlements import account

	assert portal.ACCOUNT_SPACE == account.SPACE_CODE
	assert portal.ACCOUNT.endswith(f"/{account.SPACE_CODE}")


@pytest.mark.parametrize("section", ["overview", "billing", "plan", "people", "domain"])
def test_a_linked_section_is_a_screen_the_space_declares(portal, section):
	# `screen` is resolved against the Space's own screens, so a section this
	# file names but `account.py` does not is the same dead end as a bad route —
	# and the sections here are what Stripe and our emails link to.
	from oneapp_control.entitlements import account

	screens = {screen for screen, _label, _icon in account.SCREENS}
	assert _query(portal.account_url("acme", section))["screen"] in screens


def test_the_workspace_travels_as_a_query(portal):
	# The account Space picks the workspace it shows from shared state; a link
	# out of Stripe or an email says which one it meant this way, and the screen
	# reads it off the route query.
	assert _query(portal.account_url("acme", "billing"))["workspace"] == "acme"


def test_stripe_placeholder_survives(portal):
	# Stripe substitutes this token itself; url-encoding the braces would send
	# the customer back with a literal, unusable session id.
	url = portal.account_url("acme", session="{CHECKOUT_SESSION_ID}")
	assert "session={CHECKOUT_SESSION_ID}" in url


def test_none_query_values_are_dropped(portal):
	assert "?" not in portal.account_url(checkout=None)


def test_base_url_has_no_trailing_slash(portal):
	# The setting is entered by hand in the admin UI, so a trailing slash is
	# likely and would produce //signup/... in every link.
	assert portal.base_url() == "https://app.4dl.app"


def test_base_url_refuses_when_unconfigured(portal, stub_frappe):
	stub_frappe.db.singles[("OneSpace Control Settings", "control_plane_url")] = None
	with pytest.raises(Exception, match="control_plane_url"):
		portal.base_url()


def test_checkout_urls_use_the_builders():
	# A hand-built f-string here is exactly the drift this module exists to
	# prevent, and it would pass every test above.
	source = (
		ROOT / "apps/oneapp_control/oneapp_control/billing/checkout.py"
	).read_text()
	assert "control_plane_url" not in source, "checkout.py should build URLs via portal.py"
