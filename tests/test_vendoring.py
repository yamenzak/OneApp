"""The three obligations that come with taking somebody else's code.

`CLAUDE.md` states them and calls them not optional: keep Frappe's copyright
notice, say at the top of the file what it was derived from, and never move
that file back to a permissive licence. `VENDORED.md` beside each tree repeats
them.

Nothing checked any of it until now, and the failure mode is the quiet kind: a
header block is four comment lines at the top of a file, and four comment lines
at the top of a file are exactly what a tidy-up deletes. This repository turns
a rule into a check wherever it can, and a licence obligation is the rule with
the most reason to be one.

`tests/vendored.py` already held the paths, because every style guard skips
them. This reads the same list in the other direction.
"""

import pathlib
import re

import pytest

from vendored import DERIVED_PY, OURS_INSIDE, VENDORED, is_ours_inside

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "apps/oneapp/frontend/src"
PY_APP = ROOT / "apps/oneapp/oneapp"

#: How far into a file the block has to be. It is the header or it is not a
#: header — a notice four hundred lines down is one nobody reading the file
#: will see, and one a diff will not show beside the code that changed.
HEADER = 12

# What has to be there is **an attribution to Frappe**, not a house style, so
# the check is that the header names the owner and claims a copyright — in
# either order, in whatever words.
#
# Four spellings are in the tree and all four are the notice. The JS headers
# say "Copyright (c) Frappe Technologies"; the Python ones put the year in
# between; `link_preview.py` uses the symbol; and `codec.py` writes it as a
# sentence, because it is attributing *the parts taken* rather than the whole
# file. A pattern tight enough to reject the last one would be a pattern
# enforcing a format, and the obligation is not about format.
#
# The looseness is bounded by the window: twelve lines in a JS file, sixteen in
# a Python one, which is a header and not a paragraph four hundred lines down
# that happens to mention both words.
OWNER = re.compile(r"\bFrappe\b")
CLAIM = re.compile(r"(copyright|©)", re.I)


class COPYRIGHT:
	"""Both halves, anywhere in the header. `re`-shaped so it reads like the
	other two patterns at every call site."""

	@staticmethod
	def search(text):
		return OWNER.search(text) and CLAIM.search(text)
ORIGIN = re.compile(r"(Vendored|Derived|Taken) from", re.I)
LICENCE = re.compile(r"AGPL", re.I)


def trees() -> list[pathlib.Path]:
    found = []
    for part in VENDORED:
        where = SRC / part.split("frontend/src/", 1)[-1]
        assert where.is_dir(), f"{part} is in VENDORED and is not a directory"
        found.append(where)
    return found


def sources() -> list[pathlib.Path]:
    return sorted(
        one
        for tree in trees()
        for one in tree.rglob("*")
        if one.is_file() and one.suffix in (".js", ".vue")
    )


THEIRS = [one for one in sources() if not is_ours_inside(one)]
MINE = [one for one in sources() if is_ours_inside(one)]


@pytest.mark.parametrize("path", THEIRS, ids=lambda p: p.name)
def test_a_vendored_file_keeps_frappes_notice(path):
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:HEADER])
    assert COPYRIGHT.search(head), (
        f"{path.relative_to(SRC)} is in a vendored tree and its first {HEADER} "
        f"lines do not carry Frappe's copyright. If the file is ours, add its "
        f"name to OURS_INSIDE in tests/vendored.py and say so in VENDORED.md."
    )


@pytest.mark.parametrize("path", THEIRS, ids=lambda p: p.name)
def test_a_vendored_file_says_what_it_came_from(path):
    """The second obligation, and the one that decays first: a file moved
    within our tree keeps its notice and starts lying about its path."""
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:HEADER])
    assert ORIGIN.search(head), (
        f"{path.relative_to(SRC)} carries a copyright and does not say what it "
        f"was derived from"
    )


@pytest.mark.parametrize("path", THEIRS, ids=lambda p: p.name)
def test_a_vendored_file_names_its_licence(path):
    """The third. A file that does not say AGPL is one somebody can move to a
    permissive licence without noticing they are doing it."""
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:HEADER])
    assert LICENCE.search(head), (
        f"{path.relative_to(SRC)} does not name its licence in its header"
    )


