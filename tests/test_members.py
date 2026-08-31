"""Workspace members: the seat rules, and the sync contract both ends of it.

The control plane cannot write into a tenant's database — the signed sync is the
only channel and it runs one way — so an invite is a row here and the tenant site
reconciles its own Users against it. That split is the thing worth guarding:
either half alone looks correct and does nothing.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CUSTOMER = ROOT / "apps/oneapp_control/oneapp_control/api/customer.py"
CHECKOUT = ROOT / "apps/oneapp_control/oneapp_control/billing/checkout.py"
TENANT_API = ROOT / "apps/oneapp_control/oneapp_control/api/tenant.py"
SYNC = ROOT / "apps/oneapp/oneapp/oneapp_core/sync.py"


def source(path: Path) -> str:
    return path.read_text()


def function(path: Path, name: str, code_only: bool = False) -> str:
    tree = ast.parse(source(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            if code_only:
                # Skip the docstring: it explains what the code deliberately
                # avoids, so searching it for the avoided name always matches.
                body = [n for n in node.body if not (
                    isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                    and isinstance(n.value.value, str)
                )]
                return "\n".join(ast.get_source_segment(source(path), n) for n in body)
            return ast.get_source_segment(source(path), node)
    raise AssertionError(f"{name} is missing from {path.name}")


# --------------------------------------------------------------------------- #
# The control-plane half
# --------------------------------------------------------------------------- #

def test_members_are_a_child_table_on_tenant():
    import json

    spec = json.loads(
        (
            ROOT
            / "apps/oneapp_control/oneapp_control/control_plane/doctype/tenant_member/tenant_member.json"
        ).read_text()
    )
    assert spec["istable"] == 1
    fields = {f["fieldname"] for f in spec["fields"]}
    assert {"email", "full_name", "access", "invited_on"} <= fields

    tenant = json.loads(
        (ROOT / "apps/oneapp_control/oneapp_control/control_plane/doctype/tenant/tenant.json").read_text()
    )
    members = next(f for f in tenant["fields"] if f["fieldname"] == "members")
    assert members["fieldtype"] == "Table"
    assert members["options"] == "Tenant Member"


def test_seats_count_the_owner():
    """The owner holds a seat. Counting only the table would sell one too many."""
    body = function(CUSTOMER, "_seats")
    assert "1 + len(" in body, "the owner is not counted as a seat"


def test_seats_are_counted_from_the_member_list_not_the_reported_count():
    """`user_count` is what the site last reported; the list is what is true now.

    Enforcing against the older number lets a plan be over-subscribed in the
    window between inviting someone and the next sync.
    """
    body = function(CUSTOMER, "_seats", code_only=True)
    assert "user_count" not in body


def test_an_invite_is_refused_when_the_plan_is_full():
    body = function(CUSTOMER, "invite_member")
    assert 'seats["used"] >= seats["quota"]' in body
    assert "frappe.throw" in body


@pytest.mark.parametrize(
    "guard",
    [
        "validate_email_address",          # a typo'd address is a wasted seat
        "owns this workspace already",     # the owner is not a member row
        "is already a member",             # no duplicate seats
        "Unknown access level",            # access is a closed set
    ],
)
def test_invite_validates(guard):
    assert guard in function(CUSTOMER, "invite_member")


def test_the_owner_cannot_be_removed():
    assert "owner cannot be removed" in function(CUSTOMER, "remove_member")


def test_member_endpoints_are_owner_scoped():
    """Every one goes through the single ownership check."""
    for name in ("members", "invite_member", "remove_member"):
        assert "require_workspace(workspace)" in function(CUSTOMER, name), name


# --------------------------------------------------------------------------- #
# The sync contract
# --------------------------------------------------------------------------- #

def test_the_sync_payload_carries_members():
    body = function(TENANT_API, "sync")
    assert '"members"' in body
    for field in ('"email"', '"full_name"', '"access"'):
        assert field in body.split('"members"')[1][:400], field


def test_the_tenant_reconciles_against_the_whole_list():
    """Sent whole, not as a diff, so a removal needs nothing to remember it."""
    body = function(SYNC, "sync_members")
    assert "wanted" in body and "disabled" in body


def test_a_removed_member_is_disabled_not_deleted():
    """Frappe hangs document ownership off the User.

    Deleting the account would orphan or destroy the documents that person
    created, which belong to the workspace rather than to them.
    """
    body = function(SYNC, "sync_members")
    assert 'frappe.db.set_value("User", email, "enabled", 0)' in body
    assert "delete_doc" not in body


def test_re_inviting_someone_re_enables_their_account():
    body = function(SYNC, "sync_members")
    assert "if not user.enabled" in body


def test_reconciliation_never_touches_accounts_we_do_not_manage():
    """A site's Administrator is not a workspace member."""
    body = function(SYNC, "sync_members")
    assert '("Administrator", "Guest")' in body


