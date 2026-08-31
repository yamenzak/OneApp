"""What a workspace is actually allowed, and where that number comes from.

Quotas used to be read live from the Plan doctype. That made every price-sheet
edit retroactive: tidying a plan re-quotaed everyone already on it, and someone
who bought 50GB could wake up with 20GB without having agreed to anything.
Stripe grandfathers the *price* by leaving the old Price on the subscription;
this does the same for everything that price bought.

So the terms are copied onto the Subscription when it is sold, and enforcement
reads the copy. Editing a Plan then changes what new customers get, and an
operator moves an existing subscription onto new terms deliberately, with
`adopt_current_terms`.

This module is the only thing that decides which of the two to read. Nothing
else should reach for `Plan.storage_gb` to answer "what is this tenant allowed"
— `tests/test_quotas.py` checks that it doesn't.
"""

import frappe
from frappe.utils import now_datetime

# The terms a plan sells. Same names on Plan and on Subscription, so the copy is
# field-for-field and nothing is reinterpreted on the way across.
TERMS = (
	"storage_gb",
	"database_gb",
	"max_users",
	"monthly_credit_grant",
	"background_workers",
	"press_site_plan",
)


def capture(subscription, plan: str | None = None) -> dict:
	"""Copy a plan's terms onto a subscription. Returns what was captured.

	Called when a subscription is created and again when it changes plan. Writes
	with `db_set` so it is safe from a webhook handler, where the document may
	already be mid-flight.
	"""
	plan = plan or subscription.plan
	terms = frappe.db.get_value("Plan", plan, TERMS, as_dict=True) or {}

	values = {field: terms.get(field) for field in TERMS}
	values["terms_captured_on"] = now_datetime()

	for field, value in values.items():
		subscription.db_set(field, value)

	return values


def for_subscription(subscription) -> dict:
	"""The terms one subscription is on.

	Same rule as `for_tenant`, keyed the other way: a subscription that predates
	the snapshot still reads its plan, because "no terms" is not the same as
	"no allowance".
	"""
	doc = (
		subscription
		if hasattr(subscription, "get")
		else frappe.get_doc("Subscription", subscription)
	)
	if doc.get("terms_captured_on"):
		return {field: doc.get(field) for field in TERMS}

	terms = frappe.db.get_value("Plan", doc.plan, TERMS, as_dict=True) or {}
	return {field: terms.get(field) for field in TERMS}


def for_tenant(tenant) -> dict:
	"""The terms in force for a workspace.

	The subscription's captured terms when there are any; the plan as it stands
	otherwise. The fallback is not a nicety — a tenant an operator created by
	hand, one still in trial, and every subscription sold before terms were
	captured all have no snapshot, and all of them still need a quota.
	"""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)

	if doc.subscription:
		captured = frappe.db.get_value(
			"Subscription",
			doc.subscription,
			("terms_captured_on", *TERMS),
			as_dict=True,
		)
		if captured and captured.get("terms_captured_on"):
			return {field: captured.get(field) for field in TERMS}

	if not doc.plan:
		return {field: None for field in TERMS}

	terms = frappe.db.get_value("Plan", doc.plan, TERMS, as_dict=True) or {}
	return {field: terms.get(field) for field in TERMS}


def adopt_current_terms(subscription) -> dict:
	"""Move a subscription onto its plan's terms as they stand now.

	The deliberate half of grandfathering: an operator can hand someone the
	newer, larger plan without waiting for them to re-subscribe. Deliberate
	because the automatic version is the bug this module exists to prevent.
	"""
	doc = subscription if hasattr(subscription, "get") else frappe.get_doc("Subscription", subscription)
	return capture(doc)


# --------------------------------------------------------------------------- #
# Fit
# --------------------------------------------------------------------------- #

GB = 1024**3


def blockers(tenant, plan_terms: dict) -> list[str]:
	"""Which of a plan's limits this workspace is already past.

	Shared by the plan catalogue and by the change itself, so the page cannot
	offer a plan the switch would then refuse — and, more importantly, so the
	switch cannot accept one the page would have refused. Stripe's own billing
	portal knows none of this, which is why plan changes do not go through it.
	"""
	doc = tenant if hasattr(tenant, "get") else frappe.get_doc("Tenant", tenant)

	# What the plan gives, plus what the workspace holds on top of it. The two
	# were not added together here, while `Tenant.storage_quota_bytes` did add
	# them — so a workspace that had been granted extra storage was refused a
	# plan change it would comfortably have fitted, and the message named a
	# limit it was not actually past.
	#
	# Only the grants, not the add-ons: an add-on is bought against the
	# subscription and moves with it, so counting it toward a *different* plan's
	# fit would let somebody downgrade into a plan the add-on is paying to
	# escape.
	storage_cap = ((plan_terms.get("storage_gb") or 0) + (doc.extra_storage_gb or 0)) * GB
	database_cap = ((plan_terms.get("database_gb") or 0) + (doc.extra_database_gb or 0)) * GB
	seats = 1 + len(doc.members or [])

	checks = (
		("storage", doc.storage_used_bytes or 0, storage_cap),
		("database", doc.database_used_bytes or 0, database_cap),
		("seats", seats, plan_terms.get("max_users") or 0),
	)
	return [label for label, used, cap in checks if cap and used > cap]
