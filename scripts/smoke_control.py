"""Integration smoke tests for the control plane.

Exercises the parts that only misbehave against a real database — row locking on
reserve, the append-only guard, grant consumption order, allocator behaviour and
provisioning idempotency. The bench-free suite in tests/ cannot reach any of it.

Run from a bench's sites directory against a site with oneapp_control installed:

    cd <bench>/sites
    ../env/bin/python ../../OneSpace/scripts/smoke_control.py [site]

Writes to the site, so point it at a development site, never production.
"""

import os
import sys

import frappe

SITE = sys.argv[1] if len(sys.argv) > 1 else "control.localhost"
SITES_PATH = os.environ.get("SITES_PATH", ".")

frappe.init(site=SITE, sites_path=SITES_PATH)
frappe.connect()
frappe.set_user("Administrator")
frappe.flags.in_test = True

ok, fail = [], []


def check(name, fn):
    try:
        fn()
        ok.append(name)
    except Exception as e:
        fail.append((name, f"{type(e).__name__}: {e}"))


# ---------------------------------------------------------------- shard
def make_shard():
    if not frappe.db.exists("Shard", "local-1"):
        frappe.get_doc({
            "doctype": "Shard", "shard_name": "local-1", "status": "Active",
            "deploy_ring": "Fleet", "press_release_group": "rg-1",
            "domain": "4dl.app", "capacity_tenants": 5, "accepts_new_tenants": 1,
        }).insert()
    frappe.db.commit()

check("shard creates", make_shard)


def allocator_picks():
    from oneapp_control.control_plane.doctype.shard.shard import pick_shard
    assert pick_shard() == "local-1", pick_shard()

check("allocator picks a shard with headroom", allocator_picks)


def canary_excluded():
    from oneapp_control.control_plane.doctype.shard.shard import pick_shard
    frappe.db.set_value("Shard", "local-1", "deploy_ring", "Canary")
    frappe.db.commit()
    assert pick_shard() is None, "canary must not take new tenants"
    frappe.db.set_value("Shard", "local-1", "deploy_ring", "Fleet")
    frappe.db.commit()

check("canary ring excluded from allocation", canary_excluded)


# ---------------------------------------------------------------- plan
def make_plan():
    if not frappe.db.exists("Plan", "personal-starter"):
        frappe.get_doc({
            "doctype": "Plan", "plan_code": "personal-starter",
            "plan_name": "Personal", "audience": "Personal",
            "price_monthly": 22, "storage_gb": 10, "max_users": 3,
            "monthly_credit_grant": 2000,
        }).insert()
    frappe.db.commit()

check("plan creates", make_plan)


# ---------------------------------------------------------------- tenant
def make_tenant():
    if frappe.db.exists("Tenant", "acme"):
        frappe.delete_doc("Tenant", "acme", force=True)
    t = frappe.get_doc({
        "doctype": "Tenant", "tenant_slug": "acme", "tenant_name": "Acme Ltd",
        "owner_email": "ops@acme.test", "plan": "personal-starter",
        "status": "Provisioning",
    }).insert()
    frappe.db.commit()
    assert t.name == "acme"
    assert t.site_name == "acme.4dl.app", t.site_name
    assert t.shard == "local-1"
    assert t.signing_secret() and len(t.signing_secret()) == 64

check("tenant derives site name, shard and secret", make_tenant)


def quota_from_plan():
    t = frappe.get_doc("Tenant", "acme")
    assert t.storage_quota_bytes == 10 * 1024**3, t.storage_quota_bytes
    assert t.max_users == 3

check("tenant quota resolves from plan", quota_from_plan)


def reserved_slug_blocked():
    try:
        frappe.get_doc({
            "doctype": "Tenant", "tenant_slug": "admin", "tenant_name": "X",
            "owner_email": "a@b.test",
        }).insert()
    except frappe.ValidationError:
        return
    raise AssertionError("reserved slug 'admin' was accepted")

check("reserved slug rejected at insert", reserved_slug_blocked)


def slug_immutable():
    t = frappe.get_doc("Tenant", "acme")
    t.tenant_slug = "acme2"
    try:
        t.save()
    except frappe.ValidationError:
        return
    raise AssertionError("slug was allowed to change")

check("slug immutable after creation", slug_immutable)


def shard_count_tracked():
    frappe.db.commit()
    count = frappe.db.get_value("Shard", "local-1", "tenant_count")
    assert count >= 1, count

