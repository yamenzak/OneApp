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
	# How often this workspace backs itself up to R2, and how long those copies
	# are kept. Captured with everything else so raising the frequency on a plan
	# is an offer to the next customer rather than a change to this one's bill
	# — the storage costs money, and a plan whose retention was cut must not
	# quietly start deleting a subscriber's backups.
	"backups_per_day",
	"backup_retention_days",
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


def with_addons(terms: dict, subscription: str | None) -> dict:
	"""The terms, plus whatever add-ons the subscription is paying for.

	Added here rather than by each caller, because "what is this workspace
	allowed" has exactly one answer and every reader of it — the sync payload,
	the quota properties, the plan page, the credit grant — has to get the same
	one. A caller that forgot to add would silently under-quota somebody who is
	paying.

	The GB come off the captured rows, not off the `Add-on` catalogue. Editing
	an add-on changes what the next purchase buys, never what somebody already
	holds, exactly as editing a plan does not move an existing subscriber.
	"""
	if not subscription:
		return terms

	rows = frappe.get_all(
		"Subscription Add-on",
		filters={"parent": subscription, "parenttype": "Subscription"},
		fields=["kind", "quantity", "unit_gb"],
	)
	if not rows:
		return terms

	from oneapp_control.billing import addons

	found = dict(terms)
	for field, extra in addons.quota_for(rows).items():
		if extra:
			found[field] = (found.get(field) or 0) + extra
	return found


def for_subscription(subscription) -> dict:
	"""The terms one subscription is on, add-ons included.

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
		terms = {field: doc.get(field) for field in TERMS}
	else:
		plan = frappe.db.get_value("Plan", doc.plan, TERMS, as_dict=True) or {}
		terms = {field: plan.get(field) for field in TERMS}

	return with_addons(terms, doc.name)


def for_tenant(tenant) -> dict:
	"""The terms in force for a workspace, add-ons included.

	The subscription's captured terms when there are any; the plan as it stands
	otherwise. The fallback is not a nicety — a tenant an operator created by
	hand, one still in trial, and every subscription sold before terms were
	captured all have no snapshot, and all of them still need a quota.

	What is *not* here is `Tenant.extra_storage_gb` and its sibling. Those are an
	operator's grant rather than something bought, and they are added by the
	Tenant's own quota properties — so this stays "what the subscription is
	paying for", which is what a plan change and a proration have to reason
	about.
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
			return with_addons(
				{field: captured.get(field) for field in TERMS}, doc.subscription
			)

	if not doc.plan:
		return {field: None for field in TERMS}

	terms = frappe.db.get_value("Plan", doc.plan, TERMS, as_dict=True) or {}
	return with_addons({field: terms.get(field) for field in TERMS}, doc.subscription)


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
