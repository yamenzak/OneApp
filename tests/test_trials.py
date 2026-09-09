"""A fortnight before the first charge.

`signup.py` says the card comes first and gives its reason — a fresh site per
throwaway email is expensive. A trial does not change that: Stripe holds the card
from the start and bills automatically when the trial ends. What moves is *when*
the money leaves, which is the whole of the conversion argument and none of the
abuse one.

Almost all of it was already here — `trialing` is mapped from the webhook, is
deliberately not in the dunning sweep's `UNPAID`, and counts as live in the plan
count, the subscription guards, checkout and quotas. What was missing was a term
on the plan, a rule about who gets one, and the credits.
"""

import ast
import sys
from pathlib import Path

import pytest

import where

ROOT = Path(where.__file__).resolve().parent.parent
APP = ROOT / "apps/oneapp_control/oneapp_control"
CHECKOUT = APP / "billing/checkout.py"
WEBHOOKS = APP / "billing/webhooks.py"
SWEEP = APP / "lifecycle/sweep.py"


@pytest.fixture
def checkout(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp_control"):
			del sys.modules[name]
	from oneapp_control.billing import checkout as module

	return module


def plan(days):
	return type("Plan", (), {"trial_days": days})()


# --------------------------------------------------------------------------- #
# Who gets one
# --------------------------------------------------------------------------- #

def test_a_plan_with_no_trial_gives_none(checkout, stub_frappe):
	"""Which is every plan by default, and every plan but the entry one for
	ever: a trial on an upgrade is a discount nobody asked for."""
	stub_frappe.db.exists = lambda *a, **k: None
	assert checkout.trial_days_for("t", plan(0)) == 0


def test_a_first_subscription_gets_the_trial(checkout, stub_frappe):
	stub_frappe.db.exists = lambda *a, **k: None
	assert checkout.trial_days_for("t", plan(14)) == 14


def test_a_workspace_only_ever_gets_one(checkout, stub_frappe):
	"""Stripe will start a fresh trial on every new subscription, so cancelling
	and resubscribing would be an unlimited supply of free months. The cheapest
	way to find that out is from a customer who already has."""
	stub_frappe.db.exists = lambda *a, **k: "SUB-0001"
	assert checkout.trial_days_for("t", plan(14)) == 0


def test_any_past_subscription_spends_it(checkout, stub_frappe):
	"""Whatever state it ended in — the filter is the tenant and nothing else.
	A cancelled subscription is exactly the case this is defending against."""
	asked = {}
	stub_frappe.db.exists = lambda doctype, filters=None: asked.update(
		{"doctype": doctype, "filters": filters}
	) or None
	checkout.trial_days_for("t", plan(14))
	assert asked == {"doctype": "Subscription", "filters": {"tenant": "t"}}


def test_the_trial_reaches_stripe_as_its_own_parameter():
	"""`subscription_data.trial_period_days`, so Stripe owns the whole thing:
	trialing until the first charge, active after it, past due if the card
	fails — and every one of those already means something here."""
	source = CHECKOUT.read_text()
	body = next(
		node for node in ast.walk(ast.parse(source))
		if isinstance(node, ast.FunctionDef) and node.name == "start_subscription"
	)
	said = ast.unparse(body)
	assert "trial_period_days" in said
	assert "trial_days_for" in said


# --------------------------------------------------------------------------- #
# What it is worth
# --------------------------------------------------------------------------- #

def test_a_trial_is_granted_its_credits():
	"""Every other grant hangs off `invoice.paid`, and a trial does not reliably
	produce one — Stripe bills nothing until it ends. Left alone, a trialing
	workspace has every screen and no AI, which is the one thing ONEADMIN §9
	calls the actual margin variable and the first thing a trial demonstrates."""
	source = WEBHOOKS.read_text()
	body = next(
		node for node in ast.walk(ast.parse(source))
		if isinstance(node, ast.FunctionDef) and node.name == "handle_subscription_change"
	)
	said = ast.unparse(body)
	assert "grant_period_credits" in said
	assert "Trialing" in said


def test_granting_twice_for_one_period_is_a_no_op():
	"""Which is what makes the line above safe whether or not Stripe also sends
	the invoice — the same guard a replayed webhook already needed."""
	source = WEBHOOKS.read_text()
	body = next(
		node for node in ast.walk(ast.parse(source))
		if isinstance(node, ast.FunctionDef) and node.name == "grant_period_credits"
	)
	assert "last_grant_period_end" in ast.unparse(body)


# --------------------------------------------------------------------------- #
# What it is not
# --------------------------------------------------------------------------- #

def test_a_trial_is_not_on_the_dunning_ladder():
	"""Nobody is chased for money during the fortnight they were told was
	free."""
	source = SWEEP.read_text()
	unpaid = next(
		node for node in ast.walk(ast.parse(source))
		if isinstance(node, ast.Assign)
		and any(getattr(t, "id", None) == "UNPAID" for t in node.targets)
	)
	assert "Trialing" not in ast.literal_eval(unpaid.value)


def test_the_card_is_still_taken_at_signup():
	"""What moves is when the money leaves, not whether there is a card behind
	it — so this opens no abuse surface that signing up does not already open,
	and `signup.py`'s reason for the wall still stands."""
	source = CHECKOUT.read_text()
	body = next(
		node for node in ast.walk(ast.parse(source))
		if isinstance(node, ast.FunctionDef) and node.name == "start_subscription"
	)
	# Still a Checkout session in subscription mode, which is what collects it.
	assert "mode='subscription'" in ast.unparse(body).replace('"', "'")
