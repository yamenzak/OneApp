"""A document as bytes, for the one moment it has to be a file.

The same shape `sheets/export.py` has, and it exists for the same two reasons.
The small one is `File.validate`, which refuses a row whose `file_url` names
nothing: the framework's own escape hatch for a file whose bytes are produced
rather than stored is a `/api/method/` URL, so a document's `file_url` is this
endpoint — true rather than convenient, since following it gets you the file
the row claims to be.

The large one is that a document has to leave. Somebody mails the scope of
works to a client who has never heard of this workspace, and what should land
in their inbox is a document, not a link to a login.

HTML, self-contained, with the stylesheet inlined. Not PDF: producing one on
the server means a headless browser in the container, and the browser that is
already open can print the document it is already showing. Not `.docx` either
— see `docs/WRITER.md`; the export that matters is the one anybody can open,
and every word processor opens HTML.
"""

import frappe

from ..shared import paper
from . import body, typography
from .body import _mine

ROUTE = "/api/method/oneapp.onedoc.download"

#: The languages that run the other way. Frappe's own list, and the same one the
#: SPA carries in `lib/runtime/translate.js` — kept here rather than imported
#: from it because one is Python and one is a browser bundle.
RIGHT_TO_LEFT = frozenset(
    ("ar", "arc", "dv", "fa", "ha", "he", "ks", "ku", "ps", "ur", "yi")
)

#: What surrounds the type, which `docs/typography.py` sets. Split in two
#: because the type scale is shared with the editor and has to stay exactly
#: what the editor uses, and this is the page around it — which the editor
#: draws itself, out of the same numbers, in `lib/paper/`.
#:
#: Deliberately not our design tokens: this file is read where our stylesheet
#: is not. The right-to-left rules are physical rather than logical for the
#: same reason — an attribute selector is understood by a word processor, a
#: mail client and an old print engine alike, and `padding-inline-start` is
#: understood by none of them.
FRAME = """
html, body { margin: 0; padding: 0; }
body { max-width: 46rem; margin: 3rem auto; padding: 0 1.5rem; }
"""


def url_for(doc: str) -> str:
    return f"{ROUTE}?name={doc}"


@frappe.whitelist(methods=["GET"])
def download(name: str) -> None:
    """Send the document as one HTML file."""
    to_response(_mine(name, "read"))


def page_html(doc) -> str:
    """One document as a whole HTML file — the bytes both readers get.

    Split out from `to_response` because printing wants the same page and not
    as a download: the browser prints an iframe holding this, which is how a
    letter head repeats on every sheet and how `@page` gets a size at all. A
    document printed from the app's own window would be printed through the
    app's chrome, and `@page` would be the app's.
    """
    title = doc.file_name or "document"
    loaded = body.load(doc.name)
    html = loaded["html"]

    # The language this was written in, and which way it runs. Without them an
    # Arabic document exports as a left-to-right page: the words are right, the
    # paragraphs start on the wrong side, and every table column is reversed.
    lang = frappe.local.lang or "en"
    direction = "rtl" if lang.split("-")[0] in RIGHT_TO_LEFT else "ltr"

    # How the page is set — size, orientation, margins, letter head. A pageless
    # document answers `paged: False` and gets none of it, which is the same
    # file this produced before any of this existed.
    settings = loaded.get("settings") or {}
    setup = paper.setup_of(settings)
    # The type first, because the page is measured in it. Paged, the page
    # supplies its own width and margins and `FRAME`'s centred column would
    # fight them.
    sheet = typography.sheet(settings)
    if setup["paged"]:
        sheet += paper.page_css(setup) + paper.PAPER_CSS
        html = paper.repeated(setup, html)
    else:
        sheet += FRAME

    return (
        "<!doctype html>\n"
        f'<html lang="{lang}" dir="{direction}"><head><meta charset="utf-8">'
        f"<title>{frappe.utils.escape_html(title)}</title>"
        f"<style>{sheet}</style></head><body>{html}</body></html>"
    )


def to_response(doc) -> None:
    """The same file, for a caller that has already settled the permission.

    Two entry points because there are two kinds of reader. This one is
    `storage.r2.serve`, the single funnel every download and every expiring
    share link goes through — which, for a file with no object behind it, would
    otherwise ask `get_content()` for bytes that do not exist and answer 500.
    """
    title = doc.file_name or "document"
    frappe.local.response.filename = title if title.lower().endswith(".html") else f"{title}.html"
    frappe.local.response.filecontent = page_html(doc).encode("utf-8")
    frappe.local.response.type = "download"


@frappe.whitelist(methods=["GET"])
def printable(name: str) -> dict:
    """The printable page, as a string the editor can put in an iframe."""
    doc = _mine(name, "read")
    return {"name": doc.name, "title": doc.file_name, "html": page_html(doc)}


@frappe.whitelist(methods=["GET"])
def as_markdown(name: str) -> dict:
    """The document as Markdown, for pasting somewhere that speaks it.

    Frappe ships `html2text`, which is what its own mail does, so there is no
    dependency and no second renderer to keep in step with the first.
    """
    doc = _mine(name, "read")
    from frappe.utils.html_utils import html2text

    return {"name": doc.name, "title": doc.file_name,
            "markdown": html2text(body.load(doc.name)["html"] or "")}
