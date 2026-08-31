import frappe
from frappe import _
from frappe.model.document import Document

from oneapp_control.billing import packs


class CreditPack(Document):
	def validate(self):
		if (self.credits or 0) <= 0:
			frappe.throw(_("A pack with no credits in it is not something to sell."))
		if (self.amount or 0) <= 0:
			frappe.throw(_("A pack has to cost something. Use a promo code to give one away."))

		# In validate, not on_update: the product id, the price id and the new
		# Catalogue Price row then belong to the same write the operator asked
		# for. Never raises — see billing/catalogue.py.
		packs.sync(self)
