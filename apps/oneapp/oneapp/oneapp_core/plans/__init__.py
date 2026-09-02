"""Import plans this app ships.

A plan is data — steps, field maps, value maps — so a customer arriving off
their own Frappe site is a module in here and no engine code at all. `install`
writes one onto a tenant as `Import Plan` rows; the engine in `importer.py`
reads them and knows nothing about any of it.
"""

import frappe

from oneapp.oneapp_core.plans import rua

PLANS = {"rua": rua}


def install(name: str, source: str) -> str:
	"""Write one shipped plan onto this site, pointed at a source.

	Idempotent: the plan is rewritten from the module every time, **except** the
	watermarks, which belong to what has already crossed over rather than to the
	declaration. Losing them would turn the next incremental run back into a
	full one — so a one-word fix to a field map would silently re-import
	everything.
	"""
	module = PLANS[name]
	title = module.PLAN

	kept = {}
	if frappe.db.exists("Import Plan", title):
		doc = frappe.get_doc("Import Plan", title)
		kept = {s.source_doctype: (s.watermark, s.last_run) for s in doc.steps}
		doc.steps = []
	else:
		doc = frappe.new_doc("Import Plan")
		doc.plan_name = title

	doc.source = source
	doc.space_code = module.SPACE
	doc.is_active = 1

	for step in module.STEPS:
		row = doc.append("steps", {
			"source_doctype": step["source"],
			"target_doctype": step["target"],
			"field_map": frappe.as_json(step["map"]),
			"filters": frappe.as_json(step["filters"]) if step.get("filters") else None,
			"enabled": 1,
			"notes": step.get("why", ""),
		})
		was = kept.get(step["source"])
		if was:
			row.watermark, row.last_run = was

	doc.save()
	frappe.db.commit()
	return doc.name
