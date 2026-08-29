"""HMAC signing between the control plane and tenant sites."""

import time

import pytest


@pytest.fixture
def signing():
	from oneapp_control.utils import signing

	return signing


SECRET = "s" * 64


def test_signature_round_trips(signing):
	body = {"b": 2, "a": 1}
	sig, ts = signing.sign(SECRET, body)
	assert signing.verify(SECRET, body, sig, ts)


def test_key_order_does_not_change_signature(signing):
	"""Both ends must canonicalise identically or nothing verifies."""
	a, _ = signing.sign(SECRET, {"a": 1, "b": 2}, timestamp=1000)
	b, _ = signing.sign(SECRET, {"b": 2, "a": 1}, timestamp=1000)
	assert a == b


def test_wrong_secret_fails(signing):
	body = {"x": 1}
	sig, ts = signing.sign(SECRET, body)
	assert not signing.verify("different" * 8, body, sig, ts)


def test_tampered_body_fails(signing):
	sig, ts = signing.sign(SECRET, {"amount": 1})
	assert not signing.verify(SECRET, {"amount": 1000000}, sig, ts)


def test_replay_outside_window_fails(signing):
	"""The timestamp is signed, so an old capture cannot be replayed."""
	old = int(time.time()) - (signing.TOLERANCE_SECONDS + 60)
	sig, ts = signing.sign(SECRET, {"x": 1}, timestamp=old)
	assert not signing.verify(SECRET, {"x": 1}, sig, ts)


def test_within_window_succeeds(signing):
	recent = int(time.time()) - (signing.TOLERANCE_SECONDS - 30)
	sig, ts = signing.sign(SECRET, {"x": 1}, timestamp=recent)
	assert signing.verify(SECRET, {"x": 1}, sig, ts)


def test_timestamp_cannot_be_moved_forward(signing):
	"""Changing the timestamp must invalidate the signature."""
	sig, ts = signing.sign(SECRET, {"x": 1})
	assert not signing.verify(SECRET, {"x": 1}, sig, str(int(ts) + 1))


@pytest.mark.parametrize("sig,ts", [(None, "1"), ("abc", None), ("", ""), ("abc", "nope")])
def test_missing_or_malformed_inputs_fail(signing, sig, ts):
	assert not signing.verify(SECRET, {}, sig, ts)


def test_empty_secret_fails(signing):
	sig, ts = signing.sign(SECRET, {"x": 1})
	assert not signing.verify("", {"x": 1}, sig, ts)


def test_tenant_site_and_control_plane_agree(signing):
	"""The two implementations are separate code and must stay compatible."""
	from oneapp.oneapp_core import control_client

	body = '{"a":1,"b":2}'
	sig, ts = control_client._sign(SECRET, body)
	assert signing.verify(SECRET, body, sig, ts)
