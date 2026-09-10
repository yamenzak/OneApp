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

Values and never formulas, throughout. The server does not evaluate anything
(`docs/SHEETS.md` §1); the browser wrote down what each one came to, in the
workbook's `values` slice, and a number is what a child row wants anyway.
"""

import json
import re

import frappe
from frappe import _

from ..onestorage import kinds
from . import book, codec, rules
from .book import _mine
from .reading import _read

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
def preview(sheet: str, label: str, doctype: str = "", docname: str = "",
            into: str = "", mapping: str | dict = "") -> dict:
    """What a pull would bring in, before it brings it in.

    A read-back writes over a document's lines, and the one thing somebody
    needs before that is to see what is about to land. Same code path as the
    pull, so the preview cannot be right while the pull is wrong.

    `doctype`/`docname`/`into` are what makes `problems` possible: told which
    table these rows are for, this runs the same check the pull runs and says
    what would be refused *before* the button that refuses it. Without them
    it is the shape and nothing more, which is what a preview was.
    """
    _mine(sheet)
    block = _read(book.load(sheet), label=label)
    rows = block["values"]
    if not rows:
        return {"headers": [], "rows": [], "count": 0, "problems": []}

    headers = [header(cell) for cell in rows[0]]
    body = [row for row in rows[1:] if any(cell not in (None, "") for cell in row)]

    return {
        "headers": [{"field": name, "unit": unit} for name, unit in headers],
        "rows": body[:50],
        "count": len(body),
        "ref": block["ref"],
        "tab": block["tab"],
        "problems": _problems(doctype, docname, into, rows[0], body, mapping),
    }


def _problems(doctype: str, docname: str, into: str, head: list,
              body: list[list], mapping) -> list[str]:
    """What the check would say about these rows, for a caller that may not
    have named a table. Answers nothing rather than raising: a preview of a
    range against a record somebody cannot read is a preview with no warnings
    on it, not a request that fails."""
    if not doctype or not docname or not into:
        return []
    if not frappe.has_permission(doctype, "read", doc=docname):
        return []
    try:
        field = frappe.get_meta(doctype).get_field(into)
        if not field or field.fieldtype not in ("Table", "Table MultiSelect"):
            return []
        wanted = frappe.parse_json(mapping) if isinstance(mapping, str) and mapping \
            else (mapping or {})
        return rules.check(field.options, _columns(head, field.options, wanted), body)
    except Exception:
        frappe.clear_last_message()
        return []


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

    block = _read(book.load(sheet), label=label)
    rows = block["values"]
    if not rows:
        frappe.throw(_("The range {0} is empty.").format(label))

    wanted = frappe.parse_json(mapping) if isinstance(mapping, str) and mapping else (mapping or {})
    columns = _columns(rows[0], field.options, wanted)

    body = [row for row in rows[1:] if any(cell not in (None, "") for cell in row)]

    # Every problem in the block, before the document is touched. `save()`
    # catches a bad link too — the transaction rolls back, so nothing was
    # ever half written — but it answers with the first one it hits, in the
    # framework's words, about one row. An estimator with four bad item codes
    # would find them one press at a time. See `rules.py`, including what it
    # deliberately leaves to `save()`.
    wrong = rules.check(field.options, columns, body)
    if wrong:
        frappe.throw(
            _("These rows are not ready:\n\n{0}").format("\n".join(wrong)),
            frappe.ValidationError,
            title=_("Nothing was changed"),
        )

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


# --------------------------------------------------------------------------- #
# The outward leg
#
# Everything above reads a sheet into a document. This is the other direction,
# and it is what made the round trip usable rather than a thing you had to set
# up by hand: a child table becomes a sheet whose first row is the column
# labels, whose named range is already drawn round the block, and which is
# attached to the record it came from. Press it, price the job, press "Fill from
# a sheet", and the contract on both sides is the same contract.
#
# Without this, using Sheets on a quotation meant making a blank sheet, typing
# the headings by hand *exactly* as the child doctype labels them, and naming a
# range — three chances to get it subtly wrong, discovered at the pull.
# --------------------------------------------------------------------------- #

#: How many columns a grid falls back to when the child doctype marks none
#: `in_list_view`. Frappe's own grid does the same, and an approximate sheet is
#: better than an empty one.
FALLBACK_COLUMNS = 6

#: Fieldtypes that are not a column in a spreadsheet. A signature or an image
#: in a cell is a value nobody can price against.
NOT_A_COLUMN = {
    "Section Break", "Column Break", "Tab Break", "HTML", "Button", "Image",
    "Signature", "Table", "Table MultiSelect", "Attach", "Attach Image",
    "Text Editor", "Code", "Markdown Editor", "HTML Editor", "Geolocation",
}


def _grid_columns(child: str) -> list[dict]:
    """The columns the grid shows, which are the columns the sheet should have.

    The doctype's own answer first — `in_list_view` is what its author already
    said the grid is for — and Frappe's fallback after it. Implemented here
    rather than reached for out of `spaceview.meta`: that is a private helper of
    another package, and eleven lines is cheaper than a dependency between two
    packages that otherwise do not know about each other.
    """
    meta = frappe.get_meta(child)
    usable = [
        df for df in meta.fields
        if df.fieldtype not in NOT_A_COLUMN and not df.hidden
    ]
    listed = [df for df in usable if df.in_list_view]
    chosen = listed or usable[:FALLBACK_COLUMNS]
    return [{"fieldname": df.fieldname, "label": _(df.label or df.fieldname)}
            for df in chosen]


def _packed(headers: list[str], rows: list[list]) -> dict:
    """The grid in the shape the editor loads, which is row-major and 0-based."""
    packed = {"0": list(headers)}
    for at, row in enumerate(rows, start=1):
        packed[str(at)] = list(row)
    return {"v": codec.PACK_VERSION, "current": TAB, "sheets": {TAB: {"rows": packed}}}


TAB = "Sheet1"


@frappe.whitelist(methods=["POST"])
def start_from(doctype: str, docname: str, into: str, title: str = "") -> dict:
    """The sheet for this child table: the one already bound to it, or a new one.

    **One sheet per table, not one per press.** The first version made a fresh
    sheet every time somebody pressed the button, which after an afternoon of
    pricing left a Drive full of "Quotation — Items" and no way to tell which
    one anybody had been working in. A child table has one estimator the way a
    document has one draft.

    The binding is the `Sheet Feed` row, which already existed and already
    keyed on exactly this — (document, table) — but was only written when
    somebody pulled. Writing it here makes it what its name says: which sheet
    feeds which table, from the moment the sheet exists rather than from the
    first time it was read back.

    The named range is drawn here rather than left to the person, because it is
    the contract and a contract nobody drew is a pull that finds nothing. It
    covers the headings too — `preview` reads the first row as the headings, so
    a range starting at row 2 would lose them.
    """
    target = frappe.get_doc(doctype, docname)
    target.check_permission("read")

    # The one already bound, if its file is still there. A sheet somebody threw
    # away is not a reason to refuse; it is a reason to make another.
    standing = _feed(doctype, docname, into)
    if standing and standing.sheet and frappe.db.exists("File", standing.sheet):
        row = frappe.get_doc("File", standing.sheet)
        if row.get(kinds.STATUS_FIELD) != kinds.TRASHED:
            return {
                "name": row.name,
                "title": row.file_name,
                "url": f"/one/sheets/{row.name}",
                "label": standing.label,
                "existing": True,
            }

    field = target.meta.get_field(into)
    if not field or field.fieldtype not in ("Table", "Table MultiSelect"):
        frappe.throw(_("There is nothing here to open in a sheet."))

    columns = _grid_columns(field.options)
    if not columns:
        frappe.throw(_("These rows have no columns a sheet could hold."))

    rows = [
        [row.get(column["fieldname"]) for column in columns]
        for row in (target.get(into) or [])
    ]

    label = _label_for(field)
    made = _make_sheet(target, field, title, columns, rows, label)

    # And the binding, so pressing the button again opens this one.
    _remember(standing, {
        "reference_doctype": doctype,
        "reference_name": docname,
        "into": into,
        "status": FOLLOWING,
        "sheet": made["name"],
        "sheet_title": made["title"],
        "label": label,
    })

    return {
        **made, "label": label, "columns": len(columns), "rows": len(rows),
        "existing": False,
    }


@frappe.whitelist(methods=["GET"])
def bound_to(sheet: str) -> dict:
    """The record and table this sheet feeds, or `{}` for a sheet that feeds none.

    Read by the sheet's own page, so the estimator can send its rows back
    without walking to the record to press a button there. Answering `{}` is
    the ordinary case: most sheets are just sheets.
    """
    _mine(sheet)

    found = frappe.get_all(
        "Sheet Feed",
        filters={"sheet": sheet},
        fields=FEED_FIELDS, order_by="modified desc", limit_page_length=1,
    )
    if not found:
        return {}

    row = found[0]
    # The document's permission, not the sheet's: the sentence this returns is
    # about the quotation, and naming a quotation to somebody who may not read
    # it is a leak whichever object the question arrived through.
    if not frappe.has_permission(row["reference_doctype"], "read", doc=row["reference_name"]):
        return {}

    title = frappe.db.get_value(
        row["reference_doctype"], row["reference_name"],
        frappe.get_meta(row["reference_doctype"]).get_title_field() or "name",
    )
    return {
        **_with_freshness(row),
        "title": title or row["reference_name"],
        "may_write": bool(frappe.has_permission(
            row["reference_doctype"], "write", doc=row["reference_name"])),
    }


def _label_for(field) -> str:
    """What the named range is called.

    The child table's own label, upper-cased, because that is the engine's
    convention for a name and because it is what the person will see offered
    back to them in the fill dialog.
    """
    clean = re.sub(r"[^A-Za-z0-9]+", "_", _(field.label or field.fieldname)).strip("_")
    return (clean or "ROWS").upper()


#: How many empty rows below the last one carry the child doctype's rules.
#: Validation is per cell in the engine, so a column's rule is written down
#: the column and has to stop somewhere. A hundred is more lines than anybody
#: adds to a quotation in one sitting, and a rule that stops is better than a
#: payload that never does.
SPARE_ROWS = 100


def _seeded(child: str, columns: list[dict], rows: list[list]) -> dict:
    """The `validation` and `protection` slices a fed sheet starts with.

    **The headings are protected and nothing else is.** They are the contract
    — `_columns` matches them back to fields at the pull — so a heading
    renamed by accident is a column silently left out, discovered when the
    quotation comes back short. The rows under them are the whole point of the
    sheet and stay exactly as editable as any other cell; so does every other
    tab, which is where the estimator's working goes.

    **The rules are the child doctype's own**, turned into what the browser
    engine draws: a Select becomes the same dropdown the form has, a number
    column refuses a word. `rules.py` says what is and is not expressible
    here, and why the check at the pull is not made redundant by any of it.
    """
    seeded = {}

    if columns:
        seeded["protection"] = {TAB: {"locked": False, "ranges": [{
            "id": 1, "r0": 0, "c0": 0, "r1": 0, "c1": len(columns) - 1,
            "description": _("The headings feed the record. Work below them, "
                             "or on another tab."),
        }]}}

    found = rules.for_columns(child, [one["fieldname"] for one in columns])
    if found:
        from . import refs

        # From row 2, because row 1 is the headings — and past the last row
        # somebody has, because the next thing they do is add lines.
        cells = {}
        for line in range(2, len(rows) + SPARE_ROWS + 2):
            for index, rule in found.items():
                cells[refs.format(line, index + 1)] = rule
        seeded["validation"] = {TAB: cells}

    return seeded


def _make_sheet(target, field, title, columns, rows, label) -> dict:
    from . import writing

    name = (title or "").strip() or _("{0} — {1}").format(
        target.get_title() or target.name, _(field.label or field.fieldname)
    )

    made = writing.make(title=name, doctype=target.doctype, docname=target.name)

    grid = _packed([column["label"] for column in columns], rows)
    payload = {
        "sheet": grid,
        # What each cell came to. Nothing here is a formula yet, so the two
        # slices are the same — and `values` has to exist or the read-back has
        # nothing to read.
        "values": grid,
        "namedRanges": {"entries": {label: {
            "name": label,
            "sheet": TAB,
            "range": _area(len(columns), len(rows)),
        }}},
        **_seeded(field.options, columns, rows),
    }
    book.store(made["name"], codec.encode(json.dumps(payload)))

    return made


def _area(columns: int, rows: int) -> str:
    """`A1:D9` — the headings and every row under them."""
    from . import refs

    return refs.format_range(1, 1, rows + 1, max(1, columns))
