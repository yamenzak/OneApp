"""Making a document, making a plain text file, and cleaning up after both.

Changing one is not here — `body.py` takes the whole document back, the way
`sheets/book.py` takes the whole workbook. What is here is the moments a
document is a *file* rather than prose: it comes into existence, it is copied
from another, and it is thrown away.

Two things get made here and they are not the same thing. A **document** is a
`File` of kind `Doc` whose prose is a `Doc Body` row and whose bytes do not
exist. A **text file** is a `File` of kind `Document` with a real `.txt` or
`.md` object in R2, made empty here so that "new file" in the Drive is not only
ever an upload. The editor opens both; `text.py` is the second one's store.
"""

import frappe
from frappe import _

from ..onecode import languages
from ..onestorage import kinds
from . import body, export, text

#: What may be made empty and then typed into. Anything else is an upload:
#: a `.docx` nobody has written is a file the browser cannot make either.
TEXT_KINDS = {
    "txt": ("Untitled.txt", "text/plain"),
    "md": ("Untitled.md", "text/markdown"),
    "csv": ("Untitled.csv", "text/csv"),
    # And every language OneCode knows, on the same terms: a new empty file
    # with a real object behind it, named `Untitled.<ext>`. Built rather than
    # typed out, so adding a language is one line in `languages.py` and not
    # three edits that have to agree.
    **{
        key: (f"Untitled.{key}", "text/plain")
        for key in languages.LANGUAGES
    },
}


@frappe.whitelist(methods=["POST"])
def make(title: str = "", folder: str = "", doctype: str = "", docname: str = "",
         template: str = "") -> dict:
    """A new document, which is a new `File` of kind Doc.

    `doctype`/`docname` attach it to a record, through the same two columns
    every attachment in the product uses — which is what makes "the project's
    scope of works" a query rather than a feature.
    """
    title = (title or "").strip() or "Untitled document"
    _may_attach(doctype, docname)

    doc = frappe.get_doc({
        "doctype": "File",
        "file_name": title,
        "is_folder": 0,
        "folder": folder or "Home",
        "is_private": 1,
        "attached_to_doctype": doctype or None,
        "attached_to_name": docname or None,
        # Nothing about the name says this is a document, so `kinds.on_insert`
        # cannot work it out and is told instead.
        kinds.KIND_FIELD: kinds.DOC,
        kinds.STATUS_FIELD: kinds.ACTIVE,
        # A document's bytes do not exist until somebody exports it, so there
        # is no object and no key. `File` refuses a row whose URL names
        # nothing, and its own exception for a produced file is a
        # `/api/method/` URL — so a document's URL is its exporter. Bare here
        # and completed below, because the row has no name until the insert
        # returns.
        "file_url": export.ROUTE,
    }).insert()

    doc.db_set("file_url", export.url_for(doc.name), update_modified=False)

    # What the document reads. The attachment seeds the first source, so a
    # letter started from a quotation is about it without anybody saying so
    # twice; a template hands over its *slots*, records left empty, because a
    # template is for any quotation rather than for one. See `shared/binding`.
    from ..shared import binding

    binding.seed_from_attachment(doc.name, doctype, docname)
    if template:
        binding.copy_sources(template, doc.name)

    content = copy_of(template) if template else body.blank()
    body.store(doc.name, content, body.html_of(content))

    return {"name": doc.name, "title": doc.file_name, "url": f"/one/docs/{doc.name}"}


@frappe.whitelist(methods=["POST"])
def make_text(kind: str = "txt", title: str = "", folder: str = "",
              doctype: str = "", docname: str = "") -> dict:
    """A new empty `.txt`, `.md` or `.csv`, with a real object behind it.

    The one place in the product that creates a file rather than receiving one.
    It exists because "new note" was otherwise a round trip through a text
    editor on somebody's laptop and an upload.
    """
    kind = (kind or "txt").lower().lstrip(".")
    if kind not in TEXT_KINDS:
        frappe.throw(_("A new {0} file is not something this can make.").format(kind))
    fallback, _mime = TEXT_KINDS[kind]

    _may_attach(doctype, docname)

    name = (title or "").strip() or fallback
    if not name.lower().endswith(f".{kind}"):
        name = f"{name}.{kind}"

    doc = frappe.get_doc({
        "doctype": "File",
        "file_name": name,
        "is_folder": 0,
        "folder": folder or "Home",
        "is_private": 1,
        "attached_to_doctype": doctype or None,
        "attached_to_name": docname or None,
        # A newline rather than nothing. `File.validate` writes the object only
        # when it is handed content, and falsy content is not handed: an empty
        # string leaves the row with no `file_url` and the insert fails with
        # "File  does not exist", naming a URL that was never set.
        "content": "\n",
        kinds.STATUS_FIELD: kinds.ACTIVE,
    }).insert()

    # The one line without which none of this works. Every file this function
    # makes starts as the same single newline, so Frappe hands them all one
    # object — and the first edit to any of them rewrites all of them. See
    # `text.own_object`.
    text.own_object(doc)

    return {"name": doc.name, "title": doc.file_name, "url": f"/one/docs/{doc.name}"}


def _may_attach(doctype: str, docname: str) -> None:
    if doctype and docname and not frappe.has_permission(doctype, "write", doc=docname):
        frappe.throw(_("You cannot change that record."), frappe.PermissionError)


def copy_of(source: str) -> str:
    """One document's stored prose, for another document to start from.

    Not a `File` copy: a document's content is a column, and the R2 object a
    Drive copy would duplicate does not exist.
    """
    frappe.get_doc("File", source).check_permission("read")
    return frappe.db.get_value("Doc Body", source, "content") or body.blank()


def on_trash(doc, method=None):
    """A document's prose goes when its File does.

    Registered on `File`, because that is the document being deleted. Without
    it the bin's thirty-day sweep would leave the body of every document
    anybody ever threw away.
    """
    if doc.get(kinds.KIND_FIELD) != kinds.DOC:
        return
    if frappe.db.exists("Doc Body", doc.name):
        frappe.delete_doc("Doc Body", doc.name, ignore_permissions=True, force=True)


@frappe.whitelist(methods=["POST"])
def duplicate(name: str, title: str = "") -> dict:
    """Another document just like this one, in the same folder.

    A document and a template are the same object here — `make(template=...)`
    is this call with a folder chosen — so there is nothing else to build for
    "start from the last one", which is how a workspace actually writes its
    third quotation.
    """
    source = frappe.get_doc("File", name)
    source.check_permission("read")

    if source.get(kinds.KIND_FIELD) == kinds.DOC:
        return make(
            title=(title or f"{source.file_name} copy"),
            folder=source.folder,
            template=name,
        )

    return text.duplicate(source, title)
