"""Talking to Frappe Cloud, and degrading rather than failing when it is down."""

import frappe


def _site_plans(client) -> list[dict]:
	"""Press site plans, deduplicated to the ones worth choosing from.

	Press lists a plan per cluster variant ("USD 5", "USD 5 - Hetzner"), which is
	a long list of near-duplicates in a select. Sorted by price so the cheapest —
	the one a shard default usually wants — is first.
	"""
	# `_degrade` returns (value, error): a form that cannot list site plans should
	# still open, with the field left as it was.
	plans, _error = _degrade(client.site_plans, [])
	rows = [
		{
			"name": p.get("name"),
			"title": p.get("plan_title") or p.get("name"),
			"price_usd": p.get("price_usd"),
			"storage_mb": p.get("max_storage_usage"),
			"database_mb": p.get("max_database_usage"),
		}
		for p in plans
		if p.get("name")
	]
	return sorted(rows, key=lambda r: (r["price_usd"] or 0, r["name"]))


def _site_of(tenant: str) -> tuple:
	"""The Tenant doc and the press site name, or a reason there is none."""
	doc = frappe.get_doc("Tenant", tenant)
	return doc, (doc.press_site or doc.site_name or "")


def _press():
	from oneapp_control.press.client import PressClient

	return PressClient()


def _degrade(fn, default):
	"""Run a press call, or report why it could not run.

	Returns `(value, error)`. A panel that says "Frappe Cloud is unreachable" is
	worth more than a page that fails to load, and far more than one that shows
	an empty list as though the answer were nothing.
	"""
	from oneapp_control.press.client import PressError

	try:
		return fn(), None
	except PressError as e:
		return default, str(e)
	except Exception as e:  # noqa: BLE001 — a panel must not take down the page
		frappe.log_error(title="Press read failed", message=frappe.get_traceback())
		return default, str(e)
