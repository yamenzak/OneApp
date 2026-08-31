import frappe
from frappe import _
from frappe.model.document import Document


class WorkspaceRole(Document):
	def validate(self):
		self.role_label = (self.role_label or "").strip()
		self.validate_label()
		self.validate_grants_are_allowed()

	def validate_label(self):
		"""The label is the role's identity, twice over.

		It names the Frappe role on the tenant site (`custom_frappe_role`) and it
		is the key a member's `roles` list stores (`custom_key`). Two roles in one
		workspace sharing a label would therefore be one role wearing two names,
		and revoking either would revoke both.
		"""
		if not self.role_label:
			frappe.throw(_("A role needs a name."))

		# The key is comma-separated on a member, so a comma in a label would
		# split one role into two that do not exist.
		if "," in self.role_label:
			frappe.throw(_("A role name cannot contain a comma."))

		twin = frappe.db.exists(
			"Workspace Role",
			{"tenant": self.tenant, "role_label": self.role_label, "name": ("!=", self.name)},
		)
		if twin:
			frappe.throw(
				_("This workspace already has a role called {0}.").format(self.role_label)
			)

	def validate_grants_are_allowed(self):
		"""A custom role may only reach what the workspace's spaces already expose.

		This is the whole security argument for letting a customer build roles at
		all. `allowed_doctypes` is the union of every doctype in the manifests of
		the spaces this workspace is entitled to — so a custom role can never
		reach `User`, `Role` or `DocType` (they appear in no manifest), and never
		reach an app the workspace has not bought.

		Checked here rather than only in the API because this doctype is also
		reachable from the operator console, and an allowlist that only one of
		two doors consults is not an allowlist.
		"""
		if not self.tenant:
			return

		from oneapp_control.entitlements.registry import allowed_doctypes

		allowed = set(allowed_doctypes(self.tenant))
		for row in self.grants or []:
			if row.document_type not in allowed:
				frappe.throw(
					_("{0} is not something this workspace's apps expose, so a role "
					  "here cannot grant it.").format(row.document_type)
				)

	def before_insert(self):
		if not self.created_by_email:
			self.created_by_email = frappe.session.user
