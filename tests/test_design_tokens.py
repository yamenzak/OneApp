"""No utility class may reference a token that no longer exists.

frappe-ui's Tailwind preset *replaces* Tailwind's scales rather than extending
them, so a retired token is a silent break: the class emits no rule at all. No
build error, no type error — `rounded-lg` is simply square, `bg-surface-white`
is simply transparent. Both were live in these SPAs, on cards across the tenant
app, the signup page and the billing page.

v1 retired a long list (see the migration guide's "Unused tokens and utilities
removed" and "Radius aliases removed"), and more will go. Rather than pin the
list, this compares what the source references against what Tailwind actually
emitted — so it covers every token, including ones retired after this was
written.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from token_audit import APPS, ROOT, audit, emitted_classes, referenced_classes


def _built(app: str) -> bool:
    return any((ROOT / f"apps/{app}/{app}/public/frontend/assets").glob("*.css"))


@pytest.mark.parametrize("app", APPS)
def test_every_class_emits_css(app):
    if not _built(app):
        pytest.skip(f"{app} has no built stylesheet; run vite build")
    missing = audit(app)
    assert not missing, "\n".join(
        [
            f"{app}: `{cls}` emits no CSS — retired token, typo, or a stale "
            f"build ({', '.join(sorted(files))})"
            for cls, files in sorted(missing.items())
        ]
        # A class added since the last `vite build` is not in the stylesheet
        # yet and looks exactly like a retired one. Say so, rather than sending
        # someone hunting for a token that is fine.
        + ["", "If these are new classes, run `npx vite build` and try again."]
    )


@pytest.mark.parametrize("app", APPS)
def test_the_audit_is_actually_reading_things(app):
    """Both halves must be non-trivial, or the comparison passes vacuously."""
    if not _built(app):
        pytest.skip(f"{app} has no built stylesheet; run vite build")
    referenced = referenced_classes(app)
    emitted = emitted_classes(app)
    # Unique utilities, not occurrences. The tenant app is the smaller of the
    # two at ~85; a collapse to a handful means the extractor stopped working.
    assert len(referenced) > 60, f"{app}: only found {len(referenced)} classes in source"
    assert len(emitted) > 300, f"{app}: only found {len(emitted)} classes in the CSS"
    # A class we know is used and valid, proving the two sides line up.
    assert "text-ink-gray-8" in referenced and "text-ink-gray-8" in emitted


@pytest.mark.parametrize("app", APPS)
def test_a_retired_token_would_be_caught(app):
    """The guard's own regression test: these are the ones v1 actually retired."""
    if not _built(app):
        pytest.skip(f"{app} has no built stylesheet; run vite build")
    emitted = emitted_classes(app)
    for retired in ("rounded-lg", "bg-surface-white", "rounded-md", "text-tiny"):
        assert retired not in emitted, (
            f"{retired} emits CSS again — frappe-ui un-retired it, so the "
            f"guard would no longer catch its use"
        )


# --------------------------------------------------------------------------- #
# Icons
#
# frappe-ui renders `lucide-*` names as Tailwind utility classes, so an icon is
# subject to the same rule as any other class: the JIT emits it only if it can
# find the complete name as a literal. An icon whose name is built at runtime —
# or typed by an operator into a doctype — renders as an empty box.
# --------------------------------------------------------------------------- #

def _generated_icons(app: str) -> list[str]:
    """The names inside lib/icons.js's APP_ICONS array.

    Scoped to the array: DEFAULT_APP_ICON below it is another `lucide-*` literal
    and would otherwise be counted as a 27th icon.
    """
    js = (ROOT / f"apps/{app}/frontend/src/lib/icons.js").read_text()
    block = re.search(r"APP_ICONS = \[(.*?)\]", js, re.S)
    assert block, f"{app}/lib/icons.js has no APP_ICONS array"
    return re.findall(r"'(lucide-[\w-]+)'", block.group(1))


INTERPOLATED_ICON = re.compile(r"""lucide-\$\{|['"`]lucide-['"`]\s*\+|\+\s*['"`]lucide-""")


@pytest.mark.parametrize("app", APPS)
def test_no_icon_class_is_built_by_interpolation(app):
    """`lucide-${name}` produces no CSS — the scanner cannot see what to emit."""
    root = ROOT / f"apps/{app}/frontend/src"
    offenders = [
        p.relative_to(root).as_posix()
        for p in sorted(root.rglob("*"))
        if p.suffix in (".vue", ".js") and INTERPOLATED_ICON.search(p.read_text())
    ]
    assert not offenders, (
        "icon classes built by interpolation emit no CSS: " + ", ".join(offenders)
    )


@pytest.mark.parametrize("app", APPS)
def test_every_registry_icon_emits_css(app):
    """The whole point of the generated set.

    App icons come from a doctype, so none of them would otherwise appear as a
    literal anywhere — which is exactly the case the icons page says to solve
    with a known set. If the set stops reaching the CSS, every app in the
    launcher silently loses its icon.
    """
    if not _built(app):
        pytest.skip(f"{app} has no built stylesheet; run vite build")

    names = _generated_icons(app)
    assert len(names) > 20, f"only found {len(names)} icons in the generated set"

    emitted = emitted_classes(app)
    missing = [n for n in names if n not in emitted]
    assert not missing, f"{app}: generated icons emit no CSS: {missing}"


def test_the_doctype_offers_exactly_the_generated_set():
    """The picker's options and the SPA's literals come from one list.

    A name the doctype allows but the SPA never writes as a literal is an icon
    an operator can pick and nobody can see.
    """
    import json
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from app_icons import APP_ICONS, DEFAULT_APP_ICON

    spec = json.loads(
        (
            ROOT
            / "apps/oneapp_control/oneapp_control/control_plane/doctype/oneapp_app/oneapp_app.json"
        ).read_text()
    )
    field = next(f for f in spec["fields"] if f["fieldname"] == "icon")
    assert field["fieldtype"] == "Select", "icon is free text again"
    assert field["options"].split("\n") == APP_ICONS
    assert field.get("default") == DEFAULT_APP_ICON

    for app in APPS:
        assert _generated_icons(app) == APP_ICONS, (
            f"{app}/lib/icons.js is out of date — run scripts/gen_frontend.py"
        )
