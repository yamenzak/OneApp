"""Every site on the Frappe Cloud account, and which workspace owns it.

No table. See `oneapp_control/press/records.py` for why, and for the two rules
that come with it — nothing here is written, and nothing here is joined in SQL.

What this doctype exists for that no table of ours could do: an **orphan**. A
site press is charging us for that no `Tenant` claims does not appear in any
mirror, because a mirror only ever holds what we remembered to put in it. Here
it is a row with an empty `tenant` and a filter an operator can save.
"""

import frappe
from frappe.model.document import Document

from oneapp_control.press import records


def _rows() -> list[dict]:
	"""Press's sites, shaped into this doctype's fields, joined to ours."""
	owners = records.tenants_by_site()
	found = []

	for site in records.sites():
		name = site.get("name") or site.get("site") or ""
		if not name:
			continue
		found.append({
			"name": name,
			"site_name": name,
			"status": site.get("status") or "",
			"tenant": owners.get(name) or "",
			"bench_group": site.get("group") or site.get("release_group") or "",
			"server": site.get("server") or "",
			"cluster": site.get("cluster") or "",
			"plan": site.get("plan") or "",
			"site_created_on": site.get("creation") or "",
			# Frappe's list view reads these off every row it renders, and a
			# virtual row is a dict rather than a document — so they are
			# supplied rather than defaulted, and the ones that mean "when did
			# somebody here last touch it" are the site's own dates.
			"owner": "Administrator",
			"modified": site.get("modified") or site.get("creation") or "",
			"creation": site.get("creation") or "",
			"idx": 0,
			"docstatus": 0,
		})

	return found


class PressSite(Document):
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
			frappe._("Frappe Cloud has no site called {0}.").format(self.name),
			frappe.DoesNotExistError,
		)

	def db_insert(self, *args, **kwargs):
		records.read_only("Press Site")

	def db_update(self, *args, **kwargs):
		records.read_only("Press Site")

	def delete(self, *args, **kwargs):
		records.read_only("Press Site")
