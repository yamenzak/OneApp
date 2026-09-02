"""Workspace settings — the parts of Frappe a customer owns.

A tenant site is a real Frappe site, so most of what a workspace needs to be
*theirs* already exists: the name and logo on the sign-in page, who may sign in
and how, what a date looks like. All of it lives in singles an ordinary user
cannot touch, behind a desk the customer never sees (DECISIONS §7).

So this is the bridge. Three rules make it safe to hand a customer:

  * **The spec is the allowlist.** A setting is writable because it appears in
    `GROUPS`, and writing anything else is not a bug to be caught later — there
    is no code path for it. Frappe's singles are large and mixed: System
    Settings alone carries the scheduler, the backup count and the API request
    log next to the date format.

  * **The owner is not a System Manager** (DECISIONS §8), which is the point of
    the role and also why every write here is `ignore_permissions`. The check is
    the workspace role, once, at the top.

  * **Ours stays ours.** Quotas, backups, the scheduler, telemetry and the mail
    footer are platform concerns; a workspace that can turn off its own
    scheduler can break itself in a way its owner cannot diagnose and we get
    the ticket. `docs/WORKSPACE-SETTINGS.md` records every field considered and
    why it landed where it did.
"""

import frappe
from frappe import _
from frappe.utils.momentjs import get_all_timezones

# Set by the control plane's sync. An Admin member holds it too — see
# oneapp_core/sync.py, which is deliberately the only thing that grants it.
OWNER_ROLE = "OneSpace Workspace Owner"

# Support reaches a workspace as Administrator, who holds this instead.
SUPPORT_ROLE = "System Manager"


class Setting:
	"""One thing a customer can change, and everywhere it has to be written.

	`targets` is a list because Frappe stores the same fact twice often enough
	to matter: the application name is on Website Settings *and* System Settings,
	and the sign-in page reads the first while emails read the second. Writing
	one and not the other is how a workspace ends up called two things.
	"""

	def __init__(self, key, label, type="Data", targets=(), options=None,
	             options_from=None, hint="", invert=False, placeholder=""):
		self.key = key
		self.label = label
		self.type = type
		self.targets = targets
		self.options = options
		# A few of Frappe's Selects are filled in at runtime rather than in the
		# doctype — the time zone list is built from the tz database — so the
		# meta says nothing and a copy here would be wrong within a year.
		self.options_from = options_from
		self.hint = hint
		# Some of Frappe's flags are negative — `disable_signup`, and
		# `disable_user_pass_login`. A customer should be answering "is this on",
		# not "is the disabling of this off".
		self.invert = invert
		self.placeholder = placeholder

	def read(self):
		doctype, field = self.targets[0]
		value = frappe.db.get_single_value(doctype, field)
		if self.type == "Check":
			value = 1 if value else 0
			return 0 if self.invert and value else (1 if self.invert else value)
		return value

	def write(self, value):
		if self.type == "Check":
			value = 1 if value else 0
			if self.invert:
				value = 0 if value else 1
		for doctype, field in self.targets:
			frappe.db.set_single_value(doctype, field, value)

	def as_dict(self):
		return {
			"key": self.key,
			"label": self.label,
			"type": self.type,
			"options": self.options,
			"hint": self.hint,
			"placeholder": self.placeholder,
		}


