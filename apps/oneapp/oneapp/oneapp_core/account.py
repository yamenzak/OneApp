"""The workspace's own administration, asked from inside the workspace.

Who is in this workspace, what roles it has, and what it is called on the
internet are facts about *one* workspace, so somebody editing them should not
have to leave it for another address. The rows live on the control plane —
which is right, because a person may own three workspaces and only the control
plane knows that — so these are a relay rather than a second copy. See
`docs/MARKETPLACE.md` §2 for which of the account's screens moved and which
could not.

**Every one of these is one line, and that is the point.** The moment this file
starts deciding anything, there are two implementations of who may invite
somebody and they disagree within a month. What may be asked is decided on the
control plane, by name, in `api/tenant._may_be_asked`; who is asking is asserted
here and checked there against the rows that say who owns this workspace.

The session is the whole of the assertion. `frappe.session.user` is a person
this site has authenticated — its own sign-in, its own password rules, its own
two-factor — and saying so over a signed channel is the same trust the HMAC
already carries when this site reports how much storage it is using.
"""

import frappe

from oneapp.oneapp_core import control_client


def _ask(action: str, **arguments) -> dict:
	"""Relay one question, as the person who asked it."""
	if frappe.session.user in ("", "Guest", None):
		frappe.throw(frappe._("Please sign in."), frappe.PermissionError)

	return control_client.call("workspace_admin", {
		"action": action,
		"as_user": frappe.session.user,
		"arguments": arguments,
	})


@frappe.whitelist(methods=["GET"])
def members() -> dict:
	"""Everyone who can sign in to this workspace, and how many seats are left."""
	return _ask("members")


@frappe.whitelist()
def invite_member(email: str, full_name: str = "", access: str = "Member",
                  roles: str | list | None = None) -> dict:
	"""Invite somebody in. They can sign in within the quarter hour."""
	return _ask("invite_member", email=email, full_name=full_name,
	            access=access, roles=roles)


@frappe.whitelist()
def remove_member(email: str) -> dict:
	"""Take somebody out of this workspace."""
	return _ask("remove_member", email=email)


@frappe.whitelist()
def set_member_roles(email: str, roles: str | list | None = None,
                     access: str | None = None) -> dict:
	"""Change what one person may do here. Only what is passed is changed."""
	return _ask("set_member_roles", email=email, roles=roles, access=access)


@frappe.whitelist(methods=["GET"])
def roles() -> dict:
	"""Every role this workspace may hand out, shipped and its own alike."""
	return _ask("roles")


@frappe.whitelist()
def save_role(role_label: str, grants: str | list, name: str | None = None) -> dict:
	"""Write one of the workspace's own roles, new or edited."""
	return _ask("save_role", role_label=role_label, grants=grants, name=name)


@frappe.whitelist()
def delete_role(name: str) -> dict:
	"""Retire one of the workspace's own roles."""
	return _ask("delete_role", name=name)


@frappe.whitelist(methods=["GET"])
def domain() -> dict:
	"""What this workspace is called on the internet, and how to change it."""
	return _ask("domain")


@frappe.whitelist()
def request_domain(domain: str) -> str:
	"""Ask for a domain of your own. The records to add come back with it."""
	return _ask("request_domain", domain=domain)
