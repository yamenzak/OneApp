"""The vocabulary every doctype declaration is written in.

`f`, `section` and `column` build a field; `doctype` registers one into
`DOCTYPES`, which `gen_doctypes.build` then turns into JSON. `HANDLED_SPEC_KEYS`
is every key `build` understands — a key added to a `doctype()` call without
being added here is a hard error rather than a silent omission.
"""

import os


APPS = {
    # key -> (app package dir, default module directory, default module name)
    #
    # OneAdmin is one module because it is one subject: the control plane. The
    # tenant app is not — it is OneSpace and the products that sit in it — so
    # its default is the platform module and anything belonging to a product
    # says so with `module=`, below.
    "control": ("oneapp_control", "control_plane", "Control Plane"),
    "tenant": ("oneapp", "onespace", "OneSpace"),
}

#: Frappe module name -> the directory beside `modules.txt` that holds it.
#: Frappe's own rule is `scrub(module)`, and every one of ours is that already;
#: this exists so a name with a space in it would still resolve rather than
#: quietly writing a doctype into a directory the framework never reads.
MODULE_DIRS = {
    "OneSpace": "onespace",
    "OneDoc": "onedoc",
    "OneSheet": "onesheet",
    "OneCode": "onecode",
    "OneStorage": "onestorage",
    "OneMail": "onemail",
    "OneCalendar": "onecalendar",
    "OneLegal": "onelegal",
    "OneMobility": "onemobility",
    "Control Plane": "control_plane",
}


APPS_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "apps")


STAMP = "2026-08-29 00:00:00.000000"


MANAGER_PERMS = [
    {
        "create": 1, "delete": 1, "email": 1, "export": 1, "print": 1, "read": 1,
        "report": 1, "role": "System Manager", "share": 1, "write": 1,
    }
]


READONLY_PERMS = [
    {"read": 1, "report": 1, "export": 1, "role": "System Manager"}
]


def f(fieldname, fieldtype="Data", label=None, **kw):
    d = {"fieldname": fieldname, "fieldtype": fieldtype,
         "label": label if label is not None else fieldname.replace("_", " ").title()}
    d.update(kw)
    return d


def section(name, label=""):
    return {"fieldname": name, "fieldtype": "Section Break", "label": label}


def column(name):
    return {"fieldname": name, "fieldtype": "Column Break"}


# Both operator-granted quota fields say the same thing, so they say it once.
GRANTED_GB = (
    "Extra {resource} granted by an operator, on top of the plan and any add-ons. "
    "Never billed and never expires: this is the goodwill lever, not a product."
)


DOCTYPES = {}


def doctype(name, fields, autoname=None, perms=None, app="control", **kw):
    DOCTYPES[name] = dict(name=name, fields=fields, autoname=autoname,
                          perms=perms or MANAGER_PERMS, app=app, **kw)


# Every key build() understands. Adding one to a doctype() call without adding
# it here is a hard error rather than a silent omission.
HANDLED_SPEC_KEYS = {
    "name", "fields", "perms", "autoname", "title_field",
    "allow_rename", "issingle", "istable", "app", "track_changes",
    "in_create", "states", "search_fields", "module", "is_virtual",
}