GROUPS = [
	{
		"key": "branding",
		"label": "Branding",
		"icon": "lucide-palette",
		"description": (
			"What people see before they are signed in. Set at provisioning so a "
			"workspace is never branded as something else on its first visit."
		),
		"settings": [
			Setting(
				"workspace_name",
				"Workspace name",
				targets=[("Website Settings", "app_name"), ("System Settings", "app_name")],
				hint="On the sign-in page, in the browser tab, and as the sender name on email.",
			),
			Setting(
				"logo",
				"Logo",
				type="Attach Image",
				# The sign-in page reads Website Settings first and falls back to
				# Navbar Settings; support seeing the desk should see the same
				# logo, so both are written.
				targets=[("Website Settings", "app_logo"), ("Navbar Settings", "app_logo")],
				hint="Shown on the sign-in page. A wide logo works better than a square one.",
			),
			Setting(
				"favicon",
				"Favicon",
				type="Attach Image",
				targets=[("Website Settings", "favicon")],
				hint="The browser tab icon.",
			),
			Setting(
				"splash",
				"Splash image",
				type="Attach Image",
				targets=[("Website Settings", "splash_image")],
				hint="Shown while the workspace loads.",
			),
		],
	},
	{
		"key": "signin",
		"label": "Sign in",
		"icon": "lucide-key-round",
		"description": (
			"How people get in. Everyone in a workspace is invited — see "
			"`joining` below for why that is not a setting."
		),
		"settings": [
			Setting(
				"allow_password_login",
				"Password sign-in",
				type="Check",
				targets=[("System Settings", "disable_user_pass_login")],
				invert=True,
				hint="Turn off only once everyone can sign in another way, or nobody gets in.",
			),
			Setting(
				"login_with_email_link",
				"Email a sign-in link",
				type="Check",
				targets=[("System Settings", "login_with_email_link")],
				hint="A link instead of a password, sent from your workspace's own address.",
			),
			Setting(
				"login_with_email_link_expiry",
				"Link expires after (minutes)",
				type="Int",
				targets=[("System Settings", "login_with_email_link_expiry")],
			),
			Setting(
				"enable_two_factor_auth",
				"Two-factor authentication",
				type="Check",
				targets=[("System Settings", "enable_two_factor_auth")],
				hint="Required for everyone in the workspace once on.",
			),
			Setting(
				"two_factor_method",
				"Second factor",
				type="Select",
				# Frappe also offers SMS, which needs an SMS gateway this platform
				# does not run. Offering it would fail at the moment someone is
				# locked out, which is the worst moment to discover it.
				options=["OTP App", "Email"],
				targets=[("System Settings", "two_factor_method")],
			),
			Setting(
				"session_expiry",
				"Sign out after idle",
				type="Data",
				targets=[("System Settings", "session_expiry")],
				placeholder="06:00",
				hint="Hours:minutes of inactivity. Empty means never.",
			),
			Setting(
				"deny_multiple_sessions",
				"One session per person",
				type="Check",
				targets=[("System Settings", "deny_multiple_sessions")],
			),
			Setting(
				"enable_password_policy",
				"Require strong passwords",
				type="Check",
				targets=[("System Settings", "enable_password_policy")],
			),
			Setting(
				"minimum_password_score",
				"Minimum strength",
				type="Select",
				options=["1", "2", "3", "4"],
				targets=[("System Settings", "minimum_password_score")],
				hint="2 is 'good', 4 is 'excellent'.",
			),
			Setting(
				"allow_consecutive_login_attempts",
				"Failed attempts before a pause",
				type="Int",
				targets=[("System Settings", "allow_consecutive_login_attempts")],
			),
			Setting(
				"allow_login_after_fail",
				"Pause for (seconds)",
				type="Int",
				targets=[("System Settings", "allow_login_after_fail")],
			),
		],
	},
	{
		"key": "printing",
		"label": "Printing",
		"icon": "lucide-printer",
		"description": (
			"How every printed document and PDF comes out — the paper, the type "
			"and the engine. A print format decides what is on the page; this "
			"decides what the page is."
		),
		"settings": [
			Setting("pdf_page_size", "Page size", type="Select",
			        targets=[("Print Settings", "pdf_page_size")],
			        hint="Custom takes the two sizes below, in millimetres."),
			Setting("pdf_page_width", "Custom width (mm)",
			        targets=[("Print Settings", "pdf_page_width")]),
			Setting("pdf_page_height", "Custom height (mm)",
			        targets=[("Print Settings", "pdf_page_height")]),
			# The typeface every format inherits unless it names its own. A
			# Select rather than free text: it reaches a stylesheet the PDF
			# engine has to have the font for, and a name nobody installed
			# renders as the engine's fallback with nothing to say so.
			Setting("font", "Font", type="Select",
			        targets=[("Print Settings", "font")]),
			Setting("font_size", "Font size", type="Int",
			        targets=[("Print Settings", "font_size")],
			        hint="In points. A format may still set its own."),
			Setting("print_style", "Style", type="Link", options="Print Style",
			        targets=[("Print Settings", "print_style")],
			        hint="The typography and spacing a format is drawn in."),
			# Chrome renders what a browser renders; wkhtmltopdf is an old
			# WebKit and gets modern CSS wrong. They are not interchangeable
			# and a format that looks right in one can look wrong in the other,
			# which is why this is a workspace-wide decision rather than a
			# per-print one.
			Setting("pdf_generator", "PDF engine", type="Select",
			        targets=[("Print Settings", "pdf_generator")],
			        hint="Chrome renders modern CSS. wkhtmltopdf is faster to start."),
			Setting("with_letterhead", "Print with the letter head", type="Check",
			        targets=[("Print Settings", "with_letterhead")]),
			Setting("repeat_header_footer", "Repeat the header and footer on every page",
			        type="Check",
			        targets=[("Print Settings", "repeat_header_footer")]),
			Setting("allow_print_for_draft", "Allow drafts to be printed", type="Check",
			        targets=[("Print Settings", "allow_print_for_draft")]),
			Setting("allow_print_for_cancelled", "Allow cancelled documents to be printed",
			        type="Check",
			        targets=[("Print Settings", "allow_print_for_cancelled")]),
			Setting("allow_page_break_inside_tables", "Let a table break across pages",
			        type="Check",
			        targets=[("Print Settings", "allow_page_break_inside_tables")],
			        hint="Off keeps a table whole and may leave a page short."),
		],
	},
	{
		"key": "regional",
		"label": "Regional",
		"icon": "lucide-globe",
		"description": "How dates, numbers and money are written throughout the workspace.",
		"settings": [
			Setting("country", "Country", type="Link", options="Country",
			        targets=[("System Settings", "country")]),
			Setting("time_zone", "Time zone", type="Select",
			        # Frappe fills this list at runtime from the tz database, so
			        # the doctype's own options are empty and reading the meta
			        # gives a select with nothing in it.
			        options_from=lambda: get_all_timezones(),
			        targets=[("System Settings", "time_zone")]),
			Setting("language", "Language", type="Link", options="Language",
			        targets=[("System Settings", "language")]),
			Setting("date_format", "Date format", type="Select",
			        targets=[("System Settings", "date_format")]),
			Setting("time_format", "Time format", type="Select",
			        targets=[("System Settings", "time_format")]),
			Setting("number_format", "Number format", type="Select",
			        targets=[("System Settings", "number_format")]),
			Setting("first_day_of_the_week", "Week starts on", type="Select",
			        targets=[("System Settings", "first_day_of_the_week")]),
			Setting("currency", "Currency", type="Link", options="Currency",
			        targets=[("System Settings", "currency")],
			        hint="The default for new documents. Each one can still say otherwise."),
			Setting("float_precision", "Decimal places", type="Select",
			        targets=[("System Settings", "float_precision")]),
			Setting("currency_precision", "Decimal places on money", type="Select",
			        targets=[("System Settings", "currency_precision")]),
		],
	},
]


