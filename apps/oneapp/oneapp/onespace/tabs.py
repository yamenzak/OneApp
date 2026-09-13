"""Every tab in the settings dialog, and who each one is for.

The dialog had two halves and only one of them knew about people. Four groups —
branding, sign in, printing, regional — came from `workspace.GROUPS`, which has
carried a per-group role check since the control plane started sharing this
dialog. The other ten were written into `SettingsShell.vue` by hand and drawn
for everybody, each one gated inside its own endpoints instead. Nothing was
reachable that should not have been; what was wrong is what a person *saw*. So
the dialog was only ever offered to admins, because a member opening it would
have found ten tabs and been refused by all of them.

This is the missing half: one list, declaring every tab whichever way it is
rendered, each with the audience it is for. `workspace.get()` returns the ones
this reader may open and the shell draws exactly those — so the same dialog is
the owner's and the member's, and neither is shown a door that does not open.

An audience is a **predicate, not a role**, because one of them is not a role:
"holds an address" is what decides whether somebody may write a mail template,
and no role in this product expresses it. `AUDIENCES` is the whole vocabulary.
"""

import frappe

#: What a tab is rendered by.
#:
#: `fields` is the declarative half — `workspace.GROUPS`, a spec the server
#: renders and checks writes against. `panel` is a tab the SPA draws itself
#: because it is not a list of fields: a print format builder, a chart of
#: accounts, an import with a dry run. Its name is the contract, and
#: `tests/test_settings_tabs.py` holds the SPA to it.
FIELDS = "fields"
PANEL = "panel"


def _everyone() -> bool:
	return frappe.session.user not in ("", "Guest")


def _admin() -> bool:
	from oneapp.onespace.workspace import OWNER_ROLE, SUPPORT_ROLE

	return bool(set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE})


def _support() -> bool:
	from oneapp.onespace.workspace import SUPPORT_ROLE

	return SUPPORT_ROLE in frappe.get_roles()


def _mailbox() -> bool:
	"""Holds an address here.

	The one audience that is not a role, and the reason audiences are predicates.
	A signature and an out-of-office belong to whoever answers that address,
	which is a fact about `Email Account` rows rather than about permissions —
	`email/mailbox.py` has always asked it this way and every mail endpoint
	agrees with it.
	"""
	try:
		from oneapp.onemail import mailbox

		return bool(mailbox._held())
	except Exception:
		# A workspace with no mail set up at all. Not an error and not a tab.
		return False


#: Who may open a tab. The values are the words a tab declares.
AUDIENCES = {
	# Anybody signed in. Their own things: their name, their password, what they
	# are told about, what this looks like.
	"everyone": _everyone,
	# Whoever answers an address here.
	"mailbox": _mailbox,
	# The workspace's own admin — `OneSpace Workspace Owner`, or our support
	# signed in as Administrator. Deliberately not "System Manager" alone: the
	# owner is not one, which is the whole point of the role.
	"admin": _admin,
	# Us. A group nobody at the customer should see.
	"support": _support,
}


