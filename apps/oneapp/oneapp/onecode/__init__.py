"""OneCode — the languages a code file can be, and the editor that opens it.

The catalogue is the whole of the server side. What *edits* a code file is
`onedoc.text`, because a `.py` in the Drive and a `.md` beside it are the same
object with the same versions and the same save call — see `docs/WRITER.md`.
What is here is the one thing prose does not have: which language a file is in,
what highlights it, and which of them the New menu offers.
"""

from .languages import (
    ALIASES, EXTENSIONS, LANGUAGES, NOT_OFFERED, OFFERED,
    highlight_for, is_code, label_for, resolve,
)

__all__ = [
    "ALIASES",
    "EXTENSIONS",
    "highlight_for",
    "is_code",
    "label_for",
    "LANGUAGES",
    "NOT_OFFERED",
    "OFFERED",
    "resolve",
]
