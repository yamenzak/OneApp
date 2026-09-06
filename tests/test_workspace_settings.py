"""Workspace settings: the allowlist, and the things that must stay ours.

The risk here is not that a setting is missing. It is that one is present that
should not be — a workspace that can stop its own scheduler, raise its own file
size limit past the quota it pays for, or turn its own signup back on.

`oneapp_core/workspace.py` makes that checkable by construction: the spec the SPA
renders is the same object the write path validates against, so a field is
writable exactly when it is visible. These check that nothing on the wrong side
of `docs/WORKSPACE-SETTINGS.md` has crept into it.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TENANT = ROOT / "apps/oneapp/oneapp"
WORKSPACE = TENANT / "oneapp_core/workspace.py"
BOOKS = TENANT / "oneapp_core/books.py"
SYNC = TENANT / "oneapp_core/sync.py"
AUDIT = ROOT / "docs/WORKSPACE-SETTINGS.md"
TABS = TENANT / "oneapp_core/tabs.py"
SPA = ROOT / "apps/oneapp/frontend/src"


def source(path: Path) -> str:
	return path.read_text()


def function(path: Path, name: str) -> str:
	tree = ast.parse(source(path))
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name == name:
			return ast.get_source_segment(source(path), node)
	raise AssertionError(f"{name} is missing from {path.name}")


def written_fields() -> set[tuple[str, str]]:
	"""Every (doctype, field) the spec can write.

	Read off the `targets=` of each `Setting(...)` rather than by matching
	two-string tuples anywhere in the file — that also caught the group keys and
	the `get_single_value` calls in `joining()`, which are reads.
	"""
	found = set()
	tree = ast.parse(source(WORKSPACE))
	for node in ast.walk(tree):
		if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Setting"):
			continue
		for keyword in node.keywords:
			if keyword.arg != "targets":
				continue
			for pair in keyword.value.elts:
				doctype, field = (x.value for x in pair.elts)
				found.add((doctype, field))
	return found


# Fields whose exposure would let a workspace break itself, or break the terms
# it pays under. Each is in the audit with a reason.
FORBIDDEN = {
	# Breaks the site in a way its owner cannot diagnose.
	"enable_scheduler",
	# Ours to enforce: storage is a billed quota.
	"max_file_size",
	"allowed_file_extensions",
	"backup_limit",
	"encrypt_backup",
	# Guest write access on a shared fleet.
	"allow_guests_to_upload_files",
	"allowed_doctypes_for_guest_uploads",
	# The owner is deliberately not a System Manager, so this locks them out.
	"only_allow_system_managers_to_upload_public_files",
	# White-label surface, and script injection.
	"footer_powered",
	"head_html",
	"banner_html",
	"disable_standard_email_footer",
	"email_footer_address",
	# Leaks schema and code paths across a shared fleet.
	"allow_error_traceback",
	"log_api_requests",
	# A customer's data is not ours to send anywhere.
	"enable_telemetry",
	# See test_signup_is_not_a_setting.
	"disable_signup",
	# Deleting an account here cancels no subscription and frees no seat.
	"show_account_deletion_link",
	"auto_account_deletion",
	# Where a session lands, and whether ERPNext considers itself configured.
	"default_app",
	"setup_complete",
}


def test_nothing_a_workspace_could_break_itself_with_is_writable():
	exposed = {field for _, field in written_fields()}
	overreach = exposed & FORBIDDEN
	assert not overreach, (
		"these are the platform's, not the customer's — see "
		f"docs/WORKSPACE-SETTINGS.md: {sorted(overreach)}"
	)


def test_the_spec_is_the_allowlist():
	"""Not two lists that agree today."""
	body = function(WORKSPACE, "save")
	assert "_settings(group)" in body
	assert "rejected" in body and "frappe.throw" in body, (
		"an unknown key must be refused, not ignored"
	)


def test_every_write_goes_through_the_spec():
	"""No endpoint may set a single directly, or the allowlist is decoration."""
	tree = ast.parse(source(WORKSPACE))
	for node in ast.walk(tree):
		if not isinstance(node, ast.FunctionDef):
			continue
		if node.name in ("write", "save", "sync_branding"):
			continue
		body = ast.get_source_segment(source(WORKSPACE), node) or ""
		assert "set_single_value" not in body, (
			f"{node.name} writes a single outside Setting.write"
		)


# The three ways an endpoint here can check a role, and there are only three.
#
# `require_owner` is the workspace's own gate, and was the only one until the
# settings dialog started carrying groups from another app. `require_group` and
# `may_read` are the per-group version: two audiences share the control plane
# now, so "may you open the dialog" and "may you see the Frappe Cloud
# credentials" are different questions.
# `_naming_gate()` is the same door as `require_owner()` — the workspace's own
# owners — under a name that says what it is guarding. A series is a decision
# about every id the workspace will ever issue, so it is the owner's.
ROLE_CHECKS = (
	"require_owner()", "require_group(", "may_read(", "_naming_gate()",
	# Printing has two doors: one for the settings themselves and one that also
	# checks the doctype is on a screen this workspace shows. The second calls
	# the first, so either satisfies this.
	"_printing_gate()", "_printable_gate(",
	# Alerts, for the sharper version of the same reason: a rule mails people
	# on the workspace's behalf and can name a role rather than a person.
	"_alerts_gate()",
	# Message templates have two doors, because they have two audiences.
	# Writing one is deciding what the workspace says to a customer, which is
	# an admin's; using one is answering an email, which is anybody who holds
	# an address — the same question every other mail endpoint asks.
	"_templates_gate()", "_mail_gate()",
)


def test_every_endpoint_checks_the_role_first():
	"""The owner is not a System Manager, so Frappe's own permissions do not
	protect these — the role check is the only thing that does."""
	for path in (WORKSPACE, BOOKS):
		tree = ast.parse(source(path))
		for node in ast.walk(tree):
			if not isinstance(node, ast.FunctionDef):
				continue
			decorated = any("whitelist" in ast.unparse(d) for d in node.decorator_list)
			if not decorated:
				continue
			body = ast.get_source_segment(source(path), node) or ""
			assert any(check in body for check in ROLE_CHECKS), (
				f"{path.name}:{node.name} has no role check"
			)


def test_reading_a_group_and_writing_it_ask_the_same_question():
	"""The gate that would be easy to get half-right: `get` filtering a group
	out of the list while `save` still accepts it would be a dialog that hides
	the Frappe Cloud credentials from a customer and writes them anyway."""
	text = source(WORKSPACE)
	tree = ast.parse(text)
	bodies = {
		node.name: ast.get_source_segment(text, node) or ""
		for node in ast.walk(tree)
		if isinstance(node, ast.FunctionDef)
	}
	assert "may_read(group)" in bodies["get"]
	assert "require_group(" in bodies["save"]
	# And they share one implementation rather than two that agree today.
	assert "may_read(group)" in bodies["require_group"]


def test_the_role_check_accepts_the_owner_and_support_only():
	body = function(WORKSPACE, "require_owner")
	assert "OWNER_ROLE" in body and "SUPPORT_ROLE" in body
	assert "PermissionError" in body


def test_the_owner_role_matches_what_the_control_plane_grants():
	"""Two spellings of one role is a settings page nobody can open."""
	granted = (
		ROOT / "apps/oneapp_control/oneapp_control/entitlements/registry.py"
	).read_text()
	owner = re.search(r'OWNER_ROLE = "([^"]+)"', granted).group(1)
	assert f'OWNER_ROLE = "{owner}"' in source(WORKSPACE)


# --------------------------------------------------------------------------- #
# Joining
# --------------------------------------------------------------------------- #

def test_signup_is_not_a_setting():
	"""Frappe's signup creates an enabled Website User the control plane never
	counted a seat for — and which the next sync disables again."""
	assert "disable_signup" not in {field for _, field in written_fields()}

	body = function(WORKSPACE, "joining")
	assert "seat" in body.lower()
	assert "disabled again" in body or "disabled" in body


def test_the_sync_keeps_signup_shut():
	"""Not a default someone can turn back on in the desk either."""
	body = function(SYNC, "sync_branding")
	assert 'set_single_value("Website Settings", "disable_signup", 1)' in body


def test_branding_replaces_the_frameworks_own_name_and_nothing_else():
	"""Two failures, one either side, and this guard used to hold the first one
	in place.

	A sync that reset the customer's name every hour is worse than one that
	never set it — so it must not overwrite a chosen value. But it tested for
	*empty*, and Frappe ships these fields filled: `app_name` is "Frappe" and
	`otp_issuer_name` is "Frappe Framework". The blank never existed, the branch
	never ran, and every workspace's sign-in page said Frappe.
	"""
	body = function(SYNC, "sync_branding")
	source = SYNC.read_text()

	assert "FRAMEWORKS" in body, "the sync no longer asks what nobody has chosen"
	assert '"Frappe"' in source and '"Frappe Framework"' in source, (
		"the framework's own defaults are what 'unchosen' means here"
	)


def test_the_workspace_is_named_before_anyone_signs_in():
	"""The sign-in page is the one screen every user sees before they are
	anyone, and it carried Frappe's name and logo."""
	body = function(SYNC, "sync_branding")
	for doctype, field in (
		("Website Settings", "app_name"),
		("System Settings", "app_name"),
		("System Settings", "otp_issuer_name"),
	):
		assert f'"{doctype}", "{field}"' in body, f"{doctype}.{field} is not set"


