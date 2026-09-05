"""A sheet fills a document's child table.

The stage everything else exists for. `docs/SHEETS.md` §3 is the argument;
this is it, and the shape is RUA's because RUA's was right:

    a named range is the contract  →  the first row names the columns
    →  a header may carry its unit  →  the rows become child rows
    →  and after that the document is the record.

Everything outside the named range is the estimator's working — lookup tables,
scratch columns, a note to themselves — and none of it is anybody else's
business. That is what makes a spreadsheet usable as a spreadsheet rather than
as a form with grid lines.

`value` and never `raw`, throughout. The server does not evaluate formulas
(`docs/SHEETS.md` §1); the browser wrote down what each one came to, and a
number is what a child row wants anyway.
"""

import re

import frappe
from frappe import _

from .reading import _mine, read_range

# `Width [mm]` → the field is `Width` and every value gains ` mm`.
#
# RUA's, kept because it earns its keep: one estimator template then serves a
# job quoted in millimetres and a job quoted in metres, without a second column
# or a second template. The unit is presentation — it is appended to a text
# field, never parsed back out — which is why this is safe.
UNIT = re.compile(r"\s*\[(.*?)\]\s*$")

# What a number looks like once a person has been typing in a spreadsheet.
MONEY = re.compile(r"[^\d.\-]")


def header(text: str) -> tuple[str, str]:
    """`Width [mm]` → `("Width", "mm")`. `Qty` → `("Qty", "")`."""
    text = str(text or "").strip()
    found = UNIT.search(text)
    if not found:
        return text, ""
    return UNIT.sub("", text).strip(), found.group(1).strip()


def number(value) -> float:
    """A cell's value as a number, forgiving what a spreadsheet allows.

    `1,234.50`, `AED 1,234.50` and `1234.5` are the same number, because all
    three are things people type and all three arrive here as strings when the
    cell was formatted rather than computed.
    """
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = MONEY.sub("", str(value))
    try:
        return float(cleaned) if cleaned not in ("", "-", ".", "-.") else 0.0
    except ValueError:
        return 0.0


@frappe.whitelist(methods=["GET"])
def preview(sheet: str, label: str) -> dict:
    """What a pull would bring in, before it brings it in.

    A read-back writes over a document's lines, and the one thing somebody
    needs before that is to see what is about to land. Same code path as the
    pull, so the preview cannot be right while the pull is wrong.
    """
    _mine(sheet)
    block = read_range(sheet, label=label)
    rows = block["values"]
    if not rows:
        return {"headers": [], "rows": [], "count": 0}

    headers = [header(cell) for cell in rows[0]]
    body = [row for row in rows[1:] if any(cell not in (None, "") for cell in row)]

    return {
        "headers": [{"field": name, "unit": unit} for name, unit in headers],
        "rows": body[:50],
        "count": len(body),
        "ref": block["ref"],
        "tab": block["tab"],
    }


