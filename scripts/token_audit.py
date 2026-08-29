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


def referenced_classes(app: str) -> dict[str, set[str]]:
    """{class: {files}} for every utility our source writes."""
    root = ROOT / f"apps/{app}/frontend/src"
    found: dict[str, set[str]] = {}

    def record(token: str, path: Path):
        token = token.strip()
        if not token or not UTILITY.match(token):
            return
        found.setdefault(token, set()).add(path.relative_to(root).as_posix())

    for path in sorted(root.rglob("*")):
        if path.suffix not in (".vue", ".js"):
            continue
        source = path.read_text()
        if path.relative_to(root).as_posix() in CLASS_MODULES:
            # Prose in the doc comments is not a class list, and "the" is not a
            # retired token.
            code = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
            code = re.sub(r"//[^\n]*", "", code)
            for single, double in STRING_IN_EXPR.findall(code):
                for token in (single or double).split():
                    record(token, path)
            continue
        for match in CLASS_ATTR.finditer(source):
            blob = match.group("value")
            if match.group("bound"):
                # `:class="valueClass"` names a variable, not a class. Only the
                # string literals inside a bound expression are class lists.
                for single, double in STRING_IN_EXPR.findall(blob):
                    for token in (single or double).split():
                        record(token, path)
            else:
                for token in blob.split():
                    record(token, path)
        scripts = SCRIPT.findall(source) if path.suffix == ".vue" else [source]
        for script in scripts:
            for _, blob in JS_CLASS.findall(script):
                for token in blob.split():
                    record(token, path)
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
