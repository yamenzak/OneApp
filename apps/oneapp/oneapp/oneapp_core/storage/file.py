"""File doctype override routing attachments to R2.

Registered via override_doctype_class. Falls back to Frappe's normal filesystem
behaviour whenever R2 is not configured, so a site without R2 keys still works
rather than failing every upload.

Tenant sites only. `oneapp` is installed on the control plane too, for its
shell and its Space runtime, and the override travels with the app — so
without this the control site would silently acquire a tenant's storage
arrangement for its own attachments. See `oneapp_core.site`.
"""

import frappe
from frappe.core.doctype.file.file import File

from oneapp.oneapp_core import site
from oneapp.oneapp_core.storage import r2


class OneSpaceFile(File):
	def after_insert(self):
		super_after = getattr(super(), "after_insert", None)
		if super_after:
			super_after()

		if site.is_control() or not r2.is_configured() or self.is_folder:
			return

		self.move_to_r2()

	def move_to_r2(self):
		try:
			content = self.get_content()
		except Exception:
			frappe.log_error(title="R2 upload: could not read file", message=frappe.get_traceback())
			return

		if content is None:
			return

		if isinstance(content, str):
			content = content.encode("utf-8")

		try:
			key = r2.object_key(self)
			url = r2.upload(self, content)
		except Exception:
			# Keep the local copy. An upload that failed must not lose the file.
			frappe.log_error(title="R2 upload failed", message=frappe.get_traceback())
			return

		self.db_set("file_url", url, update_modified=False)
		self.db_set("r2_key", key, update_modified=False)

		self.remove_local_copy()

	def remove_local_copy(self):
		import os

		try:
			path = self.get_full_path()
			if path and os.path.exists(path):
				os.remove(path)
		except Exception:
			# Object is safely in R2; a stale local copy is only wasted disk.
			frappe.log_error(title="R2: local cleanup failed", message=frappe.get_traceback())

	def on_trash(self):
		key = self.get("r2_key")
		if key and r2.is_configured():
			r2.delete(key)

		super_trash = getattr(super(), "on_trash", None)
		if super_trash:
			super_trash()
