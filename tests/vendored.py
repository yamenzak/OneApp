"""Which frontend source is ours to keep rules about, and which is not.

The spreadsheet — its engine, its canvas renderer and the editor above them —
is Frappe's, taken whole from `frappe/sheets` and kept as theirs
(`apps/oneapp/frontend/src/modules/onesheet/lib/VENDORED.md`). Every guard in this
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
    "frontend/src/modules/onesheet/lib/",
    "frontend/src/modules/onesheet/components/editor/",
)


#: What is *ours* inside those trees, by name. VENDORED.md says this set is
#: small and lists it; this is the same list where a test can read it.
#:
#: The distinction matters twice. A file here must **not** carry Frappe's
#: copyright, because claiming somebody else's licence over our own code is the
#: mirror of the thing the obligation exists to stop. And every other file in
#: those trees must carry the whole block, which is what `test_vendoring.py`
#: reads.
OURS_INSIDE = {
    # The spreadsheet's seams: what it persists into, what it reads off a
    # record, and the plan a model answers with.
    "aiPlan.js", "aiPlan.test.js", "headless.js", "store.js", "xlsx-file.js",
    "collab/comments-binding.js",
    "services/linkPreview.js", "services/recordFields.js",
    "services/recordFields.test.js", "services/session.js",
    "services/versions.js",
    # The editor's, likewise.
    "shortcutRegistry.js", "usePersistence.js", "useTemplateInsert.js",
}


def is_vendored(path: Path | str) -> bool:
    text = Path(path).as_posix()
    return any(part in text for part in VENDORED)


def is_ours_inside(path: Path | str) -> bool:
    """Whether a file inside a vendored tree is one this repository wrote."""
    text = Path(path).as_posix()
    return any(text.endswith("/" + name) for name in OURS_INSIDE)


def ours(paths):
    """The subset of `paths` this repository actually wrote."""
    return [p for p in paths if not is_vendored(p)]


#: Python files taken or adapted from a Frappe app, by path from the app root.
#:
#: Listed rather than discovered, because "is this derived" is a judgement a
#: person made when they took it, and a scan for the word would find every file
#: that *mentions* an upstream. The list is the record, and
#: `tests/test_vendoring.py` reads the three obligations off each one.
#:
#: `transcript.py` is why this exists. `docs/ARCHITECTURE.md` said three files
#: were adapted from `frappe/flow_client` and named them; two carried the
#: notice and the third had never been given one, which nothing anywhere could
#: have told you.
DERIVED_PY = {
    # Three from `frappe/flow_client`: the tool schema, the transcript and the
    # loop over them.
    "oneai/tools.py",
    "oneai/transcript.py",
    "oneai/conversation.py",
    # Three from `frappe/sheets`: the workbook blob's format, the version
    # store, and the link preview with its SSRF guards.
    "onesheet/codec.py",
    "shared/versions.py",
    "onespace/link_preview.py",
    # And one from `frappe/suite`.
    "onestorage/thumbnails.py",
}
