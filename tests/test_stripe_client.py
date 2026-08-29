"""Stripe form encoding.

Stripe takes bracket-notation form data, not JSON. Nested line items encoded
wrongly fail in ways that are tedious to debug against a live API.
"""

import pytest


@pytest.fixture
def client():
	from oneapp_control.billing import stripe_client

	return stripe_client


def test_flattens_scalars(client):
	assert dict(client._flatten({"mode": "payment"})) == {"mode": "payment"}


def test_flattens_nested_dicts(client):
	out = dict(client._flatten({"metadata": {"tenant": "acme"}}))
	assert out == {"metadata[tenant]": "acme"}


def test_flattens_list_of_dicts(client):
	out = dict(
		client._flatten({"line_items": [{"price": "price_1", "quantity": 1}]})
	)
	assert out == {
		"line_items[0][price]": "price_1",
		"line_items[0][quantity]": "1",
	}


def test_flattens_deeply_nested_price_data(client):
	out = dict(
		client._flatten(
			{
				"line_items": [
					{"price_data": {"currency": "usd", "product_data": {"name": "Credits"}}}
				]
			}
		)
	)
	assert out["line_items[0][price_data][currency]"] == "usd"
	assert out["line_items[0][price_data][product_data][name]"] == "Credits"


def test_drops_none_values(client):
	"""Sending an empty string where Stripe expects an absent field is an error."""
	assert dict(client._flatten({"a": None, "b": "x"})) == {"b": "x"}


def test_flattens_scalar_lists(client):
	assert dict(client._flatten({"expand": ["a", "b"]})) == {
		"expand[0]": "a",
		"expand[1]": "b",
	}