def all_groups() -> list[dict]:
	"""Every settings group on this site, ours and anybody else's.

	`GROUPS` is what a workspace has. An app installed alongside may add more
	through the `onespace_settings_groups` hook — which is how the control plane
	puts its own settings in this dialog instead of shipping a second one. Each
	provider returns groups in the same shape, so nothing downstream can tell
	them apart.

	A provider that raises is skipped rather than fatal: this runs behind the
	settings dialog, and one app's bad group should not be a dialog that will
	not open.
	"""
	found = list(GROUPS)
	for path in frappe.get_hooks("onespace_settings_groups") or []:
		try:
			found += frappe.get_attr(path)() or []
		except Exception:
			frappe.log_error(title="OneSpace settings provider failed", message=path)
	return found


def _group(key: str) -> dict:
	for group in all_groups():
		if group["key"] == key:
			return group
	frappe.throw(_("Unknown settings group {0}.").format(key))


def _settings(group_key: str) -> dict:
	return {s.key: s for s in _group(group_key)["settings"]}


def may_read(group: dict) -> bool:
	"""Whether this reader may see a group at all.

	Per group rather than per dialog, because two audiences now share the
	control plane: a workspace admin owns branding and sign-in, and only a
	System Manager has any business in the Frappe Cloud credentials. A group
	that names no roles is the workspace's own, which is what every group was
	before this existed.
	"""
	roles = set(frappe.get_roles())
	wanted = set(group.get("roles") or (OWNER_ROLE, SUPPORT_ROLE))
	return bool(roles & wanted)


