import frappe
from frappe import _
from frappe.model.document import Document


class SpaceClaimCode(Document):
	def before_naming(self):
		# Upper-cased before it becomes the docname, because nobody types a code
		# the way it was written down and Frappe would otherwise treat RUA-2026
		# and rua-2026 as two codes.
		if self.claim_code:
			self.claim_code = self.claim_code.strip().upper()

	def validate(self):
		self.claim_code = (self.claim_code or "").strip().upper()

		if int(self.uses_allowed or 0) < 0:
			frappe.throw(_("Uses allowed cannot be negative. Zero is unlimited."))

		# A code for a General space is a code that does nothing: every workspace
		# can already see one. Said here rather than discovered by a customer
		# typing a code that reports success and changes nothing.
		if self.app and frappe.db.get_value(
			"OneSpace Space", self.app, "availability"
		) != "Restricted":
			frappe.throw(
				_("{0} is available to every workspace, so a code for it would "
				  "change nothing. Codes are for Restricted spaces.").format(self.app)
			)

	@property
	def spent(self) -> bool:
		return bool(self.uses_allowed) and int(self.uses_spent or 0) >= int(self.uses_allowed)
