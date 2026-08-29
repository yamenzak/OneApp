import frappe
from frappe import _
from frappe.model.document import Document


class Subscription(Document):
	def validate(self):
		self.validate_one_active_per_tenant()

	def validate_one_active_per_tenant(self):
		"""A tenant on two active subscriptions would be billed twice and granted
		credits twice."""
		if self.status not in ("Active", "Trialing"):
			return

		clash = frappe.db.exists(
			"Subscription",
			{
				"tenant": self.tenant,
				"status": ("in", ("Active", "Trialing")),
				"name": ("!=", self.name),
			},
		)
		if clash:
			frappe.throw(
				_("{0} already has an active subscription ({1}).").format(self.tenant, clash)
			)

	def on_update(self):
		if self.status in ("Active", "Trialing"):
			frappe.db.set_value(
				"Tenant", self.tenant, {"subscription": self.name, "plan": self.plan}
			)
