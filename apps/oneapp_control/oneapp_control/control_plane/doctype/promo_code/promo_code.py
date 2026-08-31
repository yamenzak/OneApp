import frappe
from frappe import _
from frappe.model.document import Document

from oneapp_control.billing import promos


class PromoCode(Document):
	def before_naming(self):
		# Upper-cased before it becomes the docname, because nobody types a code
		# the way it was written down and Frappe would otherwise treat DEMO100
		# and demo100 as two codes.
		if self.promo_code:
			self.promo_code = self.promo_code.strip().upper()

	def validate(self):
		self.promo_code = (self.promo_code or "").strip().upper()
		self.validate_discount()
		self.validate_scope()
		# In validate, not on_update: the coupon id and the promotion code id
		# belong to the same write the operator asked for. Never raises — see
		# billing/promos.py.
		promos.sync(self)

	def validate_discount(self):
		if self.discount_type == "Percent":
			percent = float(self.percent_off or 0)
			if not 0 < percent <= 100:
				frappe.throw(_("A percentage off has to be between 1 and 100."))
		elif float(self.amount_off or 0) <= 0:
			frappe.throw(_("An amount off has to be more than nothing."))

		if self.duration == "Repeating" and int(self.duration_in_months or 0) <= 0:
			frappe.throw(_("A repeating code has to say for how many months."))

	def validate_scope(self):
		if not (self.on_subscriptions or self.on_addons or self.on_credit_packs):
			frappe.throw(
				_("A code that applies to nothing cannot be redeemed. Choose what it is for.")
			)