@frappe.whitelist(methods=["POST"])
def pull(sheet: str, label: str, doctype: str, docname: str, into: str,
         mapping: str | dict = "") -> dict:
    """Read the named range and replace a document's child table with it.

    Replace and not append. A pull is "the sheet is the truth now", and an
    append would silently double a quotation on a second press — which is the
    mistake this shape exists to make impossible.

    `mapping` is `{header: fieldname}` and is data rather than code, for the
    same reason `importer.py` is an engine and not a script: the next document
    that wants this is a manifest entry, not a module. A header with no mapping
    falls back to the field whose label or fieldname it matches, so a template
    written to match the doctype needs no mapping at all.

    Refused once the table is locked. `lock` is what RUA's lock did: after it,
    the document is the record and the sheet is history, and a pull that went
    through anyway would be the sheet quietly overwriting a quotation somebody
    has since corrected by hand.
    """
    doc = _mine(sheet)

    target = frappe.get_doc(doctype, docname)
    target.check_permission("write")

    standing = _feed(doctype, docname, into)
    if standing and standing.status == LOCKED:
        frappe.throw(
            _("These rows are locked. Unlock them first if the sheet should "
              "replace them again."),
            frappe.ValidationError,
        )

    field = target.meta.get_field(into)
    if not field or field.fieldtype not in ("Table", "Table MultiSelect"):
        frappe.throw(_("A {0} has no rows called {1} to fill.").format(doctype, into))

    block = read_range(sheet, label=label)
    rows = block["values"]
    if not rows:
        frappe.throw(_("The range {0} is empty.").format(label))

    wanted = frappe.parse_json(mapping) if isinstance(mapping, str) and mapping else (mapping or {})
    columns = _columns(rows[0], field.options, wanted)

    body = [row for row in rows[1:] if any(cell not in (None, "") for cell in row)]

    target.set(into, [])
    for row in body:
        target.append(into, _child(row, columns))

    target.save()

    left_out = [c["header"] for c in columns if not c["fieldname"]]
    record = _remember(standing, {
        "reference_doctype": doctype,
        "reference_name": docname,
        "into": into,
        "sheet": sheet,
        "sheet_title": doc.file_name,
        "label": label,
        "filled": len(body),
        "skipped": ", ".join(left_out),
        "status": FOLLOWING,
        "pulled_on": frappe.utils.now(),
        "pulled_by": frappe.session.user,
    })

    return {
        "filled": len(body),
        "into": into,
        "columns": [c for c in columns if c["fieldname"]],
        "skipped": left_out,
        "feed": record,
    }


# --------------------------------------------------------------------------- #
# Where a document's rows came from
#
# One row per (document, child table), because a table is fed by one range at a
# time and a second pull replaces its rows — so it replaces the record of them
# too. Kept as its own doctype rather than columns on the document, because the
# document is somebody else's doctype and this product does not add fields to
# Frappe's Quotation to say where it was filled from.
# --------------------------------------------------------------------------- #

FOLLOWING = "Following"
LOCKED = "Locked"

FEED_FIELDS = [
    "name", "reference_doctype", "reference_name", "into", "sheet",
    "sheet_title", "label", "filled", "skipped", "status",
    "pulled_on", "pulled_by", "locked_on", "locked_by",
]


def _feed(doctype: str, docname: str, into: str):
    """The standing feed for one table, or nothing."""
    found = frappe.get_all(
        "Sheet Feed",
        filters={"reference_doctype": doctype, "reference_name": docname, "into": into},
        fields=FEED_FIELDS, limit_page_length=1,
    )
    return frappe._dict(found[0]) if found else None


def _remember(standing, values: dict) -> dict:
    """Write the feed row, replacing the one that was there."""
    if standing:
        frappe.db.set_value("Sheet Feed", standing.name, values, update_modified=True)
        return _with_freshness({**dict(standing), **values})
    made = frappe.get_doc({"doctype": "Sheet Feed", **values}).insert(ignore_permissions=True)
    return _with_freshness({field: made.get(field) for field in FEED_FIELDS})


@frappe.whitelist(methods=["GET"])
def feeds(doctype: str, docname: str) -> list[dict]:
    """Every table on this document that was filled from a sheet.

    Permission is the *document's*, asked once. `Sheet Feed` has no rules of
    its own and must never be asked for any: a row saying "this quotation was
    filled from that estimator" is as private as the quotation.
    """
    if not frappe.has_permission(doctype, "read", doc=docname):
        frappe.throw(_("You cannot read that record."), frappe.PermissionError)

    found = frappe.get_all(
        "Sheet Feed",
        filters={"reference_doctype": doctype, "reference_name": docname},
        fields=FEED_FIELDS, order_by="into asc", limit_page_length=50,
    )
    return [_with_freshness(row) for row in found]