def test_membership_is_marked_by_a_role_of_its_own():
    """Not by "holds one of our app roles", which looks equivalent and is not.

    A member of a workspace with no apps entitled yet holds no app roles, so
    reconciling on those disabled nobody when they were removed and they kept
    their sign-in. Found by running the reconciliation rather than by reading it.
    """
    body = function(SYNC, "sync_members")
    assert "member_role in roles" in body, "removal is not keyed to the marker role"
    assert "all_managed_roles" not in body, "still reconciling on app roles"


def test_reconciliation_refuses_to_guess_without_the_marker():
    """No marker means no safe way to tell a removed member from a site's own
    user, and guessing wrong disables someone's sign-in."""
    body = function(SYNC, "sync_members")
    assert "if not member_role:" in body


def test_the_marker_role_is_sent_and_never_revoked():
    assert "MEMBER_ROLE" in source(TENANT_API)

    registry = (
        ROOT / "apps/oneapp_control/oneapp_control/entitlements/registry.py"
    ).read_text()
    assert 'MEMBER_ROLE = "OneSpace Workspace Member"' in registry

    # sync_roles revokes any managed role that is not entitled. Neither the
    # owner nor the member role is an entitlement, so both must be excluded —
    # otherwise every member is stripped of the marker on the next sync and the
    # reconciliation stops seeing them.
    body = function(SYNC, "sync_roles")
    assert "- {owner_role, member_role}" in body


def test_everyone_in_the_workspace_holds_the_marker():
    """Including the owner, so "who is in this workspace" has one answer."""
    body = function(SYNC, "sync_owner")
    assert "member_role" in body


def test_admin_members_hold_the_owner_role_and_members_do_not():
    body = function(SYNC, "sync_members")
    assert 'member.get("access") == "Admin"' in body
    assert "_set_role(user, owner_role, wants_owner)" in body

    # And _set_role actually removes when told not to hold.
    setter = function(SYNC, "_set_role")
    assert "user.roles = [r for r in user.roles if r.role != role]" in setter


def test_members_are_reconciled_after_the_owner():
    """The owner role must exist before an Admin member can be given it, and the
    owner must not look like a removal."""
    body = function(SYNC, "sync_from_control_plane")
    assert body.index("sync_owner(") < body.index("sync_members(")
    assert 'owner"] or {}).get("email")' in body or 'owner") or {}).get("email")' in body


# --------------------------------------------------------------------------- #
# The account surface
#
# `/portal` was a second SPA with its own router and its own nav declaration.
# The account is a Space now — `entitlements/account.py` declares the screens and
# `screens/index.js` maps each to a component — so "routed and reachable" is a
# question about those two agreeing, and the rail comes free.
# --------------------------------------------------------------------------- #

ACCOUNT_SCREENS = ROOT / "apps/oneapp/frontend/src/screens/account"
SCREEN_REGISTRY = ROOT / "apps/oneapp/frontend/src/screens/index.js"


def account_screens() -> set[str]:
    """The screens the account Space declares, read without importing frappe."""
    import ast

    source = (
        ROOT / "apps/oneapp_control/oneapp_control/entitlements/account.py"
    ).read_text()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SCREENS":
            return {row[0] for row in ast.literal_eval(node.value)}
    raise AssertionError("SCREENS is gone from account.py")


