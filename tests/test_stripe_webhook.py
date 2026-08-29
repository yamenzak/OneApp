"""Stripe signature verification.

The webhook endpoint is public. An unverified payload is an attacker granting
themselves credits, so these are the tests that matter most in the billing path.
"""

import hashlib
import hmac
import time

import pytest

SECRET = "whsec_" + "t" * 32
PAYLOAD = '{"id":"evt_1","type":"invoice.paid"}'


@pytest.fixture
def webhooks(stub_frappe, monkeypatch):
	import types

	# get_password lives on the settings doc, so stand in a minimal one.
	settings = types.SimpleNamespace(
		get_password=lambda field, raise_exception=False: SECRET
	)
	stub_frappe.get_single = lambda *a, **k: settings

	from oneapp_control.billing import webhooks

	return webhooks


def header_for(payload=PAYLOAD, secret=SECRET, timestamp=None, scheme="v1"):
	timestamp = timestamp or int(time.time())
	sig = hmac.new(
		secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256
	).hexdigest()
	return f"t={timestamp},{scheme}={sig}"


def test_accepts_valid_signature(webhooks):
	webhooks.verify_signature(PAYLOAD, header_for())


def test_rejects_wrong_secret(webhooks):
	import frappe

	with pytest.raises(frappe.PermissionError):
		webhooks.verify_signature(PAYLOAD, header_for(secret="whsec_wrong"))


def test_rejects_tampered_payload(webhooks):
	import frappe

	header = header_for()
	with pytest.raises(frappe.PermissionError):
		webhooks.verify_signature('{"id":"evt_1","amount":999999}', header)


def test_rejects_expired_timestamp(webhooks):
	import frappe

	old = int(time.time()) - (webhooks.SIGNATURE_TOLERANCE + 60)
	with pytest.raises(frappe.PermissionError):
		webhooks.verify_signature(PAYLOAD, header_for(timestamp=old))


def test_rejects_missing_header(webhooks):
	import frappe

	with pytest.raises(frappe.PermissionError):
		webhooks.verify_signature(PAYLOAD, None)


@pytest.mark.parametrize("header", ["garbage", "t=123", "v1=abc", "t=abc,v1=def"])
def test_rejects_malformed_header(webhooks, header):
	import frappe

	with pytest.raises(frappe.PermissionError):
		webhooks.verify_signature(PAYLOAD, header)


def test_ignores_unknown_signature_schemes(webhooks):
	"""A v0 signature must not be accepted in place of v1."""
	import frappe

	with pytest.raises(frappe.PermissionError):
		webhooks.verify_signature(PAYLOAD, header_for(scheme="v0"))


def test_accepts_when_multiple_signatures_present(webhooks):
	"""Stripe sends several v1 values during secret rotation."""
	valid = header_for()
	timestamp = valid.split(",")[0].split("=")[1]
	combined = f"{valid},v1={'0' * 64}"
	webhooks.verify_signature(PAYLOAD, combined)
	assert timestamp


def test_status_map_covers_every_stripe_state(webhooks):
	"""An unmapped status would silently become Incomplete and suspend a payer."""
	expected = {
		"trialing", "active", "past_due", "unpaid",
		"canceled", "incomplete", "incomplete_expired",
	}
	assert expected == set(webhooks.STRIPE_STATUS_MAP)


def test_past_due_is_not_a_cancellation(webhooks):
	"""Stripe is still retrying; suspending mid-dunning loses paying customers."""
	assert webhooks.STRIPE_STATUS_MAP["past_due"] == "Past Due"
	assert webhooks.STRIPE_STATUS_MAP["canceled"] == "Canceled"
