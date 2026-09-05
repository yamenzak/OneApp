"""Spreadsheets, over the file table every attachment already lives in.

**It is `File`, not a new model.** A sheet's identity, name, owner, folder,
share, place in the bin and binding to a record are a `File` row with
`custom_kind = 'Sheet'` — so a sheet arrived already able to sit in a folder, be
shared with a colleague, be handed to a stranger on an expiring link, be picked
from the attach dialog, and hang off a quotation. None of that is written here.

What is written here is the only thing a File cannot hold, which is a grid.

    refs        A1 notation, and nothing else. No Frappe, no database.
    codec       what is inside the blob a browser saves
    book        opening a workbook and saving one — the editor's two calls
    reading     reading a rectangle out of one
    writing     making a sheet, copying one, cleaning up after one
    templates   a sheet somebody starts from
    export      the one moment a sheet has to be bytes
    feed        a named range fills a document's child table

Two decisions run through all of it, and every layer would look wrong without
them.

**The browser evaluates formulas and the server stores what it computed.** The
saved workbook carries `sheet` (what was typed, `=A2*B2*C2`) beside `values`
(what it came to, `6480`), and nothing on this side ever reads the first. A
print format, a report and the read-back all want the number, and none of them
has a browser. `docs/SHEETS.md` §1 and §3 are the argument.

**A workbook is one blob, not a table of cells.** That is a reversal: the first
build stored a row per cell so a read-back could be a query. The grid is
Frappe's now — vendored whole, see `frontend/src/lib/sheets/VENDORED.md` — and
it loads and saves the workbook entire, so a second store the browser never
reads would be a second thing to keep in step for no reader. `codec.py` is how
Python reads the one that is left.
"""

from .refs import (
    MAX_CELLS, BadRef, canonical, cells_in, column_letters, column_number, format,
    format_range, grid, parse, parse_range, within,
)
from .codec import MAX_BYTES
from .book import get_sheet, save_sheet
from .reading import named_ranges, ranges, read_range, tabs
from .export import ROUTE, download, to_response, url_for
from .writing import copy_of, make, on_trash
from .templates import TEMPLATE_FIELD, listing, set_template
from .feed import FOLLOWING, LOCKED, feeds, header, lock, number, preview, pull, unlock

__all__ = [
    "BadRef",
    "canonical",
    "cells_in",
    "column_letters",
    "column_number",
    "copy_of",
    "download",
    "feed",
    "feeds",
    "FOLLOWING",
    "format",
    "format_range",
    "get_sheet",
    "grid",
    "header",
    "listing",
    "lock",
    "LOCKED",
    "make",
    "MAX_BYTES",
    "MAX_CELLS",
    "named_ranges",
    "number",
    "on_trash",
    "parse",
    "parse_range",
    "preview",
    "pull",
    "ranges",
    "read_range",
    "ROUTE",
    "save_sheet",
    "set_template",
    "tabs",
    "to_response",
    "TEMPLATE_FIELD",
    "unlock",
    "url_for",
    "within",
]
