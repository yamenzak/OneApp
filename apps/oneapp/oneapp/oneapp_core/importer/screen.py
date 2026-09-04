"""What the import screen shows and the buttons on it.

What the person leaving their old system sees: where it is, what will come
across, and two buttons — rehearse it, then do it. One request rather than
five, because the panel is one picture and five requests is five spinners.
"""

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime


@frappe.whitelist(methods=["GET"])
def console() -> dict:
	"""Everything the import panel draws, in one answer."""
	if not frappe.has_permission("Import Plan", "read"):
		frappe.throw(_("Not yours to see."), frappe.PermissionError)

	sources = frappe.get_all(
		"Import Source",
		fields=["name", "base_url", "api_key", "status", "verified_as",
		        "verified_on", "last_error"],
		order_by="creation asc",
	)

	plans = []
	for plan in frappe.get_all("Import Plan", fields=["name", "source", "is_active"],
	                           order_by="creation asc"):
		doc = frappe.get_doc("Import Plan", plan["name"])
		last = frappe.get_all(
			"Import Run", filters={"plan": plan["name"]},
			fields=["name", "status", "dry_run", "started_on", "finished_on",
			        "total_seen", "total_created", "total_updated", "total_failed"],
			order_by="creation desc", limit=1,
		)
		plans.append({
			**plan,
			"steps": [
				{"source_doctype": s.source_doctype, "target_doctype": s.target_doctype,
				 "enabled": s.enabled, "watermark": s.watermark}
				for s in doc.steps
			],
			"last_run": last[0] if last else None,
			# The whole promise, in one boolean: a plan every step of which has a
			# watermark has been across once, so the next run is a top-up rather
			# than the move.
			"carried": bool(doc.steps) and all(s.watermark for s in doc.steps),
		})

	# What this app ships, this workspace has a space for, and nobody has set
	# up yet. Without it the panel's first state is an empty one — nothing to
	# import and no way to say otherwise — and the whole "one button" claim
	# rests on somebody having installed a plan from a Python shell.
	#
	# Filtered by space, because a shipped plan is one customer's own migration
	# and offering it to every workspace would be offering to fill their books
	# with a stranger's.
	from oneapp.oneapp_core import sync
	from oneapp.oneapp_core.plans import shipped

	installed = {plan["name"] for plan in plans}
	here = {space.get("space_code") for space in sync.state().get("spaces") or []}
	offered = [
		one for one in shipped()
		if one["title"] not in installed and one["space"] in here
	]

	return {"sources": sources, "plans": plans, "shipped": offered}


@frappe.whitelist()
def install_plan(plan: str, source: str) -> str:
	"""Set up one of the plans this app ships, against a connection.

	Its own endpoint rather than a step in `start`: installing writes custom
	fields and seed records, and doing that as a side effect of pressing Run
	would make the first run mean something the second one does not.
	"""
	if not frappe.has_permission("Import Plan", "create"):
		frappe.throw(_("Not yours to set up."), frappe.PermissionError)

	frappe.get_doc("Import Source", source).check_permission("read")

	from oneapp.oneapp_core.plans import PLANS, install

	if plan not in PLANS:
		frappe.throw(_("There is no plan called {0}.").format(plan))

	return install(plan, source)


@frappe.whitelist()
def save_source(name: str, base_url: str, api_key: str, api_secret: str | None = None) -> dict:
	"""The customer's own credentials for their own old system.

	The secret is written only when one is given, so an edit to the URL does not
	need it retyped — and it is never sent back out: `console` returns the key
	and never the secret, which is what a Password field is for.
	"""
	known = frappe.db.exists("Import Source", name)
	doc = frappe.get_doc("Import Source", name) if known else frappe.new_doc("Import Source")
	doc.check_permission("write" if known else "create")

	doc.source_name = name
	doc.base_url = base_url
	doc.api_key = api_key
	if api_secret:
		doc.api_secret = api_secret
	doc.save()
	frappe.db.commit()
	return {"name": doc.name}


@frappe.whitelist(methods=["GET"])
def issues(run: str, limit: int = 50) -> list[dict]:
	"""The rows that would not come across, newest first."""
	frappe.get_doc("Import Run", run).check_permission("read")
	return frappe.get_all(
		"Import Issue",
		filters={"run": run, "status": "Open"},
		fields=["name", "source_doctype", "source_name", "error", "payload"],
		order_by="creation desc",
		limit_page_length=cint(limit),
	)