#: Every tab, in the order the dialog draws them.
#:
#: `section` is which heading it sits under — "You" for a person's own,
#: "Workspace" for the workspace's. A `fields` tab's key is a
#: `workspace.GROUPS` key; a `panel` tab's key is what `SettingsShell.vue` maps
#: to a component.
TABS = [
	# ----- You ------------------------------------------------------------- #
	{"key": "profile", "label": "Profile", "icon": "lucide-circle-user",
	 "section": "You", "kind": PANEL, "audience": "everyone"},
	{"key": "security", "label": "Security", "icon": "lucide-lock",
	 "section": "You", "kind": PANEL, "audience": "everyone"},
	{"key": "notifications", "label": "Notifications", "icon": "lucide-bell-dot",
	 "section": "You", "kind": PANEL, "audience": "everyone"},
	{"key": "appearance", "label": "Appearance", "icon": "lucide-sun-moon",
	 "section": "You", "kind": PANEL, "audience": "everyone"},
	# Under You and not under Workspace, and the rule that says so is a good
	# one: a tab everybody can open is one of their own. Half of what is in
	# here *is* theirs — the privacy notice describes the handling of their
	# personal data and they agreed to it themselves — and the workspace's half
	# is shown beside it because a person is entitled to read the contract they
	# are working under even when somebody else signed it.
	{"key": "legal", "label": "Legal", "icon": "lucide-scale",
	 "section": "You", "kind": PANEL, "audience": "everyone"},
	# Only for somebody who holds an address, which is the whole reason an
	# audience is a predicate: a signature and an away message belong to
	# whoever answers the address, and no role in this product says that.
	{"key": "mailbox", "label": "Mailbox", "icon": "lucide-at-sign",
	 "section": "You", "kind": PANEL, "audience": "mailbox"},

	# ----- Workspace ------------------------------------------------------- #
	{"key": "branding", "label": "Branding", "icon": "lucide-palette",
	 "section": "Workspace", "kind": FIELDS, "audience": "admin"},
	{"key": "signin", "label": "Sign in", "icon": "lucide-key-round",
	 "section": "Workspace", "kind": FIELDS, "audience": "admin"},
	{"key": "regional", "label": "Regional", "icon": "lucide-globe",
	 "section": "Workspace", "kind": FIELDS, "audience": "admin"},
	{"key": "books", "label": "Books", "icon": "lucide-book-open",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "printing", "label": "Printing", "icon": "lucide-printer",
	 "section": "Workspace", "kind": FIELDS, "audience": "admin"},
	{"key": "print-formats", "label": "Print formats", "icon": "lucide-file-type",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "naming", "label": "Naming", "icon": "lucide-hash",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "mail", "label": "Email", "icon": "lucide-mail",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "templates", "label": "Templates", "icon": "lucide-file-text",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "alerts", "label": "Alerts", "icon": "lucide-bell",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "ai", "label": "AI", "icon": "lucide-sparkles",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "storage", "label": "Storage", "icon": "lucide-hard-drive",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	# Beside Storage because it is the same subject seen backwards, and an
	# admin's rather than the owner's alone for the reason People is: it is a
	# workspace decision and it spends nothing. What makes it safe is not the
	# role but the count the panel puts in front of whoever opens it.
	{"key": "backups", "label": "Backups", "icon": "lucide-history",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	# And beside both, because a mounted folder is storage this workspace reads
	# and does not hold. It was configured from a menu on the mount itself in
	# the Drive, which is `docs/UNIFICATION.md` §C2's other half: a thing you
	# *set up* belongs where everything else is set up, and a thing you *use*
	# belongs where you are using it. Browsing a mount is still the rail's;
	# what host it points at is this.
	{"key": "connections", "label": "Connections", "icon": "lucide-server",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},

	# The first of three that used to be at a different address. Who is in this
	# workspace is a fact about *this* workspace, so the person reading it has
	# no reason to leave it — Roles and Domain follow, and Billing does not,
	# for the reason in `docs/MARKETPLACE.md` §2. The rows are still the
	# control plane's; `onespace/account.py` is the relay.
	{"key": "people", "label": "People", "icon": "lucide-users",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "roles", "label": "Roles", "icon": "lucide-user-round",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
	{"key": "domain", "label": "Domain", "icon": "lucide-globe",
	 "section": "Workspace", "kind": PANEL, "audience": "admin"},
]


def may_open(tab: dict) -> bool:
	"""Whether this reader may open one tab.

	An unknown audience is a closed one. A tab whose word was renamed should
	vanish rather than open to everybody, because the second failure is the one
	nobody notices.
	"""
	decide = AUDIENCES.get(tab.get("audience") or "")
	return bool(decide and decide())


def mine() -> list[dict]:
	"""The tabs this reader may open, in order, ours and anybody else's.

	Groups an installed app adds through `onespace_settings_groups` come in as
	`fields` tabs under Workspace, keeping the per-group `roles` check they
	already carry — that is how the control plane puts its own settings in this
	dialog, and it predates audiences.
	"""
	from oneapp.onespace import workspace

	found = [dict(tab) for tab in TABS if may_open(tab)]

	declared = {tab["key"] for tab in TABS}
	for group in workspace.all_groups():
		if group["key"] in declared or not workspace.may_read(group):
			continue
		found.append({
			"key": group["key"],
			"label": group["label"],
			"icon": group["icon"],
			"section": group.get("section") or "Workspace",
			"kind": FIELDS,
			"audience": "admin",
		})
	return found


def require(key: str) -> dict:
	"""The tab, if this reader may open it. The door every panel's data uses."""
	for tab in TABS:
		if tab["key"] == key:
			if not may_open(tab):
				frappe.throw(
					frappe._("You cannot open {0}.").format(tab["label"]),
					frappe.PermissionError,
				)
			return tab
	frappe.throw(frappe._("Unknown settings tab {0}.").format(key))
