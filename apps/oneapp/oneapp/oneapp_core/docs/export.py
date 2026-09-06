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

from . import body
from .body import _mine

ROUTE = "/api/method/oneapp.oneapp_core.docs.download"

#: Enough style that a printed document is not a wall of Times New Roman, and
#: little enough that it survives being pasted into a mail client. Deliberately
#: not our design tokens: this file is read where our stylesheet is not.
STYLE = """
body { font: 15px/1.6 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       color: #1f2933; max-width: 46rem; margin: 3rem auto; padding: 0 1.5rem; }
h1, h2, h3 { line-height: 1.25; margin: 1.6em 0 0.5em; }
table { border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #d9dde2; padding: 6px 8px; text-align: left; }
blockquote { margin: 1em 0; padding-left: 1em; border-left: 3px solid #d9dde2;
             color: #52606d; }
img { max-width: 100%; }
pre { background: #f5f7fa; padding: 12px; overflow-x: auto; }
"""


def url_for(doc: str) -> str:
    return f"{ROUTE}?name={doc}"


@frappe.whitelist(methods=["GET"])
def download(name: str) -> None:
    """Send the document as one HTML file."""
    to_response(_mine(name, "read"))


def to_response(doc) -> None:
    """The same file, for a caller that has already settled the permission.

    Two entry points because there are two kinds of reader. This one is
    `storage.r2.serve`, the single funnel every download and every expiring
    share link goes through — which, for a file with no object behind it, would
    otherwise ask `get_content()` for bytes that do not exist and answer 500.
    """
    title = doc.file_name or "document"
    html = body.load(doc.name)["html"]

    page = (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">"
        f"<title>{frappe.utils.escape_html(title)}</title>"
        f"<style>{STYLE}</style></head><body>{html}</body></html>"
    )

    frappe.local.response.filename = title if title.lower().endswith(".html") else f"{title}.html"
    frappe.local.response.filecontent = page.encode("utf-8")
    frappe.local.response.type = "download"


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