# --------------------------------------------------------------------------- #
# Sign-in methods
# --------------------------------------------------------------------------- #

def test_sms_two_factor_is_not_offered():
	"""Frappe supports it; this platform runs no SMS gateway, so it would fail
	at the moment someone is locked out."""
	spec = source(WORKSPACE)
	assert '"OTP App", "Email"' in spec
	assert '"SMS"' not in spec


def test_the_email_link_needs_nothing_we_have_not_already_wired():
	"""`send_login_link` goes through frappe.sendmail, which on a tenant site is
	the workspace's own Cloudflare account — so offering it is honest."""
	assert "login_with_email_link" in source(WORKSPACE)
	assert "def sync_email_account" in source(SYNC)


# --------------------------------------------------------------------------- #
# Books
# --------------------------------------------------------------------------- #

def test_books_setup_calls_erpnexts_own_wizard():
	"""A hundred fixtures reimplemented is a hundred fixtures to keep in step
	with a dependency we do not control."""
	body = function(BOOKS, "_run")
	assert "from erpnext.setup.setup_wizard.setup_wizard import setup_complete" in body
	assert "setup_complete(frappe._dict(args))" in body


def test_books_setup_marks_the_site_set_up():
	"""The wizard sets this from the desk; the programmatic path does not, and
	ERPNext reads it to decide whether the site is configured."""
	body = function(BOOKS, "_run")
	assert 'set_single_value("System Settings", "setup_complete", 1)' in body


