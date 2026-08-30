"""The press-backed operator surface.

Two things are being guarded, and they pull in different directions:

* A panel must **degrade**. Frappe Cloud being slow or unreachable should grey
  out one panel, not take down the page an operator opened to find out why a
  site is unhappy.
* A support login must **not** degrade. It is break-glass access to someone
  else's data, so it refuses without a reason and records itself before the
  session is handed over.
"""

import ast
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps/oneapp_control/oneapp_control/api/admin.py"
CLIENT = ROOT / "apps/oneapp_control/oneapp_control/press/client.py"
SETTINGS = (
    ROOT
    / "apps/oneapp_control/oneapp_control/control_plane/doctype/onespace_control_settings/onespace_control_settings.py"
)
PAGE = ROOT / "apps/oneapp_control/frontend/src/pages/Tenant.vue"


def function(path: Path, name: str) -> str:
    source = path.read_text()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node)
    raise AssertionError(f"{name} is missing from {path.name}")


# --------------------------------------------------------------------------- #
# The API host that keeps the credential
#
# frappecloud.com 308-redirects to cloud.frappe.io, and `requests` drops the
# Authorization header across the redirect. The second request arrives
# unauthenticated and press answers "Function … is not whitelisted", which reads
# as a problem with the API key rather than with the hostname. Half an hour of
# looking at key scopes is the usual price; it cost that here.
# --------------------------------------------------------------------------- #

def test_a_redirecting_press_host_is_refused_on_save():
    body = function(SETTINGS, "validate_press_url")
    assert "REDIRECTING_PRESS_HOSTS" in body
    assert "frappe.throw" in body

    module = SETTINGS.read_text()
    assert '"frappecloud.com"' in module, "the redirecting host is not listed"
    assert "cloud.frappe.io" in module, "the canonical host is not named"


def test_the_readiness_page_checks_the_host_separately():
    """Separately from the credentials, so the answer names the real problem."""
    setup = (ROOT / "apps/oneapp_control/oneapp_control/api/setup.py").read_text()
    assert '"key": "press_host"' in setup
    assert "_press_host_ok" in setup


def test_every_default_points_at_the_canonical_host():
    for path in (
        ROOT / "apps/oneapp_control/oneapp_control/install.py",
        ROOT / "apps/oneapp_control/oneapp_control/press/client.py",
        ROOT / "scripts/live.py",
        ROOT / "scripts/bootstrap_site.py",
        ROOT / "scripts/gen_doctypes.py",
    ):
        text = path.read_text()
        if "frappe.io" not in text and "frappecloud" not in text:
            continue
        assert "cloud.frappe.io" in text, f"{path.name} names a different host"
        assert not re.search(r'["\']https://(www\.)?frappecloud\.com', text), (
            f"{path.name} defaults to the redirecting host"
        )


# --------------------------------------------------------------------------- #
# Panels degrade
# --------------------------------------------------------------------------- #

READ_ENDPOINTS = ("site_state", "site_jobs", "site_backups", "site_domains")


@pytest.mark.parametrize("name", READ_ENDPOINTS)
def test_reads_report_a_press_failure_instead_of_raising(name):
    body = function(ADMIN, name)
    assert "_degrade(" in body, f"{name} does not degrade"


def test_degrade_reports_the_reason_rather_than_an_empty_result():
    """An empty list for an unreachable server reads as "there is nothing here"."""
    body = function(ADMIN, "_degrade")
    assert "return default, str(e)" in body
    assert "PressError" in body


@pytest.mark.parametrize("name", READ_ENDPOINTS)
def test_reads_say_so_when_there_is_no_site_yet(name):
    body = function(ADMIN, name)
    assert "no site yet" in body


