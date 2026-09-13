"""File doctype override routing attachments to R2.

Registered via override_doctype_class. Falls back to Frappe's normal filesystem
behaviour whenever R2 is not configured, so a site without R2 keys still works
rather than failing every upload.

Tenant sites only. `oneapp` is installed on the control plane too, for its
shell and its Space runtime, and the override travels with the app — so
without this the control site would silently acquire a tenant's storage
arrangement for its own attachments. See `onespace.site`.
"""

import frappe
from frappe.core.doctype.file.file import File
from frappe.utils import cint

from oneapp.onespace import site
from oneapp.onestorage import r2
from oneapp.onestorage.kinds import STATUS_FIELD, TRASHED
from oneapp.onestorage.query import ROOT


class OneSpaceFile(File):
	def validate_attachment_limit(self):
		"""Frappe's own check, over the files that are actually *on* the record.

		A doctype may cap its attachments — ERPNext's Project allows four — and
		the framework counts every `File` row pointing at the record. Our bin
		does not delete a row, it marks it, so four files thrown away filled
		the cap for good: the record's Files tab showed nothing, and the fifth
		upload was refused with "Maximum Attachment Limit of 4 has been
		reached" and nothing visible to remove.

		So the count is over what is *visible*, which is the same set the Files
		tab and the Drive already read. A restore can then take a file back and
		put the record one over its limit, which is the right way round: the
		alternative is a file somebody asked for back and did not get.

		Frappe's own refusal is still Frappe's — the message, the exception and
		the title come from `super()` — this only decides whether to reach it.
		"""
		from oneapp.onestorage.query import _visible

		if not (self.attached_to_doctype and self.attached_to_name):
			return
		if self.get(STATUS_FIELD) == TRASHED:
			return

		limit = cint(frappe.get_meta(self.attached_to_doctype).max_attachments)
		if not limit:
			return

		here = frappe.db.count("File", {
			"attached_to_doctype": self.attached_to_doctype,
			"attached_to_name": self.attached_to_name,
			**_visible(),
		})
		if here >= limit:
			super().validate_attachment_limit()

	def set_folder_name(self):
		"""An attachment belongs to its record, not to a bucket.

		Frappe's own version puts every file with an `attached_to_doctype` into
		one folder — `Home/Attachments` — so a workspace with four thousand
		quotations has four thousand files in a single folder nobody browses,
		sitting *beside* the folder tree somebody made rather than inside it.
		That flat bucket is a default rather than a decision, and since §E1
		there is something better in its place: the Records tree, which is the
		same rows read through `attached_to_*` and needs no `folder` at all.

		So an attachment is left folderless. `query.py`'s Home excludes it from
		the top of the drive — without that, dropping the bucket would surface
		every attachment in the workspace at the root, which is worse than the
		bucket was. A file that is *both* attached and filed into a folder
		somebody named keeps that folder: the caller asked for one, and "it can
		have both" is what makes the Files tab a filter rather than a second
		store.

		`Home` is cleared rather than kept, which looks like overriding a
		choice and is not: Frappe's `upload_file` defaults the field to `Home`
		when the caller sends none, so an attachment arriving with `Home` on it
		has not been filed anywhere — it is the default wearing the name of the
		root. Nothing in this product attaches a file to a record *and* files
		it at the top of the drive; the Drive's own upload, which does mean
		`Home`, attaches to nothing.
		"""
		if self.attached_to_doctype and (self.folder or ROOT) == ROOT:
			self.folder = None
			return
		if self.folder:
			return
		return super().set_folder_name()

	def after_insert(self):
		super_after = getattr(super(), "after_insert", None)
		if super_after:
			super_after()

		if site.is_control() or not r2.is_configured() or self.is_folder:
			return

		# Already in R2, and this row is a second pointer at the same object —
		# which is what attaching a file the Drive already holds writes. Reading
		# its content back would mean fetching our own download route, and
		# uploading it again would bill the workspace twice for one drawing.
		if self.get("r2_key"):
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

	def shared_object(self, key: str) -> bool:
		"""Whether another `File` row still points at this R2 object."""
		return bool(
			frappe.db.exists(
				"File", {"r2_key": key, "name": ["!=", self.name]}
			)
		)

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
		# A share link is only meaningful while the file exists, and an orphan
		# would answer a stranger's request with a stack trace rather than the
		# one sentence every refusal there is supposed to say.
		for link in frappe.get_all("File Link", filters={"file": self.name}, pluck="name"):
			frappe.delete_doc("File Link", link, ignore_permissions=True, force=True)

		key = self.get("r2_key")
		# Only when this is the last row pointing at the object. A file attached
		# to a second record is a second `File` row over the same key, and
		# deleting the object because one of them went would empty the other —
		# the original included, from a record nobody was looking at.
		if key and r2.is_configured() and not self.shared_object(key):
			r2.delete(key)

		super_trash = getattr(super(), "on_trash", None)
		if super_trash:
			super_trash()
