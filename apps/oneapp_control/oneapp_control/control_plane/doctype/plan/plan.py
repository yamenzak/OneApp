import frappe
from frappe import _
from frappe.model.document import Document

from oneapp_control.billing import plans


class Plan(Document):
	def validate(self):
		self.validate_price()
		# In validate, not on_update: the product id, the price ids and the new
		# Plan Price rows then belong to the same write the operator asked for,
		# rather than a second save that could half-apply. Never raises — see
		# billing/plans.py.
		plans.sync(self)

	def validate_price(self):
		if (self.price_monthly or 0) < 0 or (self.price_yearly or 0) < 0:
			frappe.throw(_("A plan cannot cost a negative amount."))

		if not self.is_new():
			self.warn_on_quota_reduction()

	def warn_on_quota_reduction(self):
		"""Say what a reduction will and will not do.

		It will not change anyone already subscribed: enforcement reads the terms
		captured on their subscription, not this document. That is deliberate, and
		it is also surprising the first time — so the message names both halves
		rather than letting an operator assume either one.
		"""
		before = self.get_doc_before_save()
		if not before:
			return

		reduced = [
			field
			for field in ("storage_gb", "database_gb", "max_users", "background_workers",
			              "monthly_credit_grant")
			if (self.get(field) or 0) < (before.get(field) or 0)
		]
		if not reduced:
			return

		count = frappe.db.count("Subscription", {"plan": self.name, "status": ("in", ("Active", "Trialing"))})
		if not count:
			return

		frappe.msgprint(
			_("{0} kept their existing limits: {1} applies to new subscriptions only.").format(
				_("{0} subscriptions on this plan").format(count),
				", ".join(reduced),
			),
			indicator="blue",
			alert=True,
		)