def test_books_refuses_to_run_twice():
	"""Both paths, because either running twice would insert fixtures that
	exist. `ensure_setup` reads two of the Company's fields rather than only
	counting rows — it backfills the regional settings off them — so what is
	checked is that it looks for a Company at all and returns before `_run`."""
	assert 'frappe.get_all("Company", limit=1)' in function(BOOKS, "_run")

	body = function(BOOKS, "ensure_setup")
	assert 'frappe.get_all("Company"' in body
	assert '"skipped": "already set up"' in body


def test_a_workspace_holds_exactly_one_company():
	"""A branch that wants its own ledger is its own workspace, on its own
	subscription — see docs/WORKSPACE-SETTINGS.md, One company per workspace.
	Two things hold it: setup refuses a second, and no space offers a screen
	over Company, so there is no other way to make one."""
	assert 'frappe.get_all("Company", limit=1)' in function(BOOKS, "_run")

	books_space = ROOT / "apps/oneapp_control/oneapp_control/spaces/books.py"
	declared = books_space.read_text()
	assert '"Company"' not in declared, "a Company screen would be a second company"


def test_a_workspace_set_up_before_the_regional_fix_is_repaired():
	"""ERPNext's `setup_complete` never wrote System Settings, so every
	workspace so far has books that know their country and a Regional tab that
	does not. The sync passes over a set-up workspace, so the repair has to
	happen on the way past."""
	assert "apply_regional(" in function(BOOKS, "ensure_setup")

	regional = function(BOOKS, "apply_regional")
	assert "UNCHOSEN" in regional, "a repair that overwrites is not a repair"
	for field in ("time_zone", "date_format", "number_format", "currency"):
		assert field in regional, field


