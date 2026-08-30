"""Checking what we charged against what Cloudflare says the call cost.

AI Gateway does not return a cost on the response — no header carries one. It
writes one into its own log, which is retrievable by the `cf-aig-log-id` that
does come back, and which Cloudflare itself describes as an estimate from token
counts. So neither figure is automatically right:

  * **Ours** is the exact usage the model reported, priced against the rates the
    provider published. It is what we bill on.
  * **Cloudflare's** is what the account will actually be invoiced under Unified
    Billing, whatever we think.

This job puts them side by side. Where they agree, nothing happens and the row
is marked settled. Where they disagree, the gap is recorded on the usage record
and — beyond a tolerance that absorbs rounding — an adjustment is posted, so the
ledger converges on the money that actually moved instead of on our arithmetic.

Written as a comparison rather than a replacement on purpose: silently trusting
the gateway's number would put an estimate on a customer's invoice, which is the
one thing this whole design exists to avoid.
"""

import frappe
import requests
from frappe.utils import add_to_date, get_datetime, now_datetime

from oneapp_control.ai import catalogue, pricing
from oneapp_control.credits import ledger

TIMEOUT = 60

# Gateway logs are written after the response is sent. Reconciling a call that
# finished a moment ago would just find nothing.
SETTLE_AFTER_MINUTES = 10

# Below this the two figures are the same number rounded differently. Posting a
# hundredth-of-a-credit adjustment costs a ledger row and answers nothing.
TOLERANCE_CREDITS = 0.05

# How far above our own figure the gateway may go before we stop believing it.
#
# A small gap is a stale rate — we synced a price a day after it changed — and
# collecting it is right. A large one is not a price difference, it is a
# disagreement about what happened: a model missing from Cloudflare's cost table,
# a rate we mis-parsed, a bug at either end. Re-billing a customer for a call
# they already made, at a number described by its own vendor as an estimate, is
# not something to do automatically. Those are flagged for a person instead.
BELIEVABLE_MULTIPLE = 1.25
BELIEVABLE_CREDITS = 5.0

BATCH = 200


def _logs(account_id: str, gateway: str, token: str, since) -> dict[str, dict]:
	"""Every gateway log since `since`, indexed by id."""
	found: dict[str, dict] = {}
	page = 1

	while page <= 10:
		response = requests.get(
			f"{catalogue.CF_API}/accounts/{account_id}/ai-gateway/gateways/{gateway}/logs",
			headers={"Authorization": f"Bearer {token}"},
			params={
				"per_page": 100,
				"page": page,
				"filters": frappe.as_json([
					{"key": "created_at", "operator": "ge", "value": [str(since)]}
				]),
			},
			timeout=TIMEOUT,
		)
		if response.status_code != 200:
			raise catalogue.SyncError(
				f"gateway logs: HTTP {response.status_code} {response.text[:200]}")

		batch = response.json().get("result") or []
		for row in batch:
			if row.get("id"):
				found[row["id"]] = row
		if len(batch) < 100:
			break
		page += 1

	return found


def pending(limit: int = BATCH) -> list[dict]:
	return frappe.get_all(
		"AI Usage Record",
		filters={
			"reconciled_on": ["is", "not set"],
			"gateway_log_id": ["is", "set"],
			"creation": ["<", add_to_date(now_datetime(), minutes=-SETTLE_AFTER_MINUTES)],
		},
		fields=["name", "tenant", "model", "credits_charged", "cost_usd",
		        "markup", "gateway_log_id", "feature"],
		order_by="creation asc",
		limit=limit,
	)


def believable(charged: float, gateway_credits: float) -> bool:
	"""Whether a gap is a price difference or a disagreement about what happened.

	Asymmetric on purpose. Giving credits back is always safe — a cache hit
	costs the provider nothing and the gateway logs zero, and a refund needs no
	further justification. Taking more is not, so it has to be within reach of
	the figure we measured.
	"""
	if gateway_credits <= charged:
		return True
	return (gateway_credits <= charged * BELIEVABLE_MULTIPLE
	        or gateway_credits - charged <= BELIEVABLE_CREDITS)