def require_group(group: dict) -> None:
	if not may_read(group):
		frappe.throw(
			_("You cannot change {0}.").format(group.get("label") or group["key"]),
			frappe.PermissionError,
		)


def require_owner():
	roles = set(frappe.get_roles())
	if OWNER_ROLE not in roles and SUPPORT_ROLE not in roles:
		frappe.throw(
			_("Only a workspace admin can change these settings."), frappe.PermissionError
		)


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

def _options_for(setting: Setting) -> list | str | None:
	"""Select options, read from the doctype rather than restated here.

	Frappe's own list of time zones is several hundred entries and its date
	formats change between versions; a copy would be wrong on the day it was
	written.
	"""
	if setting.options_from:
		return setting.options_from()

	if setting.type != "Select" or setting.options is not None:
		return setting.options

	doctype, field = setting.targets[0]
	meta = frappe.get_meta(doctype)
	options = (meta.get_field(field).options or "").split("\n")
	return [o for o in options if o]


@frappe.whitelist()
def get() -> dict:
	"""Every group this reader may see, its settings, and what they are set to.

	No longer `require_owner` at the door. The dialog is shared now — a
	workspace admin sees the workspace's groups, an operator on the control
	plane sees the control plane's — so the gate is per group, and somebody who
	may see none gets an empty dialog rather than a refusal they cannot act on.
	"""
	groups = []
	for group in all_groups():
		if not may_read(group):
			continue
		fields = []
		for setting in group["settings"]:
			entry = setting.as_dict()
			entry["options"] = _options_for(setting)
			entry["value"] = setting.read()
			fields.append(entry)
		groups.append(
			{
				"key": group["key"],
				"label": group["label"],
				"icon": group["icon"],
				"description": group["description"],
				"fields": fields,
			}
		)

	# The sign-in rules are the workspace's own, so they travel with it and not
	# with a control-plane group somebody happens to be able to see.
	joins = joining() if any(g["key"] == "signin" for g in groups) else None
	return {"groups": groups, "joining": joins}


@frappe.whitelist(methods=["POST"])
def save(group: str, values: str | dict) -> dict:
	"""Write one group. Anything outside its spec is refused, not ignored."""
	require_group(_group(group))

	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Those settings could not be read."))

	known = _settings(group)
	rejected = sorted(set(values) - set(known))
	if rejected:
		frappe.throw(_("{0} is not a workspace setting.").format(", ".join(rejected)))

	for key, value in values.items():
		known[key].write(value)

	# The one-time password issuer is what an authenticator app shows beside the
	# code. Left at Frappe's default it names software the customer has never
	# heard of, in the one place they look when they cannot get in.
	if group in ("branding", "signin"):
		name = frappe.db.get_single_value("Website Settings", "app_name")
		if name:
			frappe.db.set_single_value("System Settings", "otp_issuer_name", name)

	frappe.clear_cache()
	return {"ok": True}


# --------------------------------------------------------------------------- #
# Joining
# --------------------------------------------------------------------------- #