check("shard tenant_count maintained", shard_count_tracked)


# ---------------------------------------------------------------- credits
def ledger_balance():
    from oneapp_control.credits import ledger
    from frappe.utils import add_days, getdate

    frappe.db.sql("DELETE FROM `tabCredit Ledger Entry` WHERE tenant='acme'")
    frappe.db.commit()

    ledger.post_entry("acme", "Grant", 100, expires_on=add_days(getdate(), 30))
    ledger.post_entry("acme", "Purchase", 50)
    frappe.db.commit()
    assert ledger.balance("acme") == 150, ledger.balance("acme")

check("balance sums grants and purchases", ledger_balance)


def expired_grant_excluded():
    from oneapp_control.credits import ledger
    from frappe.utils import add_days, getdate

    ledger.post_entry("acme", "Grant", 999, expires_on=add_days(getdate(), -1))
    frappe.db.commit()
    assert ledger.balance("acme") == 150, ledger.balance("acme")

check("expired grant excluded from balance", expired_grant_excluded)


def append_only():
    entry = frappe.get_all("Credit Ledger Entry", filters={"tenant": "acme"}, limit=1)[0]
    doc = frappe.get_doc("Credit Ledger Entry", entry.name)
    doc.credits = 1_000_000
    try:
        doc.save()
    except frappe.ValidationError:
        return
    raise AssertionError("ledger entry was editable")

check("ledger entries are immutable", append_only)


def sign_enforced():
    from oneapp_control.credits import ledger
    try:
        ledger.post_entry("acme", "Spend", 50)  # positive Spend
    except frappe.ValidationError:
        return
    raise AssertionError("positive Spend accepted")

check("entry sign must match entry type", sign_enforced)


def spend_burns_expiring_first():
    from oneapp_control.credits import ledger
    from frappe.utils import add_days, getdate

    frappe.db.sql("DELETE FROM `tabCredit Ledger Entry` WHERE tenant='acme'")
    frappe.db.sql("DELETE FROM `tabCredit Reservation` WHERE tenant='acme'")
    frappe.db.commit()

    pack = ledger.post_entry("acme", "Purchase", 100)              # never expires
    grant = ledger.post_entry("acme", "Grant", 40,
                              expires_on=add_days(getdate(), 5))   # expires soon
    frappe.db.commit()

    ledger.spend("acme", 30, "ai:test")
    frappe.db.commit()

    spends = frappe.get_all("Credit Ledger Entry",
                            filters={"tenant": "acme", "entry_type": "Spend"},
                            fields=["consumed_from", "credits"])
    assert len(spends) == 1, spends
    assert spends[0].consumed_from == grant.name, \
        f"spent from {spends[0].consumed_from}, expected expiring grant {grant.name}"
    assert ledger.balance("acme") == 110, ledger.balance("acme")

check("spend consumes soonest-expiring grant first", spend_burns_expiring_first)


def spend_spills_over():
    from oneapp_control.credits import ledger
    ledger.spend("acme", 50, "ai:test2")   # 10 left in grant, rest from pack
    frappe.db.commit()
    assert ledger.balance("acme") == 60, ledger.balance("acme")

check("spend spills into the pack when a grant runs out", spend_spills_over)


def overdraw_refused():
    from oneapp_control.credits import ledger
    try:
        ledger.spend("acme", 10_000, "ai:toomuch")
    except ledger.InsufficientCredits:
        frappe.db.rollback()
        return
    raise AssertionError("overdraw was allowed")

check("overdraw refused", overdraw_refused)


def reserve_holds_credits():
    from oneapp_control.credits import ledger
    balance_before = ledger.balance("acme")
    available_before = ledger.available("acme")

    res = ledger.reserve("acme", 20, "ai:chat")
    frappe.db.commit()

    assert ledger.available("acme") == available_before - 20, ledger.available("acme")
    assert ledger.balance("acme") == balance_before, "reserve must not spend"

    res.release("test cleanup")
    frappe.db.commit()

check("reserve reduces available but not balance", reserve_holds_credits)


def commit_spends_actual():
    from oneapp_control.credits import ledger
    before = ledger.balance("acme")
    res = ledger.reserve("acme", 20, "ai:chat")
    frappe.db.commit()
    res.commit_usage(7, "used less than reserved")
    frappe.db.commit()
    assert ledger.balance("acme") == before - 7, ledger.balance("acme")
    assert res.status == "Committed"