def test_the_regional_backfill_leaves_the_platforms_own_settings_alone():
	"""Frappe's `update_system_settings` would have done this in one call, and
	it also sets `backup_limit` and `enable_scheduler` — which are billed and
	operational, and are in FORBIDDEN."""
	# The body, not the docstring — which names all four to say why.
	body = function(BOOKS, "apply_regional").split('"""')[2]
	assert "update_system_settings" not in body
	for ours in ("backup_limit", "enable_scheduler", "rounding_method"):
		assert ours not in body, ours


def test_everything_erpnext_is_guarded_on_it_being_installed():
	"""The control site has no ERPNext, and a workspace entitled to no
	accounting app has none of this."""
	body = source(BOOKS)
	assert "def erpnext_installed" in body
	assert "get_installed_apps" in body

	tree = ast.parse(body)
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name in ("charts", "_run", "reset"):
			segment = ast.get_source_segment(body, node)
			assert "_require_erpnext()" in segment, node.name

	# The sync's path has no session to throw at, so it checks and returns.
	assert "if not erpnext_installed():" in function(BOOKS, "ensure_setup")
	assert "if not erpnext_installed():" in function(BOOKS, "_charts_for")


def test_the_chart_list_is_read_from_erpnext():
	"""It ships as JSON inside the app, per country, and changes with it."""
	assert "get_charts_for_country" in function(BOOKS, "_charts_for")


# --------------------------------------------------------------------------- #
# The SPA renders the server's spec
# --------------------------------------------------------------------------- #

def test_the_spa_does_not_keep_its_own_copy_of_the_fields():
	"""A second list is a second thing to keep in step, and the one that drifts
	is always the one that decides what is rendered."""
	fields = source(SPA / "components/settings/SettingsFields.vue")
	assert "group.fields" in fields

	for name in ("session_expiry", "two_factor_method", "date_format"):
		assert name not in fields, f"{name} is restated in the SPA"


def test_settings_are_reachable_from_both_shells():
	"""A phone has no rail, so whatever the rail offers has to reach the More
	sheet — the same gap the console hit with its own settings.

	It used to be a row in the account menu and is a rail surface now, which is
	what makes both true at once: `useNav().surfaces` is the one declaration the
	rail and the drawer are both built from, and App.vue maps it into
	`menu-items`. Written in two places they drift, which is how one page came
	to be called "Readiness" in the rail and "Setup" in the bar.
	"""
	nav = source(SPA / "lib/shell/nav.js")
	assert "openSettings" in nav, "the rail no longer offers settings"
	assert "key: 'settings'" in nav

	app = source(SPA / "App.vue")
	assert "menu-items" in app
	# A surface that opens something over the page has no route to push, so the
	# drawer has to run its `act` — without this the phone's settings row is a
	# row that does nothing.
	assert "one.act" in app, "App.vue no longer runs a surface's own action"


def test_nobody_is_shown_a_tab_that_refuses_them():
	"""The rule that replaced "only an admin is shown the door".

	Settings used to be offered to admins alone, because the dialog's tabs were
	written into `SettingsShell.vue` and drawn for everybody — a member opening
	it would have found ten tabs and been refused by all of them. The tabs are
	declared server-side with an audience each now, so the dialog is offered to
	everybody and shows each person only what they can open.

	Which means the shell must not hard-code a tab list again. Checked by its
	absence: a `SettingsNavItem` with a literal `value` is a tab nobody gated.
	"""
	shell = source(SPA / "components/settings/SettingsShell.vue")

	assert 'v-for="tab in section.tabs"' in shell, (
		"SettingsShell no longer renders the tabs the server sent"
	)
	hard_coded = re.findall(r'<SettingsNavItem\s+value="([\w-]+)"', shell)
	assert not hard_coded, (
		"these tabs are written into the shell rather than declared in "
		f"oneapp_core/tabs.py, so nothing gates them: {hard_coded}"
	)


