import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class SpaceEntitlement(Document):
	def validate(self):
		self.validate_unique()
		if not self.granted_on:
			self.granted_on = now_datetime()

	def validate_unique(self):
		existing = frappe.db.exists(
			"Space Entitlement",
			{"tenant": self.tenant, "app": self.app, "name": ("!=", self.name)},
		)
		if existing:
			frappe.throw(
				_("{0} already has an entitlement for {1}.").format(self.tenant, self.app)
			)