def joining() -> dict:
	"""Who may get an account here, and why that is not a switch.

	Frappe has a signup form, and turning it on would be one line. It is off,
	permanently, for reasons that are not about preference:

	  * `frappe.core.doctype.user.user.sign_up` creates an enabled Website User
	    with whatever role Portal Settings names and no domain restriction. On a
	    workspace addressed at a guessable URL that is a stranger with an
	    account.
	  * Seats are counted and billed by the control plane against the workspace's
	    member list. A user created here is invisible to that, so open signup is
	    also a way to exceed a plan without paying for it.
	  * Membership is reconciled *into* this site from the control plane, one
	    way. An account created here that the control plane does not know about
	    is disabled again on the next sync — so open signup would not even work,
	    it would produce accounts that stop working within the hour.

	So people are invited, from the workspace's own People page, which adds them
	upstream where the seat is counted and lets the sync create the account.
	"""
	return {
		"mode": "invite",
		"signup_disabled": bool(
			frappe.db.get_single_value("Website Settings", "disable_signup")
		),
		"reason": _(
			"People are invited from your workspace's People page. Accounts created "
			"any other way are not counted against your seats and are disabled on "
			"the next sync."
		),
	}


# --------------------------------------------------------------------------- #
# Naming
#
# Not a settings *group*, because it is not a form: it is one doctype at a
# time, with a list of prefixes and a counter under each. The mechanics are in
# `oneapp_core.naming`, which is a gate and a shape over Frappe's own
# `Document Naming Settings` — every write goes through it, because the
# counter, the Property Setter on the field, the duplicate check across every
# other doctype and the Version log are four things that have to happen
# together and it already does all four.
# --------------------------------------------------------------------------- #


