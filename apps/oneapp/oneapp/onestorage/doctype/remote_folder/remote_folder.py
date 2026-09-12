"""A mount's own rules. See `oneapp/onestorage/remote.py` for what it is for."""

import frappe
from frappe import _
from frappe.model.document import Document

from oneapp.onestorage.remote import SHARED


class RemoteFolder(Document):
	def validate(self):
		self.folder_name = (self.folder_name or "").strip()
		if "/" in self.folder_name:
			# The name is the first segment of `remote://<name>/<path>`, so a
			# slash in one is a mount every path under it parses out of.
			frappe.throw(_("A mount's name cannot contain a slash."))

		self.host = (self.host or "").strip().rstrip("/")
		self.base_path = "/" + (self.base_path or "/").strip().strip("/")
		if ".." in self.base_path.split("/"):
			frappe.throw(_("A base path cannot walk upwards."))

		if self.private_key and self.protocol != "SFTP":
			# ftplib has no concept of one, and a key stored against an FTP
			# mount is a credential nothing will ever use and somebody will
			# assume is in force.
			frappe.throw(_("A private key is only used over SFTP."))

		if self.protocol in SHARED and self.base_path == "/":
			# There is no listing above a share on SMB: `\\host\` is not a
			# directory, and a mount pointed there fails on its first browse
			# with whatever the library says rather than with this.
			frappe.throw(_("An SMB folder starts with the share: /drawings, "
			               "or /drawings/2026 for a folder inside it."))

		if "://" in self.host and self.protocol != "WebDAV":
			frappe.throw(_("Only a WebDAV host carries a scheme. Put the "
			               "hostname on its own."))
