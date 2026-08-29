import frappe
from frappe import _
from frappe.model.document import Document


class CreditLedgerEntry(Document):
	"""Append-only. A ledger you can edit is not a ledger.

	Balance is always computed as a sum over these rows, never stored on Tenant,
	so there is no field that can drift out of agreement with history.
	Corrections are new Adjustment rows, not edits.
	"""

	def validate(self):
		if not self.is_new():
			frappe.throw(
				_("Credit Ledger Entries are immutable. "
				  "Post an Adjustment entry instead of editing {0}.").format(self.name)
			)

		self.validate_sign()
		self.validate_expiry()

	def validate_sign(self):
		"""Sign must match the entry type, or balances silently go wrong."""
		if not self.credits:
			frappe.throw(_("Credits cannot be zero."))

		adds = self.entry_type in ("Grant", "Purchase", "Refund")
		removes = self.entry_type in ("Spend", "Expiry")

		if adds and self.credits < 0:
			frappe.throw(_("{0} entries must be positive.").format(self.entry_type))
		if removes and self.credits > 0:
			frappe.throw(_("{0} entries must be negative.").format(self.entry_type))
		# Adjustment may be either sign.

	def validate_expiry(self):
		if self.expires_on and self.entry_type not in ("Grant", "Adjustment"):
			frappe.throw(_("Only Grant entries may carry an expiry date."))

	def on_trash(self):
		frappe.throw(_("Credit Ledger Entries cannot be deleted."))
