"""The customer's account, declared as a Space.

`/portal/account` is the other half of what `oneapp_control` served. Almost none
of it is a list of records — it is *one account* seen four ways — so it is
component screens by nature rather than by exception. That is the right shape
for it rather than a compromise: the Space runtime is what gives it the rail,
the mobile shell, theming, toasts and every future improvement, and the screens
themselves stay bespoke because their content is.

It lives on the control plane, and half of that is the whole architectural
point. A tenant site's HMAC secret proves it is *itself* and nothing more, so a
tenant can never show you the other two tenancies you own. The control plane is
the one place that knows a person owns three.

That argument is about **billing** — one card pays for three workspaces — and
about Plan and Overview, which are the same kind of fact. It was read for a
while as an argument about the whole area, and it is not: People, Roles and
Domain are facts about *one* workspace, and a person editing them had to leave
the workspace they were editing to do it. They are settings tabs inside
OneSpace now, relayed through `oneapp/onespace/account.py` as the person who
asked. `docs/MARKETPLACE.md` §2 is the dividing question — not "is this
administration?" but "whose fact is it?" — and the reason it is worth keeping
written down is that the pull is always toward moving one more.

Read by `install.py`, beside the operator console, and owned by this file for
the same reason.
"""

import frappe

SPACE_CODE = "onespace-account"

# screen, label, icon
#
# No doctypes and no grant: every screen is a component that calls the
# customer-facing whitelisted methods, each of which resolves the workspace from
# the session and refuses anything the caller does not own. There is nothing for
# `_granted_doctypes` to allow because nothing here reads a doctype directly.
SCREENS = (
	("overview", "Overview", "lucide-layout-grid"),
	("apps", "Apps", "lucide-package"),
	("billing", "Billing", "lucide-receipt"),
	("plan", "Plan", "lucide-briefcase"),
)


def manifest() -> dict:
	from oneapp_control.provisioning.signup import CUSTOMER_ROLE

	return {
		"doctype": "OneSpace Space",
		"space_code": SPACE_CODE,
		"space_label": "Account",
		"module": "OneApp Control",
		"role_name": CUSTOMER_ROLE,
		"icon": "lucide-user-round",
		"sort_order": 0,
		# Narrowed by the role, like the operator console beside it. Both
		# `visible_spaces` and `_space` filter on `role_name`, so an operator
		# does not see this and a customer cannot resolve the console by name.
		"availability": "General",
		"is_active": 1,
		"description": "Your workspaces, and what they cost.",
		"screens": [
			{
				"screen": screen,
				"label": label,
				"icon": icon,
				"component": f"{SPACE_CODE}/{screen}",
			}
			for screen, label, icon in SCREENS
		],
		"doctypes": [],
	}


def seed() -> None:
	"""Write the Space, replacing what is there — see `operator.seed`."""
	if frappe.db.exists("OneSpace Space", SPACE_CODE):
		frappe.delete_doc("OneSpace Space", SPACE_CODE, ignore_permissions=True, force=True)
	frappe.get_doc(manifest()).insert(ignore_permissions=True)
