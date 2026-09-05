"""What is inside the blob a browser saves, read back in Python.

Derived from frappe/sheets (3f9e37b5776f) — `sheets/sheets/doctype/sheet/
storage.py` for the envelope and `cell_codec.py` for the row-major unpacking.
Frappe Technologies Pvt. Ltd. and contributors hold the copyright on the parts
taken; both projects are AGPL-3.0 and this file stays that way. What is ours is
`values_map`, `named_ranges` and `extent`, which read the slices we added.

A workbook is one blob and not a table of cells. That is a reversal — the first
build stored a row per cell so the read-back could be a query — and the reason
is that the grid is Frappe's now: it holds the whole workbook in memory, saves
it whole, and expects to load it whole. Two stores for one thing is two things
to keep in step, so there is one, and this module is how the server reads it.

Three slices matter on this side:

    sheet         what was typed, `=A2*B2` and all
    values        what that came to, computed in the browser
    namedRanges   the contract a document is filled through

`values` is ours. Frappe's payload has no such slice because nothing on their
server ever needs a number — ours does: the read-back, the CSV a share link
serves and any print format all want `6480` and none of them has a browser.
"""

import base64
import binascii
import gzip
import io
import json

# The cap on the *uncompressed* workbook, which is the number that matters:
# the whole thing is decompressed and parsed to read one cell out of it.
MAX_BYTES = 40 * 1024 * 1024

_MARKER = "_z"
_KIND = "gzip"
_DATA = "data"

PACK_VERSION = 2


# --------------------------------------------------------------------------- #
# The envelope
# --------------------------------------------------------------------------- #

def encode(json_str: str) -> str:
    """Wrap a plain JSON string in the on-disk envelope."""
    raw = (json_str or "{}").encode("utf-8")
    payload = base64.b64encode(gzip.compress(raw, compresslevel=6)).decode("ascii")
    return json.dumps({_MARKER: _KIND, _DATA: payload})


def decode(stored: str | None) -> str:
    """Unwrap a stored value back to plain JSON.

    A value written before the envelope existed is plain JSON already and
    passes through, so nothing has to be migrated to be readable.
    """
    if not stored:
        return "{}"
    envelope = _envelope(stored)
    if envelope is None:
        return stored
    return _decompress(envelope[_DATA]).decode("utf-8")


def size_of(stored: str | None) -> int:
    """The uncompressed size of a stored value, without holding all of it."""
    if not stored:
        return 0
    envelope = _envelope(stored)
    if envelope is None:
        return len(stored.encode("utf-8"))
    return len(_decompress(envelope[_DATA]))


def _envelope(stored: str) -> dict | None:
    try:
        obj = json.loads(stored)
    except (ValueError, TypeError):
        return None
    if (isinstance(obj, dict) and obj.get(_MARKER) == _KIND
            and isinstance(obj.get(_DATA), str)):
        return obj
    return None


def _decompress(payload: str) -> bytes:
    """base64 + gunzip, with a ceiling.

    A gzip bomb is a small string that expands to gigabytes, and the whole
    point of a compressed column is that the caller cannot tell from the length
    what it will cost to open. So: reject an oversized envelope on sight, then
    stream out at most the cap and peek one byte past it.
    """
    if not isinstance(payload, str) or len(payload) > MAX_BYTES * 2:
        _too_big()
    try:
        compressed = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        _too_big("This sheet's stored data is not readable.")
    if len(compressed) > MAX_BYTES:
        _too_big()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as gz:
            out = gz.read(MAX_BYTES)
            if gz.read(1):
                _too_big()
    except (OSError, EOFError):
        _too_big("This sheet's stored data is not readable.")
    return out


def _too_big(reason: str = "") -> None:
    import frappe

    frappe.throw(reason or (
        "This spreadsheet is too large to save (over {0} MB). That is usually "
        "formatting applied across a very large range rather than data — clear "
        "what you do not need, or split it across tabs."
    ).format(MAX_BYTES // (1024 * 1024)))


# --------------------------------------------------------------------------- #
# The slices
# --------------------------------------------------------------------------- #

def workbook(stored: str | None) -> dict:
    """The saved payload as a dict. `{}` for anything unreadable."""
    try:
        parsed = json.loads(decode(stored))
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def tab_names(book: dict) -> list[str]:
    """The tabs, left to right. Always at least one.

    Order comes from the `sheet` slice, because that is the order the browser
    keeps them in — `Object.keys` on the workbook, which JavaScript preserves.
    """
    slice_ = book.get("sheet") or {}
    names = list((slice_.get("sheets") or {}).keys())
    return names or ["Sheet1"]


def current_tab(book: dict) -> str:
    slice_ = book.get("sheet") or {}
    return slice_.get("current") or tab_names(book)[0]


def values_map(book: dict, tab: str) -> dict:
    """`{ "A1": "6480" }` for one tab — computed, not typed.

    Falls back to the typed slice when a workbook was saved before `values`
    existed. A sheet of literals reads identically either way; one full of
    formulas reads its formulas, which is visibly wrong rather than silently
    so, and one save by anybody who can open it puts that right.
    """
    found = _cells(book.get("values"), tab)
    return found if found else _cells(book.get("sheet"), tab)


def raw_map(book: dict, tab: str) -> dict:
    """`{ "A1": "=A2*B2" }` — what was typed."""
    return _cells(book.get("sheet"), tab)


def named_ranges(book: dict) -> dict:
    """`{ "REVENUE": {"name": "Revenue", "sheet": "Sheet1", "range": "B2:B9"} }`.

    Keyed upper-case, which is the engine's own convention: a name is
    case-insensitive at the point a formula uses it.
    """
    entries = ((book.get("namedRanges") or {}).get("entries")) or {}
    return {k: v for k, v in entries.items() if isinstance(v, dict)}


def extent(cells: dict) -> tuple[int, int]:
    """The furthest row and column anybody wrote, 1-based. `(0, 0)` if empty."""
    rows = columns = 0
    for ref in cells:
        row, column = _parse(ref)
        if row > 0:
            rows, columns = max(rows, row), max(columns, column)
    return rows, columns


def _cells(slice_, tab: str) -> dict:
    if not isinstance(slice_, dict):
        return {}
    sheet = (slice_.get("sheets") or {}).get(tab)
    if not isinstance(sheet, dict):
        return {}
    if slice_.get("v") != PACK_VERSION:
        # Pre-packing shape: already `{cellId: value}`.
        return sheet
    return _unpack(sheet.get("rows") or {})


def _unpack(rows: dict) -> dict:
    out = {}
    for key, arr in rows.items():
        if not isinstance(arr, list):
            continue
        try:
            row = int(key)
        except (TypeError, ValueError):
            continue
        for column, value in enumerate(arr):
            if value is None or value == "":
                continue
            out[f"{_label(column)}{row + 1}"] = value
    return out


def _label(index: int) -> str:
    out = ""
    index += 1
    while index > 0:
        index, rest = divmod(index - 1, 26)
        out = chr(65 + rest) + out
    return out


def _parse(ref: str) -> tuple[int, int]:
    """`"B3"` → `(3, 2)`. `(0, 0)` for anything that is not a cell id."""
    column = 0
    index = 0
    text = str(ref or "")
    while index < len(text) and "A" <= text[index] <= "Z":
        column = column * 26 + (ord(text[index]) - 64)
        index += 1
    digits = text[index:]
    if not column or not digits.isdigit():
        return 0, 0
    return int(digits), column