def test_every_panel_tab_has_a_component_and_every_component_a_tab():
	"""The two halves of one contract, which Vue will not complain about.

	`tabs.py` says a tab exists; `SettingsShell.vue`'s `PANELS` says what draws
	it. A key on one side with nothing on the other renders as an empty panel —
	silently, because an unknown component is nothing at all.
	"""
	declared = {
		key for key, kind in re.findall(
			r'"key": "([\w-]+)".*?"kind": (\w+)', TABS.read_text(), re.S)
		if kind == "PANEL"
	}
	drawn = set(re.findall(
		r"^\s+'?([\w-]+)'?: \w+Settings\w*,",
		source(SPA / "components/settings/SettingsShell.vue"), re.M))

	assert declared == drawn, (
		f"declared with no component: {sorted(declared - drawn)}; "
		f"a component with no tab: {sorted(drawn - declared)}"
	)


def test_the_admin_flag_is_not_system_manager():
	"""The workspace owner deliberately is not one (docs/ONESPACE.md, Roles), so that
	question answers about us rather than about them."""
	api = (TENANT / "api.py").read_text()
	assert "is_workspace_admin" in api
	assert '"is_admin": "System Manager" in' not in api

	session = (SPA / "lib/shell/session.js").read_text()
	assert "is_workspace_admin" in session


# --------------------------------------------------------------------------- #
# A control that does nothing
#
# Two shapes of it, both found by looking at the Sign in panel rather than at
# the code. A second factor offered while two-factor is off is a choice with no
# effect; and a group whose description told the reader to see something
# "below" that was never rendered is worse — it is a promise the panel does not
# keep, in the one place somebody goes looking for a switch that deliberately
# does not exist.
# --------------------------------------------------------------------------- #

def test_a_dependent_setting_hangs_off_one_in_its_own_group():
	"""`depends_on` is a key, not an expression — so it has to be a real key."""
	from oneapp.oneapp_core import workspace

	for group in workspace.GROUPS:
		keys = {s.key for s in group["settings"]}
		for setting in group["settings"]:
			if not setting.depends_on:
				continue
			assert setting.depends_on in keys, (
				f"{group['key']}.{setting.key} hangs off {setting.depends_on}, "
				"which is not in its group"
			)


def test_no_setting_declares_a_control_that_would_be_a_text_box():
	"""There is no Link control in this dialog, so a Link is a lie.

	`SettingsFields` has no case for one and falls through to `text` — which
	made Country, Currency, Language and the print Style boxes you had to type
	an exact spelling into, with nothing on the screen to say what the
	spellings were. The picker that would fix that cannot run here:
	`search_link` refuses a workspace owner, who is deliberately not a System
	Manager. So a closed reference list is a Select fed from the doctype
	(`workspace.reference`), and a Link is not a type this spec may declare.
	"""
	from oneapp.oneapp_core import workspace

	links = [
		f"{group['key']}.{s.key}"
		for group in workspace.GROUPS
		for s in group["settings"]
		if s.type == "Link"
	]
	assert not links, f"drawn as a text box: {links}"


def test_a_reference_list_is_read_rather_than_written_down():
	"""A copy of Frappe's currency list is wrong the day one is added."""
	body = function(WORKSPACE, "reference")
	assert "frappe.get_all" in body


def test_the_spa_draws_only_the_fields_whose_parent_is_on():
	fields = source(SPA / "components/settings/SettingsFields.vue")
	assert "depends_on" in fields, "the server declares it and nothing reads it"
	assert "depends_value" in fields, "a value dependency that is never compared"


