"""What a person may change about themselves, as opposed to about the workspace.

The settings dialog was an admin's dialog. Everything in it was the workspace's
— its branding, its sign-in rules, its print formats — so it was offered to
admins and nobody else, and a member had nowhere at all to change their own name
or their own password. Frappe has all of it: `User` carries the name, the
avatar, a per-person language and time zone; `Notification Settings` is one
document per person; `update_password` and `Sessions` are the framework's own.
All of it behind a desk the customer never sees.

Two rules, the same two `workspace.py` runs on:

  * **The spec is the allowlist.** `MINE` is every `User` field a person may
    write about themselves, and there is no code path for any other. `User` is
    a large doctype and most of it is administration — roles, permissions,
    `enabled`, the API secret — so an endpoint that took a fieldname would be
    an endpoint that grants roles.

  * **Yourself, and only yourself.** Every write here names
    `frappe.session.user`; none of them takes a user. Somebody else's profile
    is the People page's business, where a seat is counted.

The one thing that is *not* here is the theme. It is a per-person preference
that lives in the browser rather than on the server, and adding a round trip to
it would make the toggle slower for no gain.
"""

import frappe
from frappe import _

#: `User` fields a person may change about themselves, with what to render.
#:
#: `language` and `time_zone` are the two worth explaining: they are per-person
#: *overrides* of the workspace's regional settings, so a colleague working from
#: another country sees their own dates without changing anybody else's.
MINE = {
	"first_name": {"label": "First name", "type": "Data"},
	"last_name": {"label": "Last name", "type": "Data"},
	"user_image": {"label": "Photograph", "type": "Attach Image"},
	"mobile_no": {"label": "Mobile", "type": "Data"},
	"language": {"label": "Language", "type": "Select",
	             "hint": "Yours only. Empty follows the workspace."},
	"time_zone": {"label": "Time zone", "type": "Select",
	              "hint": "Yours only. Empty follows the workspace."},
}

#: Never settable here, however the request is shaped. A belt beside the
#: braces of `MINE`: these are the fields that would turn a profile editor into
#: a way to grant yourself something.
NEVER = {
	"name", "email", "enabled", "user_type", "roles", "role_profile_name",
	"api_key", "api_secret", "new_password", "username", "block_modules",
}


def _me():
	return frappe.get_doc("User", frappe.session.user)


def _languages() -> list[str]:
	rows = frappe.get_all("Language", filters={"enabled": 1},
	                      fields=["name", "language_name"], order_by="language_name")
	return [{"value": row.name, "label": row.language_name or row.name} for row in rows]


def _zones() -> list[str]:
	from frappe.utils.momentjs import get_all_timezones

	return get_all_timezones()


OPTIONS = {"language": _languages, "time_zone": _zones}


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def profile() -> dict:
	"""This person's own row, as the fields they may change.

	The email is returned and is not one of them: it is the account's identity
	and changing it is a control-plane act, because the seat is counted against
	it upstream. Said rather than hidden — a profile page with no address on it
	looks like it forgot.
	"""
	me = _me()
	fields = []
	for key, spec in MINE.items():
		entry = {"key": key, "value": me.get(key) or "", **spec}
		if key in OPTIONS:
			entry["options"] = OPTIONS[key]()
		fields.append(entry)

	return {
		"email": me.name,
		"full_name": me.full_name,
		"fields": fields,
		# What the two blanks fall back to, so "empty follows the workspace" is
		# a sentence with something in it.
		"workspace": {
			"language": frappe.db.get_single_value("System Settings", "language") or "",
			"time_zone": frappe.db.get_single_value("System Settings", "time_zone") or "",
		},
	}


@frappe.whitelist(methods=["POST"])
def save_profile(values: str | dict) -> dict:
	"""Write your own profile. Anything outside `MINE` is refused, not ignored."""
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Those details could not be read."))

	rejected = sorted(set(values) - set(MINE))
	if rejected:
		frappe.throw(_("{0} is not something you can change here.").format(
			", ".join(rejected)))

	me = _me()
	for key, value in values.items():
		if key in NEVER:  # unreachable through MINE, and cheap to keep true
			continue
		me.set(key, value)
	me.save(ignore_permissions=True)
	frappe.db.commit()
	return profile()


# --------------------------------------------------------------------------- #
# Security
#
# Two things, and both are the framework's — this is a surface over them, not an
# implementation. Frappe's own password rules apply on the way in, which is why
# the policy is one of the workspace's settings: an admin sets the bar and this
# is where somebody meets it.
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def security() -> dict:
	"""What this person can be told about their own account's safety."""
	from frappe.sessions import get_expiry_period

	return {
		"email": frappe.session.user,
		"two_factor": bool(
			frappe.db.get_single_value("System Settings", "enable_two_factor_auth")),
		"sessions": _sessions(),
		"session_expiry": get_expiry_period() or "",
	}


def _sessions() -> list[dict]:
	"""Where this account is signed in, most recent first.

	Raw SQL against `tabSessions`, which is the only way to read it: Frappe
	keeps the table without a DocType over it, so `get_all` throws
	`DocType Sessions not found`. The columns are `user`, `sid`, `ipaddress`,
	`lastupdate` and `status`, and none of them names a device — so what this
	can honestly show is when and from where, and the useful control beside it
	is "end all the others" rather than picking one out of a list.
	"""
	rows = frappe.db.sql(
		"""
		select sid, ipaddress, lastupdate
		from tabSessions
		where user = %s
		order by lastupdate desc
		limit 20
		""",
		(frappe.session.user,),
		as_dict=True,
	)
	here = frappe.session.sid
	return [{
		"this_one": row.sid == here,
		"last_seen": str(row.lastupdate or ""),
		"from": row.ipaddress or "",
	} for row in rows]


@frappe.whitelist(methods=["POST"])
def change_password(old_password: str, new_password: str) -> dict:
	"""Change your own password, through the framework's own check.

	The old one is verified rather than trusted: a signed-in session is not
	proof that the person at the keyboard is the account holder, which is the
	entire reason every product asks for it.
	"""
	from frappe.utils.password import check_password, update_password

	if not (old_password or "").strip() or not (new_password or "").strip():
		frappe.throw(_("Both the current and the new password are needed."))

	try:
		check_password(frappe.session.user, old_password)
	except frappe.AuthenticationError:
		frappe.throw(_("That is not your current password."), frappe.AuthenticationError)

	# Frappe's own policy — length, score, and the workspace's minimum — is
	# applied by `User.validate`, so the rule an admin set is the rule here.
	me = _me()
	me.new_password = new_password
	me.save(ignore_permissions=True)
	update_password(frappe.session.user, new_password)
	frappe.db.commit()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def end_other_sessions() -> dict:
	"""Sign this account out everywhere except here.

	Everywhere *except here* deliberately: the button that signs you out of the
	browser you pressed it in is a button nobody presses twice, and the reason
	somebody reaches for this is a laptop they no longer have.
	"""
	from frappe.sessions import clear_sessions

	clear_sessions(user=frappe.session.user, keep_current=True)
	frappe.db.commit()
	return {"ok": True, "sessions": _sessions()}
