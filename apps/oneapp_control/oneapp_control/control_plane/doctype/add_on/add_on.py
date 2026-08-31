import frappe
from frappe import _
from frappe.model.document import Document

from oneapp_control.billing import addons


class Addon(Document):
	def validate(self):
		self.validate_price()
		self.validate_unit()
		# In validate, not on_update: the product id, the price ids and the new
		# Catalogue Price rows then belong to the same write the operator asked
		# for, rather than a second save that could half-apply. Never raises —
		# see billing/catalogue.py.
		addons.sync(self)

	def validate_price(self):
		if (self.price_monthly or 0) < 0 or (self.price_yearly or 0) < 0:
			frappe.throw(_("An add-on cannot cost a negative amount."))

		if not (self.price_monthly or 0) and not (self.price_yearly or 0):
			frappe.throw(
				_("An add-on needs a price at one cadence or the other, or nobody can buy it.")
			)

	def validate_unit(self):
		if (self.unit_gb or 0) <= 0:
			frappe.throw(_("An add-on that adds no storage is not something to sell."))

		if (self.max_units or 0) < 0:
			frappe.throw(_("A ceiling below zero is not a ceiling. Use zero for none."))

	def on_update(self):
		"""Warn that a changed unit size does not move anybody already holding it.

		Same shape as a plan's quota reduction, and surprising in the same way:
		what a workspace holds is captured on its subscription at purchase, so
		editing this changes what the *next* purchase buys and nothing else.
		"""
		before = self.get_doc_before_save()
		if not before or (before.get("unit_gb") or 0) == (self.unit_gb or 0):
			return

		held = frappe.db.count("Subscription Add-on", {"addon": self.name})
		if not held:
			return

		frappe.msgprint(
			_("{0} workspaces keep the {1} GB they bought: this applies to new purchases only.")
			.format(held, before.get("unit_gb")),
			indicator="blue",
			alert=True,
		)