def test_a_value_dependency_only_ever_hangs_off_a_closed_list():
	"""Comparing against a value means the parent has a known set of them.

	A dependency on a `Data` field would be a string typed one way in the spec
	and another in the box, which is a control that disappears for a reason
	nobody can see. Whether the value is one of the parent's *options* needs a
	doctype's meta and so is `scripts/check_settings.py`.
	"""
	from oneapp.oneapp_core import workspace

	for group in workspace.GROUPS:
		by_key = {s.key: s for s in group["settings"]}
		for setting in group["settings"]:
			if setting.depends_value is None:
				continue
			parent = by_key[setting.depends_on]
			assert parent.type == "Select", (
				f"{group['key']}.{setting.key} compares {parent.key}, "
				f"which is a {parent.type}"
			)


def test_a_zero_that_means_nothing_is_drawn_as_nothing():
	"""Frappe uses 0 for "not set" on several numeric columns — a font size of
	0 renders at 14, by its own test. Drawing the 0 shows a value nobody chose
	as though somebody had."""
	fields = source(SPA / "components/settings/SettingsFields.vue")
	assert "const draw" in fields
	assert "field.placeholder && !form[field.key]" in fields


def test_a_group_that_asks_for_two_columns_gets_a_layout_for_it():
	"""The count is the server's and the classes are the SPA's, and a count
	with no layout behind it is a panel that silently stays in one column."""
	from oneapp.oneapp_core import workspace

	asked = {g.get("columns", 1) for g in workspace.GROUPS}
	fields = source(SPA / "components/settings/SettingsFields.vue")
	for count in asked:
		assert f"  {count}: 'grid" in fields, f"no layout for {count} columns"

	# Tailwind reads this file for the classes it emits, so the layout has to
	# be a literal — a class assembled at runtime is a class with no CSS.
	assert "grid-cols-${" not in fields and "grid-cols-' +" not in fields


def test_a_group_note_is_rendered_where_it_is_declared():
	"""It used to be computed, returned, and dropped on the floor: `joining()`
	answered "who may have an account here" and no component read it, while the
	Sign in description told the reader to see it."""
	from oneapp.oneapp_core import workspace

	noted = [g["key"] for g in workspace.GROUPS if g.get("note")]
	assert noted, "no group carries a note; the seam is decoration"

	fields = source(SPA / "components/settings/SettingsFields.vue")
	assert "group.note" in fields


def test_no_group_description_names_something_only_the_source_has():
	"""A description is customer copy. Backticks in it are a comment that
	escaped into the product."""
	from oneapp.oneapp_core import workspace

	for group in workspace.GROUPS:
		assert "`" not in group["description"], group["key"]


# --------------------------------------------------------------------------- #
# The audit is the record
# --------------------------------------------------------------------------- #

def test_every_exposed_field_is_in_the_audit():
	audit = AUDIT.read_text()
	missing = [f for _, f in written_fields() if f not in audit]
	assert not missing, f"exposed but not recorded: {sorted(set(missing))}"


def test_every_forbidden_field_is_in_the_audit_too():
	audit = AUDIT.read_text()
	missing = [f for f in FORBIDDEN if f not in audit]
	assert not missing, f"withheld but not explained: {sorted(missing)}"


# --------------------------------------------------------------------------- #
# Books at provisioning
#
# Books is a generally available app, so a workspace that has to be told to set
# it up is a workspace that opens it to an ERPNext error about a missing default
# company. The wizard that would have created one lives on a desk the customer
# never sees, so the sync does it from what signup already answered.
# --------------------------------------------------------------------------- #

CONTROL_TENANT_API = ROOT / "apps/oneapp_control/oneapp_control/api/tenant.py"


def test_signups_answers_reach_the_tenant_site():
	"""The country came from the region they chose and the currency from the
	plan they bought. Neither is knowable from inside the site."""
	payload = function(CONTROL_TENANT_API, "sync")
	assert '"books": _books_hint(tenant)' in payload

	hint = function(CONTROL_TENANT_API, "_books_hint")
	assert '"Region", tenant.region, "country"' in hint
	assert '"Plan", tenant.plan, "currency"' in hint
	assert "tenant.tenant_name" in hint


