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
    """
    _mine(sheet)

    target = frappe.get_doc(doctype, docname)
    target.check_permission("write")

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

    return {
        "filled": len(body),
        "into": into,
        "columns": [c for c in columns if c["fieldname"]],
        "skipped": [c["header"] for c in columns if not c["fieldname"]],
    }


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
