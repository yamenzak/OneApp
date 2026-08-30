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

from token_audit import APPS, ROOT, audit, class_lists, emitted_classes, referenced_classes


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


# --------------------------------------------------------------------------- #
# A class list can hide in a constant
#
# The scan looks for `class="…"`, `:class="…"` and `class: '…'`. A plain
# constant — `const STUCK = 'sticky right-0 z-10 bg-surface-white'` — matches
# none of them, and that is how a retired token got past this check and rendered
# a transparent column on top of the one beside it.
#
# Telling a class list from an English sentence is a heuristic, so these pin
# both directions of it.
# --------------------------------------------------------------------------- #

from token_audit import loose_class_lists  # noqa: E402


@pytest.mark.parametrize(
    "source",
    [
        "const STUCK = 'sticky right-0 z-10 bg-surface-white'",
        'const x = "flex min-w-0 items-center gap-2"',
        "const y = 'text-p-sm text-ink-gray-5'",
    ],
)
def test_a_class_list_in_a_constant_is_read(source):
    assert loose_class_lists(source), source


@pytest.mark.parametrize(
    "source",
    [
        # Prose, which is most strings in a component.
        "const label = 'Add to favourites'",
        "const empty = 'Nothing matches the filters. Clear one to widen the list.'",
        # Frappe's own vocabularies, which are words with spaces.
        "const span = 'last 7 days'",
        "const op = 'descendants of (inclusive)'",
        "const order = 'modified desc'",
        # One token is a name, not a list.
        "const icon = 'lucide-arrow-up'",
        "const method = 'oneapp.oneapp_core.appview.rows'",
        # A hyphenated English word is not enough on its own.
        "const note = 'a well-known thing happened'",
    ],
)
def test_prose_in_a_constant_is_not_read_as_classes(source):
    assert not loose_class_lists(source), source


def test_the_loose_scan_is_wired_into_the_audit():
    """End to end: a class list that lives only in a constant has to reach the
    referenced set, or the widening changed nothing."""
    referenced = referenced_classes("oneapp")
    assert "bg-surface-base" in referenced, "the constant scan is not reaching the audit"
    assert any(
        "AppHost" in path for path in referenced["bg-surface-base"]
    ), referenced["bg-surface-base"]


# --------------------------------------------------------------------------- #
# One radius language
#
# frappe-ui's own components draw four corner sizes and mean something
# different by each: `rounded-4` is a control (Button md, every input),
# `rounded-6` is a panel (its select banner), `rounded-7` is a Dialog, and
# `rounded-full` is a circle. Ours drifted — cards were drawn at both 8px and
# 12px, and a grey band ran into a square corner beside a rounded one.
#
# Two rules, because the drift had two shapes: a radius nobody named, and the
# same kind of block drawn two ways.
# --------------------------------------------------------------------------- #

# The whole vocabulary. Anything else is either a token frappe-ui retired or a
# fifth corner size nobody decided on.
RADIUS_ROLES = {
	"rounded-4": "a control — the size Button md and every input draw",
	"rounded-6": "a panel — a card, a dialog's inset block, a floating bar",
	"rounded-7": "a dialog, which is frappe-ui's own and never ours to set",
	"rounded-full": "a circle — an avatar, a dot, a count",
	# One radius, two halves, so a box and the button welded to it read as one
	# control rather than as two that happen to touch.
	"rounded-s-none": "the leading half of an input group",
	"rounded-e-none": "the trailing half of an input group",
}

# The panel radius. An outlined block is a card whatever else it is.
PANEL = "rounded-6"

RADIUS = re.compile(r"^(?:[\w:@\[\]&.,%#/()'\"*>+~=-]+:)?(rounded[\w-]*)$")


def _radii(blob: str) -> list[str]:
	"""The radius utilities in one class list, variants stripped."""
	found = []
	for token in blob.split():
		match = RADIUS.match(token.lstrip("!"))
		if match and match.group(1).startswith("rounded"):
			found.append(match.group(1))
	return found


@pytest.mark.parametrize("app", APPS)
def test_every_radius_is_one_of_the_four_we_named(app):
	offenders = []
	for blob, rel in class_lists(app):
		for radius in _radii(blob):
			if radius not in RADIUS_ROLES:
				offenders.append(f"{rel}: `{radius}` in `{blob.strip()[:70]}`")
	assert not offenders, (
		"these corner radii are not one of the ones this product draws:\n"
		+ "\n".join(sorted(set(offenders)))
		+ "\n\nThe vocabulary is:\n"
		+ "\n".join(f"  {name:16} {why}" for name, why in RADIUS_ROLES.items())
		+ "\n\nAdding a fifth is a design decision, not a class — make it in "
		"RADIUS_ROLES with a reason, or reach for one of these."
	)


@pytest.mark.parametrize("app", APPS)
def test_an_outlined_block_is_drawn_at_the_panel_radius(app):
	"""A card is a card, and every card has the same corners.

	This is the drift that showed: `rounded-4 border border-outline-gray-2 p-4`
	on the account pages and `rounded-6 border border-outline-gray-2` on the
	launcher, side by side in the same product, eight pixels apart.
	"""
	offenders = []
	for blob, rel in class_lists(app):
		tokens = set(blob.split())
		outlined = "border" in tokens and any(t.startswith("border-outline-") for t in tokens)
		if not outlined:
			continue
		for radius in _radii(blob):
			# A half-radius joins two controls, and a circle is a circle — a
			# colour swatch with an outline is not a card with square corners.
			if "-none" in radius or radius == "rounded-full":
				continue
			if radius != PANEL:
				offenders.append(f"{rel}: `{radius}` on `{blob.strip()[:70]}`")
	assert not offenders, (
		f"an outlined block is a panel, and a panel is `{PANEL}`:\n"
		+ "\n".join(sorted(set(offenders)))
	)


def test_the_radius_scan_reads_real_class_lists():
	"""Both rules pass vacuously if the scan finds nothing."""
	seen = [r for blob, _ in class_lists("oneapp") for r in _radii(blob)]
	assert len(seen) > 5, f"only found {len(seen)} radius utilities in the tenant app"
	assert PANEL in seen


@pytest.mark.parametrize("radius", sorted(RADIUS_ROLES))
def test_every_named_radius_still_exists_in_frappe_ui(radius):
	"""A role we named is worthless if the token behind it was retired.

	`rounded-lg` was a real class until v1 and emits nothing now; a vocabulary
	that names a dead token reads as unified and renders square.
	"""
	if not _built("oneapp"):
		pytest.skip("oneapp has no built stylesheet; run vite build")
	# A radius we only ever write under a variant is emitted under that
	# variant's escaped selector — `[&_input]:rounded-e-none` — so the bare
	# token is not in the sheet even though the rule is.
	emitted = emitted_classes("oneapp")
	assert any(name == radius or name.endswith(":" + radius) for name in emitted), (
		f"`{radius}` emits no CSS, under any variant"
	)