@pytest.mark.parametrize("path", MINE, ids=lambda p: p.name)
def test_our_own_file_does_not_claim_their_notice(path):
    """The mirror, and it is not pedantry. Claiming somebody else's copyright
    over our own code is the same category of wrong as dropping theirs, and it
    is the way this list rots: a file copied from the one beside it inherits a
    header that was never true of it."""
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:HEADER])
    assert not COPYRIGHT.search(head), (
        f"{path.relative_to(SRC)} is listed in OURS_INSIDE and carries Frappe's "
        f"copyright. Either it is theirs — take it off the list — or the header "
        f"was copied from a neighbour."
    )


def test_every_name_on_the_list_is_a_file_that_exists():
    """A list of exemptions nobody prunes is how an exemption outlives the file
    it was written for, and then quietly covers the next file of that name."""
    names = {one.as_posix() for one in sources()}
    stale = [
        one for one in OURS_INSIDE
        if not any(name.endswith("/" + one) for name in names)
    ]
    assert not stale, f"listed in OURS_INSIDE and not in any vendored tree: {stale}"


def test_each_tree_is_covered_by_a_vendoring_document():
    """`VENDORED.md` is where what-we-changed is written down, which is the
    third obligation's real content. The editor tree has none of its own and is
    covered by `lib/`'s, which names it — so the rule is that a tree is either
    documented or named by a document."""
    for tree in trees():
        if (tree / "VENDORED.md").is_file():
            continue
        named = [
            one for one in SRC.rglob("VENDORED.md")
            if tree.name in one.read_text(encoding="utf-8")
            or tree.parent.name in one.read_text(encoding="utf-8")
        ]
        assert named, (
            f"{tree.relative_to(SRC)} holds vendored code and no VENDORED.md "
            f"describes it"
        )


# --------------------------------------------------------------------------- #
# The Python half
#
# There is no vendored *tree* on this side — what came across is a handful of
# files adapted into ours, so the list is the record rather than a path prefix.
# --------------------------------------------------------------------------- #

#: A Python header is a docstring rather than a comment block, so it runs
#: longer before it gets to the notice.
PY_HEADER = 16


@pytest.mark.parametrize("name", sorted(DERIVED_PY))
def test_a_derived_python_file_carries_all_three(name):
    path = PY_APP / name
    assert path.is_file(), f"{name} is listed in DERIVED_PY and is not there"

    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:PY_HEADER])
    missing = [
        what for what, pattern in (
            ("Frappe's copyright", COPYRIGHT),
            ("what it was derived from", ORIGIN),
            ("its licence", LICENCE),
        )
        if not pattern.search(head)
    ]
    assert not missing, (
        f"{name} is derived from a Frappe app and its first {PY_HEADER} lines "
        f"do not carry {', '.join(missing)}. CLAUDE.md calls all three not "
        f"optional."
    )


def test_a_python_file_naming_an_upstream_is_on_the_list():
    """The direction that catches the next one. A file whose header says it came
    from a Frappe app, and which nobody added to `DERIVED_PY`, is a file whose
    obligations nothing is holding — which is exactly what `transcript.py` was,
    except that its header did not say so either."""
    claims = re.compile(r"(Vendored|Derived|Adapted) from `?frappe/", re.I)
    found = []
    for path in sorted(PY_APP.rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:PY_HEADER])
        if claims.search(head):
            found.append(path.relative_to(PY_APP).as_posix())

    assert sorted(found) == sorted(DERIVED_PY), (
        f"headers claim a Frappe origin: {sorted(found)}; DERIVED_PY says "
        f"{sorted(DERIVED_PY)}"
    )


def test_the_scan_found_the_files():
    """A guard nobody has seen fail is a guard nobody knows the scan of."""
    assert len(THEIRS) >= 130, len(THEIRS)
    assert len(MINE) >= 10, len(MINE)
    assert len(trees()) == len(VENDORED)
    assert len(DERIVED_PY) >= 4
