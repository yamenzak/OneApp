"""Tenant slug rules.

A slug is a hostname we hand out under a wildcard, so these rules are a security
boundary, not a naming preference.
"""

import pytest


@pytest.fixture
def slug():
	from oneapp_control.utils import slug as module

	return module


def _throws(slug, value):
	import frappe

	with pytest.raises(frappe.ValidationError):
		slug.validate_slug(value)


@pytest.mark.parametrize("value", ["acme", "acme-corp", "a1b2", "x" * 40, "abc"])
def test_accepts_valid_slugs(slug, value):
	assert slug.validate_slug(value) == value


def test_normalises_case_and_whitespace(slug):
	assert slug.validate_slug("  AcMe  ") == "acme"


@pytest.mark.parametrize("value", ["ab", "", "  "])
def test_rejects_too_short(slug, value):
	_throws(slug, value)


def test_rejects_too_long(slug):
	_throws(slug, "x" * 41)


@pytest.mark.parametrize(
	"value",
	["-acme", "acme-", "ac me", "acme_corp", "acme.corp", "ACME!", "acme/../etc"],
)
def test_rejects_invalid_characters_and_edges(slug, value):
	_throws(slug, value)


def test_rejects_consecutive_hyphens(slug):
	"""xn-- is the punycode prefix; double hyphens invite homograph tricks."""
	_throws(slug, "xn--acme")
	_throws(slug, "ac--me")


@pytest.mark.parametrize(
	"value", ["www", "api", "admin", "mail", "cdn", "login", "stripe", "oneapp", "4dl"]
)
def test_rejects_reserved(slug, value):
	"""These would either collide with our infrastructure or enable phishing."""
	_throws(slug, value)


def test_reserved_check_is_case_insensitive(slug):
	_throws(slug, "ADMIN")


def test_settings_can_add_reserved_slugs(slug, stub_frappe):
	stub_frappe.db.singles[("OneApp Control Settings", "reserved_slugs")] = "acme, beta\ngamma"
	for value in ("acme", "beta", "gamma"):
		_throws(slug, value)