def _adjust(record: dict, gateway_credits: float) -> tuple[str | None, str]:
	"""Post the difference, in the direction the money actually went."""
	charged = float(record["credits_charged"] or 0)
	delta = round(gateway_credits - charged, 2)

	if abs(delta) < TOLERANCE_CREDITS:
		return None, "agrees with the gateway"

	if not believable(charged, gateway_credits):
		frappe.log_error(
			title="AI gateway cost is far from ours",
			message=(
				f"{record['name']} ({record['model']}): we charged {charged} credits "
				f"from the usage the model reported; the gateway's log says "
				f"{gateway_credits}. Nothing was adjusted. Check the model's rates "
				f"in the catalogue."
			),
		)
		return None, (
			f"NOT adjusted: the gateway says {gateway_credits} credits against our "
			f"{charged}. That gap is a rate to check, not a price to re-bill."
		)

	# Spend is negative in the ledger. Charging too little means we owe another
	# debit; charging too much means giving credits back.
	entry = ledger.post_entry(
		tenant=record["tenant"],
		entry_type="Adjustment",
		credits=-delta,
		source_doctype="AI Usage Record",
		source_name=record["name"],
		remarks=(
			f"AI Gateway log {record['gateway_log_id']} priced this call at "
			f"{gateway_credits} credits; we charged {charged}."
		),
	)
	return entry.name, f"gateway {gateway_credits} credits, charged {charged}"


def run(limit: int = BATCH) -> dict:
	"""Compare a batch of recent calls against the gateway's own log."""
	conf = catalogue.settings()
	account_id = conf.cf_account_id
	gateway = conf.ai_gateway or "oneapp"
	token = conf.get_password("cf_api_token", raise_exception=False)

	rows = pending(limit)
	if not rows:
		return {"checked": 0, "matched": 0, "adjusted": 0, "flagged": 0, "missing": 0}

	if not (account_id and token):
		return {"checked": 0, "error": "Cloudflare account id and API token are not set."}

	oldest = min(get_datetime(frappe.db.get_value("AI Usage Record", r["name"], "creation"))
	             for r in rows)
	logs = _logs(account_id, gateway, token, add_to_date(oldest, minutes=-5))

	report = {"checked": len(rows), "matched": 0, "adjusted": 0, "flagged": 0,
	          "missing": 0}

	for record in rows:
		log = logs.get(record["gateway_log_id"])
		if not log:
			# Not yet written, or older than the window. Left unreconciled so the
			# next run picks it up rather than being marked settled on silence.
			report["missing"] += 1
			continue

		gateway_usd = float(log.get("cost") or 0)
		markup = float(record["markup"] or 0) or 1.0
		gateway_credits = pricing.to_credits(gateway_usd, markup)

		adjustment, note = _adjust(record, gateway_credits)
		if log.get("cached"):
			# A cache hit costs the provider nothing and the gateway logs zero.
			# We charged for the tokens the response reported, which is wrong,
			# and the refund above has already put it right.
			note = f"served from the gateway cache — {note}"

		frappe.db.set_value("AI Usage Record", record["name"], {
			"reconciled_on": now_datetime(),
			"gateway_cost_usd": gateway_usd,
			"cached": 1 if log.get("cached") else 0,
			"adjustment": adjustment,
			"recon_note": note,
		})

		if adjustment:
			report["adjusted"] += 1
		elif note.startswith("NOT adjusted"):
			report["flagged"] += 1
		else:
			report["matched"] += 1

	frappe.db.commit()
	return report


def scheduled_run():
	"""Hourly, from hooks. Never raises: an unreachable gateway leaves rows
	unreconciled, which is exactly what the next run is for."""
	try:
		run()
	except Exception:
		frappe.log_error(title="AI reconciliation failed", message=frappe.get_traceback())