def test_reads_get_a_shorter_timeout_than_writes():
    """30 seconds of spinner is worse than an answer after eight.

    Provisioning genuinely needs the long budget — cutting it short would
    abandon a site press is already creating — so the two are separate.
    """
    client = CLIENT.read_text()
    assert re.search(r"^READ_TIMEOUT = (\d+)", client, re.M), "no read budget"
    read = int(re.search(r"^READ_TIMEOUT = (\d+)", client, re.M).group(1))
    write = int(re.search(r"^TIMEOUT = (\d+)", client, re.M).group(1))
    assert read < write, f"reads ({read}s) are not quicker than writes ({write}s)"

    for method in ("get_site", "backups", "site_jobs", "site_domains"):
        assert "READ_TIMEOUT" in function(CLIENT, method), f"{method} uses the write budget"


def test_the_panel_names_the_failure():
    panel = (ROOT / "apps/oneapp_control/frontend/src/components/PressPanel.vue").read_text()
    assert "did not answer" in panel
    assert "retry" in panel


def test_panels_load_when_opened_not_all_at_once():
    """Five press calls on page load make the page as slow as the slowest."""
    press = (ROOT / "apps/oneapp_control/frontend/src/lib/press.js").read_text()
    assert "state.loaded" in press and "tabValue" in press


# --------------------------------------------------------------------------- #
# Support login
# --------------------------------------------------------------------------- #

def test_a_support_login_needs_a_reason():
    body = function(ADMIN, "support_login")
    assert "Say why you need to sign in" in body


def test_the_audit_row_is_written_before_the_session_is_handed_over():
    """Written afterwards, the ones worth having are exactly the ones lost."""
    body = function(ADMIN, "support_login")
    assert body.index('"doctype": "Support Login"') < body.index("login_sid("), (
        "the audit row is written after the login"
    )
    assert body.index("frappe.db.commit()") < body.index("login_sid("), (
        "the audit row is not committed before the login"
    )


def test_a_failed_attempt_is_distinguishable_from_an_entry():
    body = function(ADMIN, "support_login")
    assert 'record.db_set("succeeded", 1)' in body
    assert body.index("login_sid(") < body.index('db_set("succeeded"')

    spec = json.loads(
        (
            ROOT
            / "apps/oneapp_control/oneapp_control/control_plane/doctype/support_login/support_login.json"
        ).read_text()
    )
    fields = {f["fieldname"]: f for f in spec["fields"]}
    assert "succeeded" in fields
    assert fields["reason"].get("reqd") == 1, "a reason is not required"
    assert fields["operator"].get("reqd") == 1


def test_support_lands_in_the_workspace_not_the_desk():
    """The desk is not part of this product; putting an operator in it would
    make it part of theirs, and support should see what the customer sees."""
    body = function(ADMIN, "support_login")
    assert "/one?sid=" in body
    assert "/app?sid=" not in body


def test_every_press_endpoint_is_operator_only():
    source = ADMIN.read_text()
    for name in READ_ENDPOINTS + ("take_backup", "backup_download", "set_primary_domain",
                                  "remove_domain", "support_login", "support_logins"):
        assert "_require_manager()" in function(ADMIN, name), name


def test_the_primary_domain_cannot_be_removed_out_from_under_the_links_we_build():
    body = function(ADMIN, "remove_domain")
    assert "primary_domain" in body and "frappe.throw" in body


def test_changing_the_primary_domain_updates_what_we_link_to():
    body = function(ADMIN, "set_primary_domain")
    assert 'db_set("primary_domain"' in body


# --------------------------------------------------------------------------- #
# The page
# --------------------------------------------------------------------------- #

def test_the_page_shows_both_views_and_marks_a_disagreement():
    page = PAGE.read_text()
    assert "control_plane" in page or "ours" in page
    assert "mismatch" in page, "a disagreement between press and us is not marked"


def test_only_an_offsite_backup_offers_a_download():
    """A local backup lives on the server; press has nothing to hand out."""
    page = PAGE.read_text()
    assert 'v-if="row.offsite"' in page