check("commit charges actual usage, not the reservation", commit_spends_actual)


def release_charges_nothing():
    from oneapp_control.credits import ledger
    balance_before = ledger.balance("acme")
    available_before = ledger.available("acme")

    res = ledger.reserve("acme", 25, "ai:failed")
    frappe.db.commit()
    assert ledger.available("acme") == available_before - 25

    res.release("provider failed")
    frappe.db.commit()
    assert ledger.balance("acme") == balance_before, "release must not charge"
    assert ledger.available("acme") == available_before, "hold must be returned"

check("release returns the hold without charging", release_charges_nothing)


def reserve_refuses_overdraw():
    from oneapp_control.credits import ledger
    try:
        ledger.reserve("acme", 99_999, "ai:huge")
    except ledger.InsufficientCredits:
        frappe.db.rollback()
        return
    raise AssertionError("reserve allowed an overdraw")

check("reserve refuses to overdraw", reserve_refuses_overdraw)


# ---------------------------------------------------------------- entitlements
def entitlements():
    from oneapp_control.entitlements import registry

    for code, avail in (("core", "General"), ("bespoke", "Restricted")):
        if not frappe.db.exists("OneSpace Space", code):
            frappe.get_doc({
                "doctype": "OneSpace Space", "space_code": code, "space_label": code.title(),
                "module": f"Mod{code.title()}", "role_name": f"OneSpace {code.title()}",
                "availability": avail, "is_active": 1,
            }).insert()
    frappe.db.commit()

    codes = {a["space_code"] for a in registry.spaces_for_tenant("acme")}
    assert codes == {"core"}, codes

    registry.grant("acme", "bespoke")
    frappe.db.commit()
    codes = {a["space_code"] for a in registry.spaces_for_tenant("acme")}
    assert codes == {"core", "bespoke"}, codes

    assert set(registry.entitled_roles("acme")) == {"OneSpace Core", "OneSpace Bespoke"}

    registry.revoke("acme", "bespoke")
    frappe.db.commit()
    codes = {a["space_code"] for a in registry.spaces_for_tenant("acme")}
    assert codes == {"core"}, codes

check("restricted apps appear only when entitled", entitlements)


def duplicate_entitlement_blocked():
    registry_doc = frappe.get_doc({
        "doctype": "Space Entitlement", "tenant": "acme", "app": "bespoke", "enabled": 1,
    })
    try:
        registry_doc.insert()
    except frappe.ValidationError:
        return
    raise AssertionError("duplicate entitlement accepted")

check("duplicate entitlement rejected", duplicate_entitlement_blocked)


# ---------------------------------------------------------------- provisioning
def job_idempotency():
    from oneapp_control.provisioning import runner
    frappe.db.sql("DELETE FROM `tabProvisioning Job` WHERE tenant='acme'")
    frappe.db.commit()

    a = runner.enqueue("acme", "Create Site")
    b = runner.enqueue("acme", "Create Site")
    frappe.db.commit()
    assert a.name == b.name, f"double enqueue created two jobs: {a.name} {b.name}"

check("duplicate provisioning request returns the same job", job_idempotency)


def failed_job_can_be_retried():
    from oneapp_control.provisioning import runner
    job = frappe.get_doc("Provisioning Job", {"tenant": "acme"})
    job.fail("simulated")
    frappe.db.commit()
    assert job.state == "Failed"
    assert frappe.db.get_value("Tenant", "acme", "status") == "Failed"

    again = runner.enqueue("acme", "Create Site")
    frappe.db.commit()
    assert again.name == job.name
    assert frappe.db.get_value("Provisioning Job", job.name, "state") == "Requested"

check("failed job is reset rather than duplicated on retry", failed_job_can_be_retried)


def payload_round_trips():
    from oneapp_control.provisioning import runner
    job = runner.enqueue("acme", "Add Domain", {"domain": "erp.acme.test"},
                         idempotency_key="dom:acme:1")
    frappe.db.commit()
    assert job.parsed_payload() == {"domain": "erp.acme.test"}

check("job payload round trips", payload_round_trips)


# ---------------------------------------------------------------- report
print()
for name in ok:
    print(f"  PASS  {name}")
for name, err in fail:
    print(f"  FAIL  {name}\n          {err}")
print(f"\n{len(ok)} passed, {len(fail)} failed")

frappe.destroy()
sys.exit(1 if fail else 0)
