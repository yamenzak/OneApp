"""Regions come from Frappe Cloud's clusters, not from a table somebody keeps.

A `Region` is what a customer picks at signup, and underneath it is a press
cluster. Two facts, and only one of them is ours: the label a customer reads
and the country that drives storage jurisdiction and the chart of accounts are
decisions; *which clusters exist* is press's answer and was being retyped.

Keeping the two in step by hand has one failure mode and it is silent — a
cluster press added is a region nobody can be placed in, and a region naming a
cluster press retired is a shard that validates and then cannot create a site.

So: one Region per cluster press reports, created inactive with the cluster's
own name as a placeholder label. An operator turns it on and names it properly
— those are the two decisions — and everything else follows.

**Never deletes and never overwrites.** A region a customer already chose is a
region tenants are sitting in, and press dropping a cluster from a bench
group's list is not evidence it is gone. Rows that stop appearing are left
alone and reported by `attention`, which is where a human should decide.
"""

import frappe

from oneapp_control.press import records

#: What a new region is called before anybody names it. Deliberately ugly: a
#: region still called `eu-central-1` on the signup form is a region nobody
#: finished setting up, and it should look like it.
PLACEHOLDER = "{0} (unnamed)"


def clusters() -> set[str]:
	"""Every cluster any of our bench groups can deploy into.

	Asked per group rather than globally because that is the question press
	answers — `press.api.bench.regions` — and because a cluster no bench group
	reaches is a cluster we cannot place a tenant in whatever press thinks.
	"""
	found: set[str] = set()
	for group in records.groups():
		name = group.get("name")
		if not name:
			continue
		for row in records.regions_of(name):
			cluster = row.get("name") or row.get("cluster")
			if cluster:
				found.add(str(cluster))
	return found


def sync_from_press() -> dict:
	"""Create a Region for any cluster that has none. Returns what it did.

	Inactive on creation, so a half-set-up region cannot be offered at signup
	before somebody has said which country it is in — which the workspace's
	books depend on.
	"""
	if not records.groups():
		return {"ok": False, "reason": "press has nothing to say"}

	known = {
		row["press_cluster"]: row["name"]
		for row in frappe.get_all(
			"Region", fields=["name", "press_cluster"], filters={"press_cluster": ("is", "set")}
		)
	}

	made = []
	for cluster in sorted(clusters()):
		if cluster in known:
			continue
		code = frappe.scrub(cluster).replace("_", "-")
		if frappe.db.exists("Region", code):
			# A region somebody made by hand before this existed. Adopt it
			# rather than making a second one beside it.
			frappe.db.set_value("Region", code, "press_cluster", cluster,
			                    update_modified=False)
			continue
		frappe.get_doc({
			"doctype": "Region",
			"region_code": code,
			"region_name": PLACEHOLDER.format(cluster),
			"press_cluster": cluster,
			# Country is required and is not press's to answer, so a new region
			# is inactive until somebody says. `regions_with_capacity` already
			# filters on `is_active`, so nothing offers it in the meantime.
			"country": frappe.db.get_single_value("System Settings", "country") or "Germany",
			"is_active": 0,
			"description": "Created from the Frappe Cloud cluster of the same "
			               "name. Name it, set its country, then turn it on.",
		}).insert(ignore_permissions=True)
		made.append(code)

	if made:
		frappe.db.commit()
	return {"ok": True, "created": made, "clusters": len(clusters())}


def scheduled_run() -> dict:
	"""Daily. Cheap — `records` caches press, so this is usually zero calls."""
	try:
		return sync_from_press()
	except Exception:
		frappe.log_error(
			title="Region sync from press failed", message=frappe.get_traceback()
		)
		return {"ok": False}


def unbacked() -> list[str]:
	"""Active regions whose cluster press no longer offers.

	Read by `attention`. Not acted on here: tenants live in these, and the
	answer is a migration rather than a flag flip.
	"""
	live = clusters()
	if not live:
		return []
	return [
		row["name"]
		for row in frappe.get_all(
			"Region",
			filters={"is_active": 1, "press_cluster": ("is", "set")},
			fields=["name", "press_cluster"],
		)
		if row["press_cluster"] not in live
	]
