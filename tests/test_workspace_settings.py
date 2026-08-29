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
			assert "require_owner()" in body, f"{path.name}:{node.name} has no role check"


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


def test_branding_only_ever_fills_a_blank():
	"""A sync that reset the customer's logo every hour would be worse than one
	that never set it."""
	body = function(SYNC, "sync_branding")
	assert "if not frappe.db.get_single_value" in body


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
	body = function(BOOKS, "create")
	assert "from erpnext.setup.setup_wizard.setup_wizard import setup_complete" in body
	assert "setup_complete(frappe._dict(args))" in body


def test_books_setup_marks_the_site_set_up():
	"""The wizard sets this from the desk; the programmatic path does not, and
	ERPNext reads it to decide whether the site is configured."""
	body = function(BOOKS, "create")
	assert 'set_single_value("System Settings", "setup_complete", 1)' in body


def test_books_refuses_to_run_twice():
	body = function(BOOKS, "create")
	assert 'frappe.get_all("Company", limit=1)' in body


def test_everything_erpnext_is_guarded_on_it_being_installed():
	"""The control site has no ERPNext, and a workspace entitled to no
	accounting app has none of this."""
	body = source(BOOKS)
	assert "def erpnext_installed" in body
	assert "get_installed_apps" in body

	tree = ast.parse(body)
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name in ("charts", "create"):
			segment = ast.get_source_segment(body, node)
			assert "_require_erpnext()" in segment, node.name


def test_the_chart_list_is_read_from_erpnext():
	"""It ships as JSON inside the app, per country, and changes with it."""
	assert "get_charts_for_country" in function(BOOKS, "charts")


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
	"""A phone has no rail, so the account menu's entries have to reach the More
	sheet — the same gap the console hit with its own settings."""
	assert "openSettings" in source(SPA / "components/RailAccount.vue")
	assert "menu-items" in source(SPA / "App.vue")


def test_only_a_workspace_admin_is_shown_the_door():
	"""A member who opens a dialog every field of which refuses them has been
	shown a door that does not open."""
	for path in ("components/RailAccount.vue", "App.vue"):
		assert "session.isAdmin" in source(SPA / path), path


def test_the_admin_flag_is_not_system_manager():
	"""The workspace owner deliberately is not one (DECISIONS §8), so that
	question answers about us rather than about them."""
	api = (TENANT / "api.py").read_text()
	assert "is_workspace_admin" in api
	assert '"is_admin": "System Manager" in' not in api

	session = (SPA / "lib/session.js").read_text()
	assert "is_workspace_admin" in session


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
