"""What a file is, decided once when it arrives.

A file manager's first question is "show me the drawings", and the answer has to
be a column. Deriving it from the mime type at read time would be a Python walk
over a mime map for every row of every page; deriving it on insert is one
comparison, once, ever.

Ten kinds and no more. The point of a kind is the filter chip and the icon —
a reader scanning for the site photos does not want twelve buckets, and the
mime type is still on the row for anything that needs to be exact.

`Sheet` and `Doc` are the two that are not derived from a name. Both are a
`File` whose content lives in a column and whose bytes do not exist until
somebody exports it — see `docs/SHEETS.md` and `docs/WRITER.md` — so nothing
about "Padel Pro estimator" or "Scope of works" says what it is, and
`sheets.make` and `docs.make` set the kind themselves.

`Doc` sits beside `Document` rather than inside it, and the near-collision is
deliberate: a `.docx` somebody uploaded and a document somebody wrote here are
different things to open, to weigh and to search, and one bucket holding both
would mean every reader of a kind asking a second question afterwards. The same
asymmetry already exists for `Sheet` beside a `.xlsx`.
"""

import frappe

from ..onecode import languages

KIND_FIELD = "custom_kind"
STATUS_FIELD = "custom_status"
TRASHED_FIELD = "custom_trashed_on"
OPENED_FIELD = "custom_opened"

#: Whether this file is one to start from. Declared here, with the other
#: columns this product adds to `File`, rather than in either templates module:
#: a sheet template and a document template are the same flag, and the name was
#: written out in three places before the Drive grew a rail entry for them.
TEMPLATE_FIELD = "custom_is_template"

ACTIVE = "Active"
TRASHED = "Trashed"

FOLDER = "Folder"
IMAGE = "Image"
PDF = "PDF"
VIDEO = "Video"
AUDIO = "Audio"
DOCUMENT = "Document"
SHEET = "Sheet"
DOC = "Doc"
CODE = "Code"
OTHER = "Other"

KINDS = (FOLDER, IMAGE, PDF, VIDEO, AUDIO, DOCUMENT, SHEET, DOC, CODE, OTHER)

# Matched in order, on the extension rather than on a mime type: Frappe stores
# no mime type on `File`, and the browser's guess for an upload is famously the
# thing that says a `.dwg` is `application/octet-stream`.
BY_EXTENSION = (
    (IMAGE, ("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "heic", "avif", "tiff")),
    (PDF, ("pdf",)),
    (VIDEO, ("mp4", "mov", "webm", "avi", "mkv", "m4v")),
    (AUDIO, ("mp3", "wav", "ogg", "m4a", "aac", "flac")),
    (DOCUMENT, (
        "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp",
        "txt", "md", "csv", "rtf",
    )),
    # Last, so a name that is both stays what it already was. `.md` and `.txt`
    # are read here by the same editor as a `.py`, and are still Documents:
    # what a kind answers is "show me the drawings", and a person filtering for
    # code does not mean the README.
    (CODE, languages.EXTENSIONS),
)


#: Kinds no filename can say. A sheet is a sheet because `sheets.make` said so
#: — "Padel Pro estimator" has no extension and nothing about it is a
#: spreadsheet — so a kind derived from the name would quietly demote every
#: sheet the first time anybody renamed one. A document is the same.
DECLARED = (SHEET, DOC)

#: Where each of those is listed, as a place in the Drive's rail.
#:
#: A person who wants to see *their documents* had no door: `custom_kind`
#: already held `Doc` and `Sheet` as first-class kinds, every rail place is one
#: `where`, and neither had one. Google Docs' home screen is four filters this
#: product already computes — `docs/UNIFICATION.md` §E2+E3 calls it the
#: cheapest large improvement in section E, and this is the whole of it.
#:
#: Declared here, beside the kinds, so the rule is mechanical rather than
#: remembered: a kind somebody *makes* here has a place, and a guard reads this
#: back. The words differ from the kinds on purpose — `Doc` is a column value
#: and `Documents` is what a person calls the list of them, and "Workbooks"
#: rather than "Sheets" because a sheet is a tab inside one.
PLACE_FOR = {DOC: "documents", SHEET: "workbooks"}


def kind_of(file_name: str, is_folder=False, current: str = "") -> str:
    """The kind of one file, from its name — unless it was declared.

    A folder is a kind rather than a flag on the side, because every list this
    draws sorts folders first and a sort has to have something to sort on.

    `current` is what the row already says. Passed by `rename`, which otherwise
    re-derives the kind from the new name and turns a sheet into `Other` — with
    the visible symptom, a rename later, being "That file is not a sheet."
    """
    if current in DECLARED:
        return current
    if is_folder:
        return FOLDER

    name = (file_name or "").rsplit("?", 1)[0]
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if not extension:
        return OTHER

    for kind, extensions in BY_EXTENSION:
        if extension in extensions:
            return kind
    return OTHER


def on_insert(doc, method=None):
    """Stamp the kind and the status on every new file.

    `before_insert`, so it is part of the row being written. A file that arrived
    before this existed has neither, and every query here treats a missing
    status as Active for exactly that reason — a backfill would be a write over
    every File on the site to say what its absence already says.
    """
    if not doc.get(KIND_FIELD):
        doc.set(KIND_FIELD, kind_of(doc.get("file_name"), doc.get("is_folder")))
    if not doc.get(STATUS_FIELD):
        doc.set(STATUS_FIELD, ACTIVE)
