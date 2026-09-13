import frappe
from frappe.model.document import Document

from oneapp.onestorage import scopes


class DriveAccess(Document):
	def validate(self):
		"""A scope nothing can resolve is a mount that answers 404 to
		everything, and the person who made it finds out in Finder.

		Also where the old `folder` link becomes a scope: a key written before
		scopes existed says `folder:<that>` and means exactly what it always
		did. That is the whole of the migration — no patch, no backfill.
		"""
		if not self.scope and self.folder:
			self.scope = f"{scopes.FOLDER}:{self.folder}"
		scopes.validate(self.scope)
