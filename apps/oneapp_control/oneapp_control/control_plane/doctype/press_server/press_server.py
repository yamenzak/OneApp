"""The servers on the account, and the cluster each one sits in.

No table — `oneapp_control/press/records.py` is the argument. This is what a
Region is a name over: press already knows where a server is, so a table of ours
saying the same thing is a second answer waiting to disagree with the first.
"""

import frappe
from frappe.model.document import Document

from oneapp_control.press import records


def _rows() -> list[dict]:
	found = []
	for server in records.servers():
		name = server.get("name") or ""
		if not name:
			continue
		found.append({
			"name": name,
			"server_name": name,
			"title": server.get("title") or name,
			"status": server.get("status") or "",
			"cluster": server.get("cluster") or "",
			"plan": server.get("plan") or "",
			"owner": "Administrator",
			"modified": server.get("modified") or server.get("creation") or "",
			"creation": server.get("creation") or "",
			"idx": 0,
			"docstatus": 0,
		})
	return found


class PressServer(Document):
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
				super(Document, self).__init__(row)
				return
		frappe.throw(
			frappe._("Frappe Cloud has no server called {0}.").format(self.name),
			frappe.DoesNotExistError,
		)

	def db_insert(self, *args, **kwargs):
		records.read_only("Press Server")

	def db_update(self, *args, **kwargs):
		records.read_only("Press Server")

	def delete(self, *args, **kwargs):
		records.read_only("Press Server")
