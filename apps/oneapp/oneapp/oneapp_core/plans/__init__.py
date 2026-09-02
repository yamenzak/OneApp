"""Import plans this app ships.

A plan is data — steps, field maps, value maps — so a customer arriving off
their own Frappe site is a module in here and no engine code at all. `install`
writes one onto a tenant as `Import Plan` rows; the engine in `importer.py`
reads them and knows nothing about any of it.
"""

import frappe

from oneapp.oneapp_core.plans import rua

PLANS = {"rua": rua}


def shipped() -> list[dict]:
	"""Every plan this app carries, as the console offers them.

	`key` and not the title is what `install` takes: a plan's title is the
	customer's sentence about their own old system and may be edited, and the
	module it came from may not.
	"""
	return [
		{
			"key": key,
			"title": module.PLAN,
			"space": module.SPACE,
			"steps": len(module.STEPS),
			"fields": len(getattr(module, "FIELDS", [])),
		}
		for key, module in PLANS.items()
	]


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

	prepare(module)

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
			"fan_out": frappe.as_json(step["fan_out"]) if step.get("fan_out") else None,
			"enabled": 1,
			"notes": step.get("why", ""),
		})
		was = kept.get(step["source"])
		if was:
			row.watermark, row.last_run = was

	doc.save()
	frappe.db.commit()
	return doc.name


def prepare(module) -> dict:
	"""The fields and records a plan's maps assume, made before it runs.

	A field map naming `custom_retention_percentage` on a site where nothing
	created it is a plan that cannot run — `check` says so, which is better
	than silence and still leaves somebody making nine fields by hand before
	the button does anything. Declaring them beside the maps that use them is
	the only place they cannot drift from.

	Skipped rather than fatal where the target doctype is absent: this app
	installs on benches without ERPNext, and a plan that cannot be *installed*
	there is worse than one that cannot be run there.
	"""
	made = {"fields": 0, "records": 0, "skipped": 0}

	for field in getattr(module, "FIELDS", []):
		if not frappe.db.exists("DocType", field["dt"]):
			made["skipped"] += 1
			continue
		if frappe.db.exists("Custom Field", {"dt": field["dt"],
		                                     "fieldname": field["fieldname"]}):
			continue
		frappe.get_doc({"doctype": "Custom Field", **field}).insert(ignore_permissions=True)
		made["fields"] += 1

	for seed in getattr(module, "SEEDS", []):
		doctype = seed["doctype"]
		if not frappe.db.exists("DocType", doctype):
			made["skipped"] += 1
			continue
		# By the field its doctype is named after, because a seed is written
		# before it has a name — and `autoname` on Item is `item_code`, which
		# is what makes this answerable at all.
		named = frappe.get_meta(doctype).autoname or ""
		key = named.split(":", 1)[1] if named.startswith("field:") else "name"
		if frappe.db.exists(doctype, seed.get(key)):
			continue
		frappe.get_doc(dict(seed)).insert(ignore_permissions=True)
		made["records"] += 1

	frappe.db.commit()
	return made
