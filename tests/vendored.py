"""Which frontend source is ours to keep rules about, and which is not.

The spreadsheet — its engine, its canvas renderer and the editor above them —
is Frappe's, taken whole from `frappe/sheets` and kept as theirs
(`apps/oneapp/frontend/src/lib/sheets/VENDORED.md`). Every guard in this
directory encodes a rule about how *we* write a component: which frappe-ui props
exist in the version we pin, that an icon-only button says what it does, that a
tooltip is frappe-ui's, that a customer never reads a supplier's name.

None of those rules is wrong. They are simply not questions about somebody
else's file. Their editor was written against frappe-ui beta.3 and its own
conventions, and the two ways to make it pass are both worse than this: edit
four thousand lines of theirs until our linter is happy — which is exactly what
vendoring exists to avoid, and which makes the next upstream fix a merge instead
of a copy — or weaken the rule for everybody.

So the guards skip these paths, and the header block on every file in them says
where it came from. What is ours inside that tree — the store, the persistence
seam, the ExcelJS adapter — is small, and is listed in VENDORED.md.
"""

from pathlib import Path

#: Path fragments, matched against a POSIX path. Anything under one of these is
#: somebody else's.
VENDORED = (
    "frontend/src/lib/sheets/",
    "frontend/src/components/sheets/editor/",
)


def is_vendored(path: Path | str) -> bool:
    text = Path(path).as_posix()
    return any(part in text for part in VENDORED)


def ours(paths):
    """The subset of `paths` this repository actually wrote."""
    return [p for p in paths if not is_vendored(p)]
