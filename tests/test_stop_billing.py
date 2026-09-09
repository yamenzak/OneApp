"""We stop charging when we take the workspace away.

`stripe_client.cancel_subscription` was written in Phase 4 and called by nothing
for the whole of the product's life. Stripe's own dunning cancels most
subscriptions before the ladder gets anywhere near them, which is exactly why
this was easy to miss: the failure only appears in the cases that *do not* go
through dunning — a workspace archived by an operator, one whose card is fine
and whose owner asked to be removed — and it appears as a charge for a workspace
we deleted.

So: at the archive, which is the moment the site stops existing, and again at
the purge for anything that reached it still subscribed.
"""

import pytest


@pytest.fixture
def checkout(stub_frappe):
	from oneapp_control.billing import checkout as module

	return module


@pytest.fixture
def stripe(checkout, monkeypatch):
	"""Stripe, recording what it was asked to do."""
	calls = []

	def cancel(subscription_id, at_period_end=True):
		calls.append((subscription_id, at_period_end))
		return {"id": subscription_id, "status": "canceled"}

	monkeypatch.setattr(checkout.stripe_client, "cancel_subscription", cancel)
	return calls


def _subscriptions(stub_frappe, rows):
	stub_frappe.get_all = lambda *a, **k: list(rows)


def test_the_subscription_is_cancelled_now_rather_than_at_period_end(
	checkout, stub_frappe, stripe
):
	"""`cancel_at_period_end` keeps a subscription alive through a month the
	workspace no longer exists for, which is the thing being avoided."""
	_subscriptions(stub_frappe, [{"name": "SUB-1", "stripe_subscription_id": "sub_123"}])

	result = checkout.stop_billing("acme", reason="archived")

	assert stripe == [("sub_123", False)]
	assert result == {"ok": True, "cancelled": 1, "failed": []}


def test_our_own_row_is_marked_cancelled_too(checkout, stub_frappe, stripe):
	"""The webhook says the same thing a moment later. The local write is what
	the ladder reads on its next pass, which may be before the event lands."""
	_subscriptions(stub_frappe, [{"name": "SUB-1", "stripe_subscription_id": "sub_123"}])

	checkout.stop_billing("acme")

	assert ("Subscription", "SUB-1", "status", "Canceled") in stub_frappe.db.writes


def test_a_workspace_that_never_paid_is_not_an_error(checkout, stub_frappe, stripe):
	_subscriptions(stub_frappe, [])

	assert checkout.stop_billing("acme")["cancelled"] == 0
	assert stripe == []


def test_a_row_with_no_stripe_id_is_skipped(checkout, stub_frappe, stripe):
	"""A subscription that never reached Stripe — an abandoned checkout — has
	nothing to cancel and must not be reported as a failure."""
	_subscriptions(stub_frappe, [{"name": "SUB-1", "stripe_subscription_id": None}])

	assert checkout.stop_billing("acme") == {
		"ok": True, "cancelled": 0, "reason": "nothing to cancel",
	}


def test_stripe_being_down_does_not_stop_the_archive(checkout, stub_frappe, monkeypatch):
	"""The caller is `finalise_archive`. A workspace stuck mid-ladder because
	Stripe was unreachable is one that still costs us a site plan, with every
	rung below it blocked — and the purge calls this again anyway.
	"""
	def refuse(subscription_id, at_period_end=True):
		raise RuntimeError("stripe is having a day")

	monkeypatch.setattr(checkout.stripe_client, "cancel_subscription", refuse)
	_subscriptions(stub_frappe, [{"name": "SUB-1", "stripe_subscription_id": "sub_123"}])

	result = checkout.stop_billing("acme")

	assert result["ok"] is False
	assert result["failed"][0]["subscription"] == "SUB-1"
	# And nothing was marked cancelled on our side, because it is not.
	assert not [w for w in stub_frappe.db.writes if w[0] == "Subscription"]


def test_the_archive_stops_the_billing(stub_frappe, monkeypatch):
	"""Read off the step rather than run through press: what this pins is that
	the call is there at all, which is the whole of what was missing."""
	import inspect

	from oneapp_control.provisioning import steps

	assert "stop_billing" in inspect.getsource(steps.finalise_archive)


def test_the_purge_tries_again(stub_frappe):
	import inspect

	from oneapp_control.lifecycle import cold

	body = inspect.getsource(cold.purge)
	assert "stop_billing" in body
	# Before the deletion rather than after: a purge that dies halfway should
	# already have stopped the charging.
	assert body.index("stop_billing") < body.index("delete_prefix")