def test_the_sync_sets_books_up():
	body = function(SYNC, "sync_books")
	assert "books.ensure_setup(hint)" in body


def test_a_failed_books_setup_does_not_fail_the_sync():
	"""A sync that stopped for it would also stop delivering entitlements,
	quotas and member changes."""
	body = function(SYNC, "sync_books")
	assert "except Exception" in body
	assert "log_error" in body


def test_setup_is_skipped_rather_than_guessed_when_too_little_is_known():
	"""Guessing a country guesses a chart of accounts and a tax regime."""
	body = function(BOOKS, "ensure_setup")
	for skip in ("no accounting app", "already set up", "not enough known"):
		assert skip in body, skip
	assert "no chart of accounts for" in body


def test_an_assumed_setup_says_so():
	"""Only the customer knows whether the chart and the financial year are
	right, and they are only cheap to change before the first entry."""
	assert "ASSUMED_KEY" in source(BOOKS)
	assert '"assumed"' in function(BOOKS, "status")
	assert '"can_reset"' in function(BOOKS, "status")

	panel = source(SPA / "components/settings/BooksSettings.vue")
	assert "status.assumed" in panel
	assert "Start over" in panel


def test_starting_over_is_refused_once_anything_is_posted():
	body = function(BOOKS, "reset")
	assert "_has_entries()" in body
	assert "frappe.throw" in body

	entries = function(BOOKS, "_has_entries")
	for doctype in ("GL Entry", "Sales Invoice", "Payment Entry"):
		assert doctype in entries, doctype


def test_both_creation_paths_run_the_same_setup():
	"""An assumed company and a typed one must be the same company."""
	assert "_run(" in function(BOOKS, "create")
	assert "_run(" in function(BOOKS, "ensure_setup")
	assert "setup_complete(frappe._dict(args))" in function(BOOKS, "_run")


def test_the_fiscal_year_follows_the_country():
	"""A workspace in the UK given a January-to-December year has wrong books
	from its first invoice."""
	spec = source(BOOKS)
	assert '"United Kingdom": ("04-01", "03-31")' in spec
	assert '"India": ("04-01", "03-31")' in spec

	body = function(BOOKS, "fiscal_year_for")
	# ERPNext's own rule: a year whose start has not arrived yet began last year.
	assert "year -= 1" in body


def test_the_fiscal_year_table_matches_erpnexts_own():
	"""Ported from `erpnext/public/js/setup_wizard.js`, which is the only place
	it exists — and which is not ours, so it can change under us.

	Skipped when ERPNext is not installed, which is every bench but a tenant's.
	"""
	candidates = list(ROOT.parent.glob("**/erpnext/public/js/setup_wizard.js"))
	if not candidates:
		pytest.skip("erpnext is not installed on this bench")

	js = candidates[0].read_text()
	block = re.search(r"erpnext\.setup\.fiscal_years = \{(.*?)\n\};", js, re.S).group(1)
	theirs = {
		re.sub(r'^"|"$', "", country): (start, end)
		for country, start, end in re.findall(
			r'\s*("?[\w ]+"?):\s*\["([\d-]+)",\s*"([\d-]+)"\]', block
		)
	}

	import ast as _ast

	spec = _ast.literal_eval(
		re.search(r"FISCAL_YEARS = (\{.*?\n\})", source(BOOKS), re.S).group(1)
	)
	assert spec == theirs, "ERPNext's fiscal-year table has changed"


def test_the_abbreviation_is_always_letters():
	"""ERPNext puts it on every account name."""
	body = function(BOOKS, "_abbreviate")
	# Not `isalpha`, which is Unicode-aware: "Ünïcode Çø" would abbreviate to
	# "ÜÇ" and land in every account name, every ledger export and every
	# filename built from one.
	assert '"A" <= c <= "Z"' in body
	assert 'or "CO"' in body
