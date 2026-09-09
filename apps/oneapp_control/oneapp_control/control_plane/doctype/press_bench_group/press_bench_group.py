"""The bench groups sites are created on, and what each one carries.

No table — `oneapp_control/press/records.py` is the argument. A Shard names one
of these and nothing else about it: the version it builds, the apps it carries
and the clusters it can deploy into are press's answers, and the copies of them
we used to keep were stale the first time anybody upgraded a bench.

The apps are fetched when a record is opened rather than when the list is drawn.
`bench.all` gives a count; the list itself is one call per group, and a listing
of forty groups would be forty calls to fill a column nobody reads at a glance.
"""

import frappe
from frappe.model.document import Document

from oneapp_control.press import records
from oneapp_control.press.client import PressError, get_client


def _rows() -> list[dict]:
	found = []
	for group in records.groups():
		name = group.get("name") or ""
		if not name:
			continue
		found.append({
			"name": name,
			"group_name": name,
			"title": group.get("title") or name,
			"version": group.get("version") or "",
			"apps": "",
			"owner": "Administrator",
			"modified": group.get("modified") or group.get("creation") or "",
			"creation": group.get("creation") or "",
			"idx": 0,
			"docstatus": 0,
		})
	return found


def _apps(name: str) -> str:
	try:
		apps = get_client().group_apps(name)
	except PressError:
		frappe.log_error(
			title=f"Could not read the apps on {name}", message=frappe.get_traceback()
		)
		return ""
	return ", ".join(
		str(app.get("app") or app.get("name") or "") for app in apps if app
	)


class PressBenchGroup(Document):
	@staticmethod
	def get_list(**kwargs):
		return records.listing(_rows(), kwargs)

	@staticmethod
	def get_count(**kwargs):
		return records.counted(_rows(), kwargs)

	@staticmethod
	def get_stats(**kwargs):
		return {}

	def load_from_db(self):
		for row in _rows():
			if row["name"] == self.name:
				super(Document, self).__init__({**row, "apps": _apps(self.name)})
				return
		frappe.throw(
			frappe._("Frappe Cloud has no bench group called {0}.").format(self.name),
			frappe.DoesNotExistError,
		)

	def db_insert(self, *args, **kwargs):
		records.read_only("Press Bench Group")

	def db_update(self, *args, **kwargs):
		records.read_only("Press Bench Group")

	def delete(self, *args, **kwargs):
		records.read_only("Press Bench Group")