def declared_and_registered(screen: str) -> None:
    assert screen in account_screens(), f"{screen} is not a screen of the account Space"
    registry = SCREEN_REGISTRY.read_text()
    assert f"'onespace-account/{screen}'" in registry, (
        f"{screen} is declared but nothing renders it"
    )


def test_the_team_screen_is_declared_and_reachable():
    declared_and_registered("people")


def test_the_page_says_an_invite_is_not_immediate():
    """It lands on the next sync. Saying so is the difference between 'slow' and
    'broken' for someone watching a colleague fail to sign in."""
    page = (ACCOUNT_SCREENS / "People.vue").read_text()
    assert "syncs" in page


# --------------------------------------------------------------------------- #
# Apps and plan
# --------------------------------------------------------------------------- #

def test_apps_separates_what_every_plan_carries_from_what_was_granted():
    """Otherwise "why do we have this?" has no answer on the page."""
    body = function(CUSTOMER, "apps")
    assert '"included"' in body
    assert "Space Entitlement" in body


def test_plans_lists_more_than_the_current_one():
    """Frappe ANDs `or_filters` onto `filters` rather than ORing the clause.

    `is_active=1` plus `name=<current>` resolved to exactly the current plan, so
    the page offered nothing to move to — nine active plans showed as one.
    """
    body = function(CUSTOMER, "plans")
    # The keyword, not the word — the comment above the fix explains the trap
    # and would otherwise match.
    assert "or_filters=" not in body, "or_filters is ANDed; it cannot express this"
    assert 'filters={"is_active": 1}' in body


def test_a_retired_plan_is_still_shown_to_whoever_is_on_it():
    body = function(CUSTOMER, "plans")
    assert "retired" in body


QUOTAS = ROOT / "apps/oneapp_control/oneapp_control/billing/quotas.py"


def test_a_plan_too_small_for_the_workspace_is_named_not_just_refused():
    """"storage" tells someone what to clear; a disabled button tells them to
    write in."""
    body = function(CUSTOMER, "plans")
    assert '"blocked_by"' in body

    blockers = function(QUOTAS, "blockers")
    for dimension in ('"storage"', '"database"', '"seats"'):
        assert dimension in blockers, dimension

    page = (ACCOUNT_SCREENS / "Plan.vue").read_text()
    assert "blocked_by" in page


def test_seat_capacity_is_measured_the_same_way_everywhere():
    """The plan page and the invite check must agree on what a seat is, or a
    plan reads as available and refuses the first invite."""
    assert "1 + len(doc.members or [])" in function(QUOTAS, "blockers")

    seats_body = function(CUSTOMER, "_seats", code_only=True)
    assert "1 + len(" in seats_body


def test_the_page_and_the_switch_run_the_same_fit_check():
    """The reason plan changes do not go through Stripe's billing portal.

    The portal cannot know our quotas, so it would sell a downgrade to a
    workspace already holding more than the smaller plan allows — and the
    customer finds out afterwards, over quota. One implementation, called from
    both, is what stops the page offering something the switch refuses and, more
    importantly, the switch accepting something the page refused.
    """
    assert "quotas.blockers" in function(CUSTOMER, "plans")
    assert "quotas.blockers" in function(CHECKOUT, "change_plan")


def test_the_portal_keeps_cards_and_cancellation():
    """Not a rejection of the portal — it is better at the things it owns."""
    page = (ACCOUNT_SCREENS / "Plan.vue").read_text()
    assert "customer.changePlan" in page, "the plan page no longer changes the plan"

    billing = (ACCOUNT_SCREENS / "Billing.vue").read_text()
    assert "billingPortal" in billing, "nothing hands the customer to Stripe any more"


@pytest.mark.parametrize("screen", ["apps", "plan"])
def test_the_new_screens_are_reachable(screen):
    declared_and_registered(screen)
