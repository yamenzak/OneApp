"""Every declared setting, checked against the doctype it actually writes.

The half `tests/test_settings_tabs.py` cannot do: whether the `type` a setting
declares matches the Frappe fieldtype of the column behind it. That needs a
doctype's meta, so it needs a bench.

    ONEAPP_SITE=space.localhost ONEAPP_PORT=8001 scripts/dev.sh run scripts/check_settings.py

Worth running after touching `workspace.GROUPS` or `me.MINE`, and after a Frappe
upgrade — a field that moved doctype, or changed from Data to Float, leaves a
form that keeps working and quietly writes the wrong shape. It found four the
day it was written: the favicon declared as an image where Frappe's own field is
a plain attach, both custom page sizes declared as text over Float columns, and
a print font size as an Int, which cannot be 9.5.

A few pairs differ on purpose and are listed in `NARROWED`, with the reason.
"""
import frappe
from oneapp.oneapp_core import workspace, me

#: (ours, Frappe's) pairs that differ on purpose.
NARROWED = {
    # We supply the options rather than search a doctype the owner's role
    # cannot read: `search_link` refuses a workspace owner, who is deliberately
    # not a System Manager.
    ("Select", "Link"),
    # A closed list is a picker; an autocomplete over the whole tz database is
    # a text box that guesses.
    ("Select", "Autocomplete"),
    # A Select whose options Frappe fills in at runtime rather than on the
    # doctype, so its meta says Data.
    ("Select", "Data"),
}

print("=== workspace settings ===")
bad = []
for group in workspace.GROUPS:
    for s in group["settings"]:
        if not s.targets:
            # A setting with no Frappe field behind it — the brand accent, kept
            # as a site default. There is no fieldtype to disagree with, so
            # there is nothing here to check; say so rather than skip in
            # silence, which is how a setting with a *lost* target would hide.
            print(f"   {group['key']}.{s.key:28} ours={s.type:14} "
                  f"default={s.default_key}")
            continue
        for doctype, field in s.targets:
            if not frappe.db.exists("DocType", doctype):
                bad.append(f"{group['key']}.{s.key}: no doctype {doctype}")
                continue
            df = frappe.get_meta(doctype).get_field(field)
            if not df:
                bad.append(f"{group['key']}.{s.key}: {doctype} has no field {field}")
                continue
            ours, theirs = s.type, df.fieldtype
            same = ours == theirs
            # Deliberate narrowings we accept.
            ok = same or (ours, theirs) in NARROWED
            mark = "  " if ok else "!!"
            print(f"{mark} {group['key']}.{s.key:28} ours={ours:14} frappe={theirs:14} {doctype}.{field}")
            if not ok:
                bad.append(f"{group['key']}.{s.key}: ours {ours}, frappe {theirs}")

print("\n=== profile (me.MINE) ===")
meta = frappe.get_meta("User")
for key, spec in me.MINE.items():
    df = meta.get_field(key)
    ours, theirs = spec["type"], (df.fieldtype if df else "MISSING")
    mark = "  " if (ours == theirs or (ours, theirs) in NARROWED) else "!!"
    print(f"{mark} {key:16} ours={ours:14} frappe={theirs}")

print("\n=== value dependencies ===")
for group in workspace.GROUPS:
    known = {s.key: s for s in group["settings"]}
    for s in group["settings"]:
        if s.depends_value is None:
            continue
        parent = known[s.depends_on]
        options = workspace._options_for(parent) or []
        ok = s.depends_value in options
        print(f"{'  ' if ok else '!!'} {group['key']}.{s.key:24} shown when "
              f"{parent.key} == {s.depends_value!r}")
        if not ok:
            bad.append(
                f"{group['key']}.{s.key}: {parent.key} has no option "
                f"{s.depends_value!r} — the field can never be drawn"
            )

print("\n=== summary ===")
for line in bad:
    print(" ", line)
print(f"{len(bad)} mismatch(es)")