def _with_freshness(row: dict) -> dict:
    """Whether the sheet has moved on since these rows were taken from it.

    Nothing pushes. A sheet does not update a document — somebody presses Fill
    again — and that is the design rather than a gap: a quotation is a
    commitment, and a spreadsheet that could reprice one after it was sent
    would make locking the thing you must remember rather than the thing you
    choose. What was missing was only *finding out*, which is this.

    One comparison and no new storage: `File.modified`, which `writing._touch`
    stamps on every cell written, against when the pull was taken. Renaming or
    moving the sheet moves that timestamp too, so this occasionally says
    "changed" when only the name did. That is the safe direction to be wrong
    in — it sends somebody to look — and the alternative is a column on `File`
    to say what its own `modified` already nearly says.
    """
    when = frappe.db.get_value("File", row.get("sheet"), "modified")
    taken = row.get("pulled_on")

    # Both sides through `get_datetime`, because one of these is a string and
    # the other is not depending on where the row came from — the database
    # hands back a datetime, and a row just written carries the `now()` string
    # that wrote it. Comparing the two raises rather than answering wrongly,
    # which is at least the good kind of bug to have had.
    fresh = False
    if when and taken:
        fresh = frappe.utils.get_datetime(when) > frappe.utils.get_datetime(taken)

    return {
        **row,
        # The sheet is gone. Worth saying rather than showing an "as of" that
        # can never change again — and the row deliberately outlives it.
        "sheet_gone": not when,
        "sheet_modified": when,
        "stale": fresh,
    }


@frappe.whitelist(methods=["POST"])
def lock(doctype: str, docname: str, into: str) -> dict:
    """The document is the record now, and the sheet is history.

    `write` on the document and not on the sheet: locking is a statement about
    the quotation, and the person who owns the quotation is the one entitled to
    make it — often not the estimator whose sheet fed it.
    """
    return _set_status(doctype, docname, into, LOCKED)


@frappe.whitelist(methods=["POST"])
def unlock(doctype: str, docname: str, into: str) -> dict:
    """Follow the sheet again."""
    return _set_status(doctype, docname, into, FOLLOWING)


def _set_status(doctype: str, docname: str, into: str, status: str) -> dict:
    if not frappe.has_permission(doctype, "write", doc=docname):
        frappe.throw(_("You cannot change that record."), frappe.PermissionError)

    standing = _feed(doctype, docname, into)
    if not standing:
        frappe.throw(_("Those rows were not filled from a sheet."))

    values = {"status": status}
    if status == LOCKED:
        values["locked_on"] = frappe.utils.now()
        values["locked_by"] = frappe.session.user
    else:
        values["locked_on"] = None
        values["locked_by"] = None

    frappe.db.set_value("Sheet Feed", standing.name, values, update_modified=True)
    return _with_freshness({**dict(standing), **values})


def _columns(head: list, child_doctype: str, wanted: dict) -> list[dict]:
    """Work out, once, which sheet column feeds which child field.

    Done for the header row rather than per row: a hundred lines is a hundred
    repetitions of the same question otherwise, and the answer cannot change
    between rows.
    """
    meta = frappe.get_meta(child_doctype)
    by_fieldname = {f.fieldname: f for f in meta.fields}
    by_label = {(f.label or "").strip().lower(): f for f in meta.fields if f.label}

    columns = []
    for index, cell in enumerate(head):
        name, unit = header(cell)
        target = wanted.get(name) or wanted.get(str(cell).strip())

        if not target:
            found = by_fieldname.get(name.lower().replace(" ", "_")) or by_label.get(name.lower())
            target = found.fieldname if found else ""

        field = by_fieldname.get(target)
        columns.append({
            "index": index,
            "header": name,
            "unit": unit,
            "fieldname": target if field else "",
            "fieldtype": field.fieldtype if field else "",
        })
    return columns


def _child(row: list, columns: list[dict]) -> dict:
    """One sheet row, as a child row.

    The unit is appended to text and dropped from numbers. A `Currency` field
    holding `"1200 mm"` is a field holding zero, and a `Data` field holding
    `1200` without its unit is a line item nobody can check.
    """
    out = {}
    for column in columns:
        if not column["fieldname"]:
            continue
        raw = row[column["index"]] if column["index"] < len(row) else None

        if column["fieldtype"] in ("Currency", "Float", "Int", "Percent"):
            out[column["fieldname"]] = number(raw)
        elif raw in (None, ""):
            out[column["fieldname"]] = ""
        elif column["unit"]:
            out[column["fieldname"]] = f"{str(raw).strip()} {column['unit']}"
        else:
            out[column["fieldname"]] = str(raw).strip()
    return out
