"""Documents — the prose half of what a workspace writes.

A document is a `File`, the same way a sheet is. That one decision is what
makes the rest cheap: it lands in a folder, it can be shared with a link that
outlives a session, it goes in the bin and comes back, it hangs off a record
through `attached_to_doctype`, it is in the storage meter, and none of that is
built here. What is here is the only thing a `File` cannot hold, which is what
the document says.

Reseamed from `frappe/writer` (AGPL-3.0, © Frappe Technologies Pvt. Ltd. and
contributors), whose model this is: a document is Drive's file, and the app
beside it holds the body. Two things are ours rather than theirs. The body is
ProseMirror JSON saved whole rather than a base64 CRDT update, because their
editing model needs a signalling server we would have to run per shard, and
`docs/SHEETS.md` already argued that case. And versions are `File Version`
rows shared with sheets rather than a `Writer Version` table of their own,
because a version of a document and a version of a workbook turned out to be
the same five columns.

Three things get opened by the same editor and only two of them are documents:

    Doc kind          prose in a `Doc Body` row; no object, bytes on export
    .txt / .md / .csv a real object in R2, edited in place — `text.py`
    anything else     downloaded, not opened

The layers, in import order:

    body      opening a document and saving one, and the store contract
              `versions.py` reads
    text      the plain-text files beside them, read and written in place
    export    a document as one self-contained HTML file, which is also the
              `file_url` the framework insists on
    templates one to start from, which is a flag on a file
    fields    a field of the bound record, inside the prose — live while the
              document is a draft, frozen when it is sent
    writing   making one, copying one, throwing one away
"""

import frappe

from .body import (
    BLANK, DEFAULT_SETTINGS, MAX_BYTES, TITLE_MAX, blank, get_doc, head_of,
    html_of, load, may_read, may_write, put, save_doc, store,
)
from .export import ROUTE, as_markdown, download, page_html, printable, to_response, url_for
from .fields import fill, freeze, frozen_content, named, refresh, settle, values
from .templates import TEMPLATE_FIELD, listing, set_template
from .text import EDITABLE, get_text, is_text, save_text
from .writing import TEXT_KINDS, copy_of, duplicate, make, make_text, on_trash

__all__ = [
    "as_markdown",
    "BLANK",
    "blank",
    "copy_of",
    "DEFAULT_SETTINGS",
    "download",
    "duplicate",
    "EDITABLE",
    "fill",
    "freeze",
    "frozen_content",
    "get_doc",
    "get_text",
    "head_of",
    "html_of",
    "is_text",
    "listing",
    "load",
    "make",
    "make_text",
    "MAX_BYTES",
    "may_read",
    "may_write",
    "named",
    "on_trash",
    "page_html",
    "printable",
    "put",
    "refresh",
    "ROUTE",
    "save_doc",
    "save_text",
    "set_template",
    "settle",
    "store",
    "TEMPLATE_FIELD",
    "TEXT_KINDS",
    "TITLE_MAX",
    "to_response",
    "url_for",
    "values",
]
