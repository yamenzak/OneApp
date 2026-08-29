"""Server-built customer URLs must land on routes the SPA declares.

Checkout return URLs, signup links and billing-portal returns are built in
Python but resolved by the Vue router. Nothing fails loudly when they disagree:
Stripe accepts any URL, the redirect succeeds, and the customer lands on a 404
holding a receipt. So the router is parsed here and compared against the
builders.
"""

import re
from pathlib import Path

import pytest

ROUTER = (
	Path(__file__).resolve().parents[1]
	/ "apps/oneapp_control/frontend/src/router.js"
)


def declared_paths() -> set[str]:
	"""Every `path:` literal in the router."""
	return set(re.findall(r"path:\s*'([^']+)'", ROUTER.read_text()))


def matches(url_path: str, declared: set[str]) -> bool:
	"""Whether a concrete path resolves against a declared route.

	Dynamic segments are compared by shape, so /portal/account/acme matches the
	declared /portal/account/:workspace.
	"""
	for route in declared:
		pattern = re.sub(r":[A-Za-z_]+", "[^/]+", re.escape(route).replace(r"\:", ":"))
		if re.fullmatch(pattern, url_path):
			return True
	return False


@pytest.fixture
def portal(stub_frappe):
	from oneapp_control import portal as module

	stub_frappe.db.singles[("OneApp Control Settings", "control_plane_url")] = (
		"https://app.4dl.app/"
	)
	return module


def _path(url: str) -> str:
	"""The path of a built URL, without origin or query string."""
	return url.split("://", 1)[-1].split("/", 1)[1].split("?")[0].rstrip("/")


def test_router_file_exists():
	assert ROUTER.exists(), f"{ROUTER} moved — this guard needs updating"


def test_signup_url_resolves(portal):
	assert matches("/" + _path(portal.signup_url()), declared_paths())


def test_welcome_url_resolves(portal):
	assert matches("/" + _path(portal.welcome_url("req-1")), declared_paths())


def test_account_url_resolves(portal):
	assert matches("/" + _path(portal.account_url()), declared_paths())


def test_workspace_account_url_resolves(portal):
	assert matches("/" + _path(portal.account_url("acme")), declared_paths())


def test_prefix_matches_router(portal):
	# Every portal route shares one prefix; if the router's changes and the
	# constant does not, the checks above would still pass against stale routes.
	portal_routes = {p for p in declared_paths() if p.startswith(portal.PREFIX)}
	assert portal_routes, f"no routes under {portal.PREFIX} in the router"


def test_stripe_placeholder_survives(portal):
	# Stripe substitutes this token itself; url-encoding the braces would send
	# the customer back with a literal, unusable session id.
	url = portal.account_url("acme", session="{CHECKOUT_SESSION_ID}")
	assert "session={CHECKOUT_SESSION_ID}" in url


def test_none_query_values_are_dropped(portal):
	assert "?" not in portal.account_url("acme", checkout=None)


def test_base_url_has_no_trailing_slash(portal):
	# The setting is entered by hand in the admin UI, so a trailing slash is
	# likely and would produce //portal/... in every link.
	assert portal.base_url() == "https://app.4dl.app"


def test_base_url_refuses_when_unconfigured(portal, stub_frappe):
	stub_frappe.db.singles[("OneApp Control Settings", "control_plane_url")] = None
	with pytest.raises(Exception, match="control_plane_url"):
		portal.base_url()


def test_checkout_urls_use_the_builders():
	# A hand-built f-string here is exactly the drift this module exists to
	# prevent, and it would pass every test above.
	source = (
		Path(__file__).resolve().parents[1]
		/ "apps/oneapp_control/oneapp_control/billing/checkout.py"
	).read_text()
	assert "control_plane_url" not in source, "checkout.py should build URLs via portal.py"
