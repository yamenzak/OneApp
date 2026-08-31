"""Plans, prices and the promise that a plan edit is not retroactive.

Two rules hold this together, and both are the kind that look fine right up to
the moment they are broken by a one-line change somewhere else:

  1. Stripe owns the money. A Price is immutable in amount and currency, so
     changing what a plan costs mints a new Price and archives the old — which
     is also exactly what leaves existing subscribers on the price they bought.

  2. We own the quotas, and they are captured when a subscription is sold.
     Reading them live from the Plan doctype made every price-sheet edit
     retroactive: someone who bought 50GB could wake up with 20GB.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/oneapp_control/oneapp_control"

PLANS = APP / "billing/plans.py"
QUOTAS = APP / "billing/quotas.py"
CHECKOUT = APP / "billing/checkout.py"
WEBHOOKS = APP / "billing/webhooks.py"
STRIPE = APP / "billing/stripe_client.py"
TENANT = APP / "control_plane/doctype/tenant/tenant.py"
PLAN_DOC = APP / "control_plane/doctype/plan/plan.py"


def source(path: Path) -> str:
	return path.read_text()


def function(path: Path, name: str) -> str:
	tree = ast.parse(source(path))
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name == name:
			return ast.get_source_segment(source(path), node)
	raise AssertionError(f"{name} is missing from {path.name}")


# --------------------------------------------------------------------------- #
# Prices are minted, never edited
# --------------------------------------------------------------------------- #

def test_a_price_change_mints_a_new_price_rather_than_editing_one():
	"""Stripe rejects an edit to `unit_amount`, and even if it did not, editing
	would reprice everyone already subscribed."""
	body = function(PLANS, "_ensure_price")
	assert "create_price" in body
	assert "archive_price" in body
	assert not re.search(r"update_price\b", source(PLANS)), (
		"there is no such thing as updating a price"
	)


def test_the_client_offers_no_way_to_change_a_price_in_place():
	client = source(STRIPE)
	assert "def create_price" in client
	assert "def archive_price" in client
	assert "def update_price" not in client


def test_archiving_is_explained_as_the_thing_that_grandfathers():
	"""A future reader deleting `archive_price` because "nothing reads it" is
	the failure this comment exists to prevent."""
	assert "existing subscriptions" in function(STRIPE, "archive_price").lower()


def test_every_price_is_kept_not_just_the_current_one():
	"""The reverse lookup a webhook needs: Stripe names a price, and only this
	table can say which plan that was."""
	plan_price = ROOT / (
		"apps/oneapp_control/oneapp_control/control_plane/doctype/plan_price/plan_price.json"
	)
	assert plan_price.exists(), "the Plan Price table is gone"

	plan = ROOT / "apps/oneapp_control/oneapp_control/control_plane/doctype/plan/plan.json"
	assert '"options": "Plan Price"' in plan.read_text()

	assert "def plan_for_price" in source(PLANS)


def test_the_price_ids_are_not_typed_by_hand():
	"""Dual entry is how a page advertises one number and the card is charged
	another."""
	plan = ROOT / "apps/oneapp_control/oneapp_control/control_plane/doctype/plan/plan.json"
	fields = {
		f["fieldname"]: f
		for f in __import__("json").loads(plan.read_text())["fields"]
	}
	for name in ("stripe_product_id", "stripe_price_id_monthly", "stripe_price_id_yearly"):
		assert fields[name].get("read_only"), f"{name} is editable again"

	# The operator's form is the generic record form now, over this doctype —
	# there is no hand-written PlansSettings.vue to keep in step. So `read_only`
	# above is what makes the field uneditable, and this is the other half: the
	# Plans screen does not put a Stripe id in front of somebody as if it were
	# theirs to set.
	import ast as _ast

	operator = (
		ROOT / "apps/oneapp_control/oneapp_control/entitlements/operator.py"
	).read_text()
	screens = next(
		_ast.literal_eval(node.value)
		for node in _ast.walk(_ast.parse(operator))
		if isinstance(node, _ast.Assign) and getattr(node.targets[0], "id", "") == "SCREENS"
	)
	columns = next(row[4] for row in screens if row[3] == "Plan")
	assert "stripe_price_id" not in columns, "the Plans screen advertises a price id"
	assert "stripe_product_id" not in columns


def test_syncing_cannot_stop_a_plan_being_saved():
	"""Stripe being unreachable is temporary. A plan an operator cannot edit is
	not."""
	body = function(PLANS, "sync")
	assert "except Exception" in body
	assert "sync_error" in body

	# The prose says "never raises"; this is the part a compiler can check.
	tree = ast.parse(body.replace("\t", "    ", 1) if body.startswith("\t") else body)
	raises = [n for n in ast.walk(tree) if isinstance(n, ast.Raise)]
	assert not raises, "sync raises, so a Stripe outage stops a plan being edited"


def test_a_control_plane_without_stripe_can_still_draft_plans():
	assert "_configured()" in function(PLANS, "sync")


def test_the_sync_runs_inside_the_save_it_belongs_to():
	"""In validate, not on_update: a second write can half-apply, and the child
	rows and the ids belong to the same save the operator asked for."""
	body = source(PLAN_DOC)
	assert "def validate" in body
	assert "plans.sync(self)" in body
	assert "def on_update" not in body


# --------------------------------------------------------------------------- #
# Quotas are captured, not read live
# --------------------------------------------------------------------------- #

QUOTA_FIELDS = (
	"storage_gb",
	"database_gb",
	"max_users",
	"monthly_credit_grant",
	"background_workers",
	"press_site_plan",
)


def test_the_terms_a_subscription_captures_are_the_terms_a_plan_sells():
	"""Field-for-field, so nothing is reinterpreted on the way across."""
	terms = re.search(r"TERMS = \(\n(.*?)\)", source(QUOTAS), re.S).group(1)
	captured = set(re.findall(r'"(\w+)"', terms))
	assert captured == set(QUOTA_FIELDS), captured

	import json

	for doctype in ("plan", "subscription"):
		path = APP / f"control_plane/doctype/{doctype}/{doctype}.json"
		fields = {f["fieldname"] for f in json.loads(path.read_text())["fields"]}
		missing = set(QUOTA_FIELDS) - fields
		assert not missing, f"{doctype} cannot hold {missing}"


def test_nothing_reads_a_plan_quota_to_answer_what_a_tenant_is_allowed():
	"""One module decides between the captured terms and the plan.

	The catalogue still reads Plan rows — that is what a price sheet is — but
	anything answering "what is *this workspace* allowed" has to go through
	quotas.py, or the snapshot is a decoration.
	"""
	allowed = {
		# The catalogue: what a plan offers, not what a tenant holds.
		"api/customer.py",
		"api/signup.py",
		# The snapshot itself, and the two places that take one.
		"billing/quotas.py",
		"billing/plans.py",
		"billing/checkout.py",
		"patches/capture_plan_terms.py",
	}

	pattern = re.compile(
		r'get_value\(\s*"Plan"[^)]*?(?:' + "|".join(QUOTA_FIELDS) + r")", re.S
	)
	offenders = []
	for path in sorted(APP.rglob("*.py")):
		rel = path.relative_to(APP).as_posix()
		if rel in allowed:
			continue
		if pattern.search(path.read_text()):
			offenders.append(rel)
	assert not offenders, (
		"these read a plan quota directly instead of the terms in force: "
		+ ", ".join(offenders)
	)


def test_the_tenants_own_quota_properties_read_the_captured_terms():
	body = source(TENANT)
	assert "quotas.for_tenant(self)" in body
	for prop in ("storage_quota_bytes", "database_quota_bytes", "max_users", "background_workers"):
		assert "self.terms" in function(TENANT, prop), prop


def test_the_credit_grant_is_the_one_that_was_bought():
	"""A plan whose grant was raised does not retroactively owe every existing
	customer the difference; one whose grant was cut does not take it away."""
	body = function(WEBHOOKS, "grant_period_credits")
	assert "quotas.for_subscription(subscription)" in body
	assert "terms_captured_on" in function(QUOTAS, "for_subscription")


def test_the_site_plan_is_grandfathered_too():
	"""CPU and memory are part of what was bought, same as storage."""
	steps = source(APP / "provisioning/steps.py")
	assert 'tenant.terms.get("press_site_plan")' in steps
	assert 'get_value("Plan", tenant.plan, "press_site_plan")' not in steps


def test_terms_are_captured_the_moment_a_subscription_exists():
	assert "quotas.capture" in function(WEBHOOKS, "ensure_subscription")


def test_a_subscription_with_no_snapshot_still_has_a_quota():
	"""Trials, operator-made tenants and everything sold before the snapshot."""
	body = function(QUOTAS, "for_tenant")
	assert "terms_captured_on" in body
	assert 'get_value("Plan"' in body


def test_moving_someone_onto_new_terms_is_deliberate():
	assert "def adopt_current_terms" in source(QUOTAS)


def test_existing_subscriptions_are_backfilled():
	patch = APP / "patches/capture_plan_terms.py"
	assert patch.exists()
	assert "oneapp_control.patches.capture_plan_terms" in (APP / "patches.txt").read_text()


def test_reducing_a_plan_says_who_it_does_and_does_not_affect():
	"""Surprising in both directions the first time, so the message names both."""
	body = function(PLAN_DOC, "warn_on_quota_reduction")
	assert "msgprint" in body
	assert "new subscriptions" in body


# --------------------------------------------------------------------------- #
# Changing plan
# --------------------------------------------------------------------------- #

def test_a_retired_plan_cannot_be_sold_even_by_code():
	"""A plan code is not a secret. "Not offered any more" has to mean something
	at the point of sale, not only in the list."""
	body = function(CHECKOUT, "_sellable")
	assert "is_active" in body

	for entry in ("start_subscription", "change_plan", "start_signup"):
		assert "_sellable(" in function(CHECKOUT, entry), entry


def test_a_plan_change_applies_immediately_at_both_ends():
	"""The webhook is the durable path, but it may be seconds away or, on a
	control plane whose webhook is not configured yet, never."""
	body = function(CHECKOUT, "change_plan")
	assert "update_subscription" in body
	assert "apply_plan(" in body
	assert "proration_behavior" in body


def test_applying_a_plan_twice_does_it_once():
	"""It arrives twice by design: once from the call, once from the webhook."""
	body = function(CHECKOUT, "apply_plan")
	assert "unchanged" in body and "return" in body


def test_a_plan_change_reaches_frappe_cloud_when_the_site_plan_moves():
	body = function(CHECKOUT, "apply_plan")
	assert "Change Plan" in body
	assert "press_site_plan" in body
	assert "runner.enqueue" in body


def test_a_repricing_we_did_not_initiate_is_followed_home():
	"""Coupons, dashboard edits, an operator swapping the item by hand. Without
	this an upgrade billed at the new price and left the old storage and seats.
	"""
	body = function(WEBHOOKS, "_reconcile_plan")
	assert "plan_for_price" in body
	assert "apply_plan" in body
	assert "_reconcile_plan" in function(WEBHOOKS, "handle_subscription_change")


def test_the_price_decides_the_plan_not_the_metadata():
	"""Nobody updates metadata when they edit a subscription in the dashboard."""
	body = function(WEBHOOKS, "_reconcile_plan")
	assert '("price") or {}).get("id")' in body


def test_an_ambiguous_subscription_is_left_alone_rather_than_guessed_at():
	"""Repricing a workspace off the wrong line item is worse than a stale record
	an operator can see."""
	assert "len(items) != 1" in function(WEBHOOKS, "_reconcile_plan")
	assert "len(items) != 1" in function(CHECKOUT, "change_plan")


def test_a_price_we_did_not_mint_is_reported_rather_than_swallowed():
	"""It means someone is paying for something we cannot describe."""
	assert "log_error" in function(WEBHOOKS, "_reconcile_plan")
