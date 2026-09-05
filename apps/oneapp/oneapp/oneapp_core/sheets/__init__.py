"""Spreadsheets, over the file table every attachment already lives in.

**It is `File`, not a new model.** A sheet's identity, name, owner, folder,
share, place in the bin and binding to a record are a `File` row with
`custom_kind = 'Sheet'` — so a sheet arrived already able to sit in a folder, be
shared with a colleague, be handed to a stranger on an expiring link, be picked
from the attach dialog, and hang off a quotation. None of that is written here.

What is written here is the only thing a File cannot hold, which is a grid.

    refs        A1 notation, and nothing else. No Frappe, no database.
    reading     opening a sheet whole, and reading a rectangle out of one
    writing     making one, and every change to one
    templates   a sheet somebody starts from
    export      the one moment a sheet has to be bytes
    feed        a named range fills a document's child table

One decision runs through all of it and is worth stating once more here,
because every layer would look wrong without it: **the browser evaluates
formulas and the server stores what it computed.** `Sheet Cell` keeps `raw`
(`=A2*B2*C2`) beside `value` (`6480`), and nothing on this side ever reads
`raw`. A print format, a report and the read-back all want the number, and none
of them has a browser. `docs/SHEETS.md` §1 and §3 are the argument.
"""

from .refs import (
    MAX_CELLS, BadRef, canonical, cells_in, column_letters, column_number, format,
    format_range, grid, parse, parse_range, within,
)
from .reading import open_sheet, ranges, read_range, tabs
from .export import ROUTE, download, to_response, url_for
from .writing import (
    add_tab, copy_into, make, on_trash, remove_range, remove_tab, rename_tab,
    set_range, set_tab_geometry, write_cells,
)
from .templates import TEMPLATE_FIELD, listing, set_template
from .feed import FOLLOWING, LOCKED, feeds, header, lock, number, preview, pull, unlock

__all__ = [
    "add_tab",
    "BadRef",
    "canonical",
    "cells_in",
    "column_letters",
    "column_number",
    "copy_into",
    "download",
    "feed",
    "feeds",
    "FOLLOWING",
    "format",
    "format_range",
    "grid",
    "header",
    "listing",
    "lock",
    "LOCKED",
    "make",
    "MAX_CELLS",
    "number",
    "on_trash",
    "open_sheet",
    "parse",
    "parse_range",
    "preview",
    "pull",
    "ranges",
    "read_range",
    "remove_range",
    "remove_tab",
    "rename_tab",
    "ROUTE",
    "set_range",
    "set_tab_geometry",
    "set_template",
    "tabs",
    "to_response",
    "TEMPLATE_FIELD",
    "unlock",
    "url_for",
    "within",
    "write_cells",
]
