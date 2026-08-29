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
        f"{app}: `{cls}` emits no CSS — retired token or typo ({', '.join(sorted(files))})"
        for cls, files in sorted(missing.items())
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
