"""A mount's own rules. See `oneapp/onestorage/remote.py` for what it is for."""

import frappe
from frappe import _
from frappe.model.document import Document


class RemoteFolder(Document):
	def validate(self):
		self.folder_name = (self.folder_name or "").strip()
		if "/" in self.folder_name:
			# The name is the first segment of `remote://<name>/<path>`, so a
			# slash in one is a mount every path under it parses out of.
			frappe.throw(_("A mount's name cannot contain a slash."))

		self.host = (self.host or "").strip()
		self.base_path = "/" + (self.base_path or "/").strip().strip("/")
		if ".." in self.base_path.split("/"):
			frappe.throw(_("A base path cannot walk upwards."))

		if self.private_key and self.protocol != "SFTP":
			# ftplib has no concept of one, and a key stored against an FTP
			# mount is a credential nothing will ever use and somebody will
			# assume is in force.
			frappe.throw(_("A private key is only used over SFTP."))
