"""What a file is, decided once when it arrives.

A file manager's first question is "show me the drawings", and the answer has to
be a column. Deriving it from the mime type at read time would be a Python walk
over a mime map for every row of every page; deriving it on insert is one
comparison, once, ever.

Eight kinds and no more. The point of a kind is the filter chip and the icon —
a reader scanning for the site photos does not want twelve buckets, and the
mime type is still on the row for anything that needs to be exact.

`Sheet` is the one that is not derived from a name. A sheet is a `File` whose
grid lives in `Sheet Cell` rows and whose bytes do not exist until somebody
exports it — see `docs/SHEETS.md` — so nothing about its filename says what it
is, and `sheets.make` sets the kind itself.
"""

import frappe

KIND_FIELD = "custom_kind"
STATUS_FIELD = "custom_status"
TRASHED_FIELD = "custom_trashed_on"
OPENED_FIELD = "custom_opened"

ACTIVE = "Active"
TRASHED = "Trashed"

FOLDER = "Folder"
IMAGE = "Image"
PDF = "PDF"
VIDEO = "Video"
AUDIO = "Audio"
DOCUMENT = "Document"
SHEET = "Sheet"
OTHER = "Other"

KINDS = (FOLDER, IMAGE, PDF, VIDEO, AUDIO, DOCUMENT, SHEET, OTHER)

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
)


def kind_of(file_name: str, is_folder=False) -> str:
    """The kind of one file, from its name.

    A folder is a kind rather than a flag on the side, because every list this
    draws sorts folders first and a sort has to have something to sort on.
    """
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
