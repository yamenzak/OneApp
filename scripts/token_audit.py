#!/usr/bin/env python3
"""Every utility class our SPAs use must actually emit CSS.

frappe-ui's Tailwind preset *replaces* Tailwind's own scales rather than
extending them, so a retired token is a silent break: `rounded-lg` and
`bg-surface-white` produce no rule at all — no build error, no type error, just
square corners and a transparent card. The v1 migration retired a long list of
these, and more will go.

This compares the classes our source references against the class names Tailwind
actually emitted for the built stylesheet. Anything referenced and not emitted is
either a retired token or a typo; both are worth failing over.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ("oneapp", "oneapp_control")

# Where classes are written: a static attribute, a bound expression's string
# literals, frappe-ui's own class-shaped props, and JS that builds a class list.
CLASS_ATTR = re.compile(
    r"""(?:^|\s)(?P<bound>:|v-bind:)?(?:class|[\w-]*-class)\s*=\s*"(?P<value>[^"]*)\"""",
    re.M | re.S,
)
# Only in script: in a template this same shape matches `:class="valueClass"`
# and records the variable name as a class.
JS_CLASS = re.compile(r"""(?<![:\w-])(?:class(?:Name)?|Class)\s*[=:]\s*(['"`])(.*?)\1""", re.S)
SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.S)
STRING_IN_EXPR = re.compile(r"""'([^']*)'|"([^"]*)\"""")

# A Tailwind utility, roughly: an optional `-`/`!` prefix, then lowercase or an
# arbitrary-variant bracket, then anything a variant or arbitrary value can
# contain. Deliberately loose — anything that is not a utility simply will not
# be in the emitted set either, so the allowlist below carries the exceptions.
#
# The narrow earlier version excluded `&`, `=` and `!`, which is every arbitrary
# variant and every `!important` utility: `max-sm:[&_[data-slot=x]]:!px-4` and
# `-mx-4` were both skipped without a word, so the one that emitted nothing was
# invisible to the very check meant to find it.
UTILITY = re.compile(r"""^[-!]?[a-z\[][\w\[\]&=!*>+~:.,%#/()'"$-]*$""")

# Files whose *whole* purpose is to name classes, so every string literal in
# them is a class list.
#
# The regexes above look for `class="…"` and `class: '…'`; a module that exports
# `export const TAB_STRIP = [...]` matches neither, so its classes were never
# audited at all — and one of them (an arbitrary variant Tailwind could not
# parse) emitted nothing for exactly as long as nobody looked. A file listed
# here is opting in to being read as a class list.
CLASS_MODULES = ("components/settings/geometry.js",)

# The opposite exemption: files whose string literals are a formal language of
# somebody else's, which the loose heuristic below cannot tell from a class
# list. Excel number-format codes are the case that forced this —
# `'dd-mmm-yyyy hh:mm'` is two tokens, both lowercase, both carrying a `-` or a
# `:`, which is exactly the shape of `sticky right-0`. Only the heuristic is
# skipped: a real `class="…"` in one of these files is still read.
NOT_CLASS_LISTS = ("lib/sheets/display.js",)

# Whole subtrees that are somebody else's code and do not use Tailwind at all.
# The spreadsheet engine and its canvas renderer are Frappe's, vendored as-is
# (see apps/oneapp/frontend/src/lib/sheets/VENDORED.md); a canvas has no class
# attribute, and what class-shaped strings they do hold are their own — the
# scrollbar's `sn-sb`, a `describe()` title, an Excel format code. Auditing them
# against our Tailwind build asks a question with no right answer, and the
# alternative — editing their files to please our linter — is exactly what
# vendoring is meant to avoid.
VENDORED = (
    "lib/sheets/engine/",
    "lib/sheets/canvas/",
    "lib/sheets/utils/",
    # The editor above them. It paints itself: four hundred lines of its own
    # `sn-*` CSS in the same file, so `sn-topbar` is defined two hundred lines
    # below where it is used and has never been a Tailwind utility.
    "components/sheets/editor/",
)

# Files that write a *whole* HTML document — their own `<style>` included — and
# hand it to an iframe. The class names in one of those are defined by the
# stylesheet in the same string, so measuring them against the app's Tailwind
# build asks the wrong question: they emit no utility CSS because they are not
# utilities. `lib/sheets/printing.js` builds the printer's copy of a tab.
SELF_CONTAINED = ("lib/sheets/printing.js",)

# Referenced but never emitted for reasons that are not drift.
ALLOWED_MISSING = {
    # Ours, defined in index.css or by frappe-ui's own component CSS.
    "dialog-scroll-container",
    "dialog-content",
    # Tailwind emits `.group` only when a group-* variant is used; frappe-ui
    # names its own groups and we only read them.
    "group",
}


def emitted_classes(app: str) -> set[str]:
    """Class names present in the app's built stylesheet."""
    assets = ROOT / f"apps/{app}/{app}/public/frontend/assets"
    sheets = sorted(assets.glob("*.css"))
    if not sheets:
        raise SystemExit(f"{app}: no built stylesheet in {assets} — run vite build")
    css = "\n".join(p.read_text() for p in sheets)
    # Selectors are escaped: `.sm\:hidden`, `.px-\[4\.4rem\]`.
    return {re.sub(r"\\(.)", r"\1", name) for name in re.findall(r"\.((?:[\w-]|\\.)+)", css)}


def class_lists(app: str) -> list[tuple[str, str]]:
    """Every class list our source writes, as (blob, file).

    A blob rather than a token, because some rules are about what a class list
    says *together* — an outlined block and its corner radius are one decision,
    and reading them apart cannot see it.
    """
    root = ROOT / f"apps/{app}/frontend/src"
    found: list[tuple[str, str]] = []

    def record(blob: str, path: Path):
        if blob.strip():
            found.append((blob, path.relative_to(root).as_posix()))

    for path in sorted(root.rglob("*")):
        if path.suffix not in (".vue", ".js"):
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(VENDORED):
            continue
        source = path.read_text()
        if path.relative_to(root).as_posix() in CLASS_MODULES:
            # Prose in the doc comments is not a class list, and "the" is not a
            # retired token.
            code = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
            code = re.sub(r"//[^\n]*", "", code)
            for single, double in STRING_IN_EXPR.findall(code):
                record(single or double, path)
            continue
        if path.relative_to(root).as_posix() in SELF_CONTAINED:
            continue
        for match in CLASS_ATTR.finditer(source):
            blob = match.group("value")
            if match.group("bound"):
                # `:class="valueClass"` names a variable, not a class. Only the
                # string literals inside a bound expression are class lists.
                for single, double in STRING_IN_EXPR.findall(blob):
                    record(single or double, path)
            else:
                record(blob, path)
        scripts = SCRIPT.findall(source) if path.suffix == ".vue" else [source]
        for script in scripts:
            for _, blob in JS_CLASS.findall(script):
                record(blob, path)
            # A class list held in a plain constant matches neither regex above.
            # `const STUCK = 'sticky right-0 z-10 bg-surface-white'` is how a
            # retired token got past this and rendered a transparent column over
            # the one beside it.
            if path.relative_to(root).as_posix() not in NOT_CLASS_LISTS:
                for blob in loose_class_lists(script):
                    record(blob, path)
    return found


def referenced_classes(app: str) -> dict[str, set[str]]:
    """{class: {files}} for every utility our source writes."""
    found: dict[str, set[str]] = {}
    for blob, rel in class_lists(app):
        for token in blob.split():
            token = token.strip()
            if token and UTILITY.match(token):
                found.setdefault(token, set()).add(rel)
    return found


# A token nothing but Tailwind writes: it carries a scale, a variant or an
# arbitrary value. Used to tell a class list from an English sentence.
TAILWIND_ISH = re.compile(r"[-:\[]")


def loose_class_lists(script: str) -> list[str]:
    """String literals that can only be class lists.

    A heuristic, and it has to be: any string in a script could be anything.
    The rule is deliberately conservative — several tokens, every one of them
    shaped like a utility, and at least half carrying a scale, a variant or an
    arbitrary value. "sticky right-0 z-10 bg-surface-base" qualifies; "Add to
    favourites" and "last 7 days" do not.
    """
    code = re.sub(r"/\*.*?\*/", "", script, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)

    found = []
    for single, double in STRING_IN_EXPR.findall(code):
        blob = single or double
        tokens = blob.split()
        if len(tokens) < 2 or not all(UTILITY.match(t) for t in tokens):
            continue
        if sum(bool(TAILWIND_ISH.search(t)) for t in tokens) * 2 < len(tokens):
            continue
        found.append(blob)
    return found


def audit(app: str) -> dict[str, set[str]]:
    emitted = emitted_classes(app)
    return {
        cls: files
        for cls, files in referenced_classes(app).items()
        if cls not in emitted and cls not in ALLOWED_MISSING
    }


if __name__ == "__main__":
    failed = False
    for app in APPS:
        missing = audit(app)
        print(f"{app}: {len(missing)} classes referenced but never emitted")
        for cls, files in sorted(missing.items()):
            print(f"  {cls:32} {', '.join(sorted(files)[:3])}")
        failed |= bool(missing)
    sys.exit(1 if failed else 0)
