"""Credit ledger.

Balance is a sum over Credit Ledger Entry rows, never a stored field, so it
cannot drift out of agreement with history.

Two rules do most of the work:

* Non-rollover grants carry `expires_on`. Balance only counts unexpired rows.
* Spend draws down the soonest-expiring grant first, so a tenant never loses
  purchased credits (which roll over) while free monthly credits sit unused.

Concurrency is handled by reserve/commit. Reading a balance and then spending it
is a race: two parallel AI calls both see 5 credits and both spend 4. Reserving
first, under a row lock on the tenant, makes the check-and-hold atomic.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime


def balance(tenant: str) -> float:
	"""Credits available right now: all entries whose grants have not expired."""
	rows = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(credits), 0)
		FROM `tabCredit Ledger Entry`
		WHERE tenant = %(tenant)s
		  AND (expires_on IS NULL OR expires_on >= CURDATE())
		""",
		{"tenant": tenant},
	)
	return float(rows[0][0] or 0)


def reserved_credits(tenant: str) -> float:
	"""Credits held by open reservations — spoken for, but not yet spent."""
	rows = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(credits_reserved - credits_committed), 0)
		FROM `tabCredit Reservation`
		WHERE tenant = %(tenant)s AND status = 'Open'
		""",
		{"tenant": tenant},
	)
	return float(rows[0][0] or 0)


def available(tenant: str) -> float:
	"""What a new request may actually spend."""
	return balance(tenant) - reserved_credits(tenant)


def post_entry(
	tenant: str,
	entry_type: str,
	credits: float,
	expires_on=None,
	source_doctype: str | None = None,
	source_name: str | None = None,
	reservation: str | None = None,
	remarks: str | None = None,
	consumed_from: str | None = None,
):
	"""Append one immutable ledger row."""
	doc = frappe.get_doc(
		{
			"doctype": "Credit Ledger Entry",
			"tenant": tenant,
			"entry_type": entry_type,
			"credits": credits,
			"expires_on": expires_on,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"reservation": reservation,
			"remarks": remarks,
			"consumed_from": consumed_from,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def reserve(tenant: str, credits: float, purpose: str, ttl_minutes: int = 15):
	"""Hold credits before doing expensive work.

	Locks the Tenant row so a concurrent reserve cannot read the same balance.
	Raises if the tenant cannot cover it — callers should treat that as
	"out of credits", not as an error to retry.
	"""
	if credits <= 0:
		frappe.throw(_("Reserved credits must be positive."))

	# SELECT ... FOR UPDATE. Serialises reservations per tenant for this transaction.
	frappe.db.sql(
		"SELECT name FROM `tabTenant` WHERE name = %s FOR UPDATE", tenant
	)

	if available(tenant) < credits:
		frappe.throw(
			_("Insufficient credits: {0} available, {1} required.").format(
				round(available(tenant), 2), round(credits, 2)
			),
			exc=InsufficientCredits,
		)

	return frappe.get_doc(
		{
			"doctype": "Credit Reservation",
			"tenant": tenant,
			"credits_reserved": credits,
			"purpose": purpose,
			"expires_at": add_to_date(now_datetime(), minutes=ttl_minutes),
			"status": "Open",
		}
	).insert(ignore_permissions=True)


class InsufficientCredits(frappe.ValidationError):
	pass


def grant_for_period(tenant: str, credits: float, period_end, source_name=None):
	"""Post a non-rollover grant that dies at the end of the billing period."""
	if credits <= 0:
		return None

	return post_entry(
		tenant=tenant,
		entry_type="Grant",
		credits=credits,
		expires_on=period_end,
		source_doctype="Subscription",
		source_name=source_name,
		remarks="Plan grant (non-rollover)",
	)


def expire_stale_grants():
	"""Scheduled. Post explicit Expiry rows for grants that have lapsed.

	The balance query already ignores expired grants, so this changes no number.
	It exists so the ledger *reads* as a complete history — a tenant asking
	"where did my credits go" gets an answer instead of a silent gap.
	"""
	grants = frappe.db.sql(
		"""
		SELECT g.name, g.tenant, g.credits, g.expires_on
		FROM `tabCredit Ledger Entry` g
		WHERE g.entry_type = 'Grant'
		  AND g.expires_on IS NOT NULL
		  AND g.expires_on < CURDATE()
		  AND NOT EXISTS (
			SELECT 1 FROM `tabCredit Ledger Entry` e
			WHERE e.entry_type = 'Expiry' AND e.consumed_from = g.name
		  )
		""",
		as_dict=True,
	)

	posted = 0
	for grant in grants:
		spent = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(-credits), 0)
			FROM `tabCredit Ledger Entry`
			WHERE entry_type = 'Spend' AND consumed_from = %s
			""",
			grant.name,
		)[0][0] or 0

		unused = float(grant.credits) - float(spent)
		if unused <= 0:
			continue

		post_entry(
			tenant=grant.tenant,
			entry_type="Expiry",
			credits=-unused,
			consumed_from=grant.name,
			remarks=f"Unused grant expired on {grant.expires_on}",
		)
		posted += 1

	if posted:
		frappe.db.commit()

	return posted


def open_grants(tenant: str) -> list[dict]:
	"""Grants with credits left, soonest-expiring first.

	This ordering is the policy: burn what is about to die before touching
	purchased packs, which never expire.
	"""
	return frappe.db.sql(
		"""
		SELECT
			g.name,
			g.credits,
			g.expires_on,
			g.credits - COALESCE((
				SELECT SUM(-s.credits) FROM `tabCredit Ledger Entry` s
				WHERE s.consumed_from = g.name AND s.entry_type IN ('Spend', 'Expiry')
			), 0) AS remaining
		FROM `tabCredit Ledger Entry` g
		WHERE g.tenant = %(tenant)s
		  AND g.entry_type IN ('Grant', 'Purchase')
		  AND (g.expires_on IS NULL OR g.expires_on >= CURDATE())
		HAVING remaining > 0
		ORDER BY g.expires_on IS NULL, g.expires_on ASC, g.creation ASC
		""",
		{"tenant": tenant},
		as_dict=True,
	)


def spend(tenant: str, credits: float, purpose: str, reservation: str | None = None):
	"""Draw down credits across grants, soonest-expiring first.

	Prefer reserve/commit for anything that can fail partway. This is for
	spends that are already certain.
	"""
	remaining = float(credits)
	entries = []

	for grant in open_grants(tenant):
		if remaining <= 0:
			break

		take = min(remaining, float(grant.remaining))
		entries.append(
			post_entry(
				tenant=tenant,
				entry_type="Spend",
				credits=-take,
				consumed_from=grant.name,
				reservation=reservation,
				remarks=purpose,
			)
		)
		remaining -= take

	if remaining > 0:
		frappe.throw(
			_("Insufficient credits: short by {0}.").format(round(remaining, 2)),
			exc=InsufficientCredits,
		)

	return entries
