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
	"""Relay one question, as the person who asked it.

	An account that cannot be reached comes back as `{"unreachable": True}`
	rather than as an exception, because it is an answer: this site is not
	linked to a control plane, or the network is having a day, and neither is a
	fault in the request somebody just made. Raising made it a 500 in the
	browser console on a settings page that had rendered correctly.
	"""
	if frappe.session.user in ("", "Guest", None):
		frappe.throw(frappe._("Please sign in."), frappe.PermissionError)

	try:
		return control_client.call("workspace_admin", {
			"action": action,
			"as_user": frappe.session.user,
			"arguments": arguments,
		})
	except (control_client.NotProvisioned, control_client.ControlPlaneError):
		return {"unreachable": True}


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


@frappe.whitelist(methods=["GET"])
def marketplace() -> dict:
	"""Spaces this workspace could add, and what adding each one would take."""
	return _ask("marketplace")


@frappe.whitelist()
def enable_space(space: str) -> dict:
	"""Turn on a space this workspace was offered, and bring it in now.

	The grant is written on the control plane, and this site learns what it is
	entitled to by pulling — every fifteen minutes. Which would make pressing a
	card do nothing visible for a quarter of an hour, and "it will appear
	shortly" is the sentence `tests/test_ui_copy.py` exists to keep out of this
	product. So the pull is made here, immediately, and the space is in the
	launcher by the time the page has finished reloading.

	The sync is allowed to fail without failing the press: the entitlement is
	written either way, and the scheduled pull fifteen minutes later is exactly
	the fallback this is a shortcut past.
	"""
	answer = _ask("enable_space", space=space)

	try:
		from oneapp.oneapp_core import sync

		sync.sync_from_control_plane()
	except Exception:
		frappe.log_error(title="Marketplace: could not pull after enabling")

	return answer