def _naming_gate() -> None:
	"""Naming is the workspace's, so the workspace's own owners decide it.

	The same door the settings dialog uses, and for the same reason: a series
	is a decision about every id the workspace will ever issue.
	"""
	roles = set(frappe.get_roles())
	if not roles & {OWNER_ROLE, SUPPORT_ROLE}:
		frappe.throw(_("Only a workspace admin can change how records are named."),
		             frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def naming() -> list[dict]:
	"""Every doctype this workspace may set a series for, with its prefixes."""
	from oneapp.oneapp_core import naming as module

	_naming_gate()
	return module.doctypes()


@frappe.whitelist(methods=["POST"])
def set_naming(doctype: str, series: str | list) -> list[dict]:
	"""Replace the prefixes a doctype offers."""
	from oneapp.oneapp_core import naming as module

	_naming_gate()
	wanted = frappe.parse_json(series) if isinstance(series, str) else series
	return module.set_options(doctype, wanted or [])


@frappe.whitelist(methods=["POST"])
def set_naming_counter(doctype: str, prefix: str, value) -> list[dict]:
	"""Move a series' counter, which is the one destructive thing here."""
	from oneapp.oneapp_core import naming as module

	_naming_gate()
	return module.set_counter(doctype, prefix, value)


@frappe.whitelist(methods=["GET"])
def naming_preview(doctype: str, prefix: str) -> list[str]:
	"""The next few ids a series would issue."""
	from oneapp.oneapp_core import naming as module

	_naming_gate()
	return module.preview(doctype, prefix)


# --------------------------------------------------------------------------- #
# Printing
#
# The settings *group* above decides the paper — size, font, engine, margins.
# This decides what is drawn on it: the formats themselves and the letter heads
# they sit under. Both are documents rather than settings, so neither fits the
# Setting/target shape, and both are the workspace's own decision rather than a
# per-person one — which is why they share the settings gate.
#
# Every mechanic lives in `oneapp_core.printing`, over Frappe's own Print
# Format, Letter Head and `PrintFormatGenerator`. Nothing here renders.
# --------------------------------------------------------------------------- #


def _printing_gate() -> None:
	"""A format is what every printed document looks like, so it is an admin's.

	The same door the settings dialog uses. It matters more here than most: a
	drawn format may carry an HTML element, which the generator renders as a
	Jinja template with the document in scope.
	"""
	roles = set(frappe.get_roles())
	if not roles & {OWNER_ROLE, SUPPORT_ROLE}:
		frappe.throw(_("Only a workspace admin can change print formats."),
		             frappe.PermissionError)


def _printable() -> set[str]:
	"""Every doctype this workspace's own spaces put on a screen.

	The same rule as naming, for the same reason: a format is drawn over a
	doctype, and the ones worth drawing over are the ones somebody here can
	open. `Error Log` is not one of them.
	"""
	from oneapp.oneapp_core import sync

	return sync.granted_doctypes()


def _printable_gate(doctype: str) -> None:
	_printing_gate()
	if doctype not in _printable():
		frappe.throw(_("No screen in this workspace shows {0}.").format(doctype))


@frappe.whitelist(methods=["GET"])
def print_formats(doctype: str = "") -> dict:
	"""The doctypes a format may be drawn over, and one doctype's formats."""
	from oneapp.oneapp_core import printing

	_printing_gate()
	offered = sorted(one for one in _printable() if frappe.has_permission(one, "read"))
	doctype = doctype if doctype in offered else (offered[0] if offered else "")
	return {
		"doctypes": [{"doctype": one, "label": _(one)} for one in offered],
		"doctype": doctype,
		"formats": printing.formats(doctype) if doctype else [],
		"letter_heads": printing.letter_heads(),
	}


@frappe.whitelist(methods=["GET"])
def print_palette(doctype: str) -> dict:
	"""What the builder may put on the page, for one doctype."""
	from oneapp.oneapp_core import printing

	_printable_gate(doctype)
	return printing.palette(doctype)


@frappe.whitelist(methods=["GET"])
def print_format(name: str) -> dict:
	"""One drawn format, as the builder opens it."""
	from oneapp.oneapp_core import printing

	_printing_gate()
	found = printing.format_of(name)
	_printable_gate(found["doctype"])
	return found


@frappe.whitelist(methods=["POST"])
def save_print_format(doctype: str, label: str, layout, setup=None,
                      name: str = "") -> dict:
	"""Create or replace a drawn format."""
	from oneapp.oneapp_core import printing

	_printable_gate(doctype)
	return printing.save_format(doctype, label, layout, setup, name)


@frappe.whitelist(methods=["POST"])
def delete_print_format(name: str) -> dict:
	"""Remove one, and the default that pointed at it."""
	from oneapp.oneapp_core import printing

	_printing_gate()
	found = printing.format_of(name)
	_printable_gate(found["doctype"])
	printing.delete_format(name)
	return {"formats": printing.formats(found["doctype"])}


@frappe.whitelist(methods=["POST"])
def set_default_print_format(doctype: str, name: str = "") -> list[dict]:
	"""Which format a document prints with when nobody picks one."""
	from oneapp.oneapp_core import printing

	_printable_gate(doctype)
	return printing.set_default(doctype, name)


@frappe.whitelist(methods=["POST"])
def print_format_preview(doctype: str, layout, setup=None, name: str = "",
                         letterhead: str = "") -> dict:
	"""Render a layout that has not been saved, against a real record."""
	from oneapp.oneapp_core import printing

	_printable_gate(doctype)
	return printing.draft_preview(doctype, layout, setup, name, letterhead)


@frappe.whitelist(methods=["GET"])
def letter_heads() -> list[dict]:
	from oneapp.oneapp_core import printing

	_printing_gate()
	return printing.letter_heads()


@frappe.whitelist(methods=["GET"])
def letter_head(name: str) -> dict:
	from oneapp.oneapp_core import printing

	_printing_gate()
	return printing.letter_head(name)


@frappe.whitelist(methods=["POST"])
def save_letter_head(label: str, values=None, name: str = "") -> dict:
	from oneapp.oneapp_core import printing

	_printing_gate()
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	return printing.save_letter_head(label, values, name)


@frappe.whitelist(methods=["POST"])
def delete_letter_head(name: str) -> list[dict]:
	from oneapp.oneapp_core import printing

	_printing_gate()
	printing.delete_letter_head(name)
	return printing.letter_heads()
