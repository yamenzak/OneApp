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

import where

from vendored import is_vendored
from token_audit import APPS, ROOT, audit, class_lists, emitted_classes, referenced_classes
from gen_frontend import APPS as SPECS

# Bundles that render the shell. Only they have a space launcher, so only they
# generate `lib/icons.js` — the signup page has no space to draw an icon for.
SHELL_APPS = tuple(app for app, spec in SPECS.items() if spec.get("shell"))

# How many distinct utilities each bundle is expected to reference. Not one
# number, because they are not one size: the tenant app is a whole product and
# the signup bundle is two pages. What both are guarding against is the
# extractor quietly returning nothing, which is what makes the comparison pass
# vacuously.
FLOOR = {"oneapp": 60, "oneapp_control": 20}


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
    assert len(referenced) > FLOOR[app], (
        f"{app}: only found {len(referenced)} classes in source"
    )
    assert len(emitted) > 300, f"{app}: only found {len(emitted)} classes in the CSS"
    # A class we know is used and valid, proving the two sides line up. The
    # darkest ink is on every page either bundle has, which is what makes it a
    # witness rather than a coincidence.
    assert "text-ink-gray-9" in referenced and "text-ink-gray-9" in emitted


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
    """The names inside lib/icons.js's SPACE_ICONS array.

    Scoped to the array: DEFAULT_SPACE_ICON below it is another `lucide-*` literal
    and would otherwise be counted as a 27th icon.
    """
    js = (ROOT / f"apps/{app}/frontend/src/modules/onespace/lib/shell/icons.js").read_text()
    block = re.search(r"SPACE_ICONS = \[(.*?)\]", js, re.S)
    assert block, f"{app}/lib/icons.js has no SPACE_ICONS array"
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


@pytest.mark.parametrize("app", SHELL_APPS)
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
    from app_icons import SPACE_ICONS, DEFAULT_SPACE_ICON

    spec = json.loads(
        (
            ROOT
            / "apps/oneapp_control/oneapp_control/control_plane/doctype/onespace_space/onespace_space.json"
        ).read_text()
    )
    field = next(f for f in spec["fields"] if f["fieldname"] == "icon")
    assert field["fieldtype"] == "Select", "icon is free text again"
    assert field["options"].split("\n") == SPACE_ICONS
    assert field.get("default") == DEFAULT_SPACE_ICON

    for app in SHELL_APPS:
        assert _generated_icons(app) == SPACE_ICONS, (
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
        "const method = 'oneapp.onespace.spaceview.rows'",
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
        "ScreenHost" in path for path in referenced["bg-surface-base"]
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


# --------------------------------------------------------------------------- #
# One breakpoint
#
# `lib/shell/breakpoint.js` chooses 768 and says why: DesktopShell and
# MobileShell are different components, so something has to choose, and 768 is
# Tailwind's `md` so anything branching in CSS agrees without a second number
# to keep in step. The code then branched 77 times at `sm:` (640) and 12 at
# `md:` — and between 640 and 767 the shell was mobile while every `sm:` rule
# had already turned the content desktop. Mail was the clearest case: a
# two-pane mail client inside a bottom-bar shell on a 700px tablet.
# `docs/UNIFICATION.md` §D4.
#
# `sm:` stays legal for the two things that genuinely step twice — page
# padding and type size — because those are "more room on a bigger screen"
# rather than "this is the other layout".
# --------------------------------------------------------------------------- #

#: What makes a utility a *layout* decision rather than a breathing-room one.
LAYOUT_AT = re.compile(
	r"^sm:(grid-cols-|grid$|flex$|flex-row|flex-col|flex-none|flex-1|flex-wrap"
	r"|flex-nowrap|hidden$|block$|inline|table$|contents$|w-|min-w-|max-w-|h-"
	r"|min-h-|max-h-|size-|col-span|row-span|basis-|self-|items-|justify-"
	r"|order-|absolute$|relative$|fixed$|static$|sticky$|top-|bottom-|start-"
	r"|end-|left-|right-|inset-|overflow-|columns-)"
)


#: The one place `sm:` is right for layout, and it is right because it is not
#: ours. frappe-ui's SettingsDialog is `w-screen h-[100dvh]` below 640 and a
#: window with a backdrop above it, so everything inside that dialog — the nav
#: reflow in `geometry.js`, the panels' field grids, our own close control —
#: has to switch where the library switches. Matching the library beats
#: matching ourselves here, and a dialog is a world of its own anyway.
LIBRARY_GEOMETRY = "components/settings/"


@pytest.mark.parametrize("app", APPS)
def test_layout_branches_at_the_shell_s_own_breakpoint(app):
	offenders = []
	for blob, rel in class_lists(app):
		if LIBRARY_GEOMETRY in str(rel):
			continue
		for token in blob.split():
			if LAYOUT_AT.match(token.lstrip("!")):
				offenders.append(f"{rel}: `{token}` in `{blob.strip()[:70]}`")
	assert not offenders, (
		"these lay out at 640 while the shell switches at 768, so between the "
		"two the page is a mobile shell around a desktop layout:\n"
		+ "\n".join(sorted(set(offenders)))
		+ "\n\nUse `md:` — the number `breakpoint.js` picked. `sm:` stays "
		"legal for page padding and type size, which step for a different "
		"reason."
	)


def test_the_breakpoint_scan_would_catch_one():
	"""The rule is only worth having if the scan can see an offender — and
	four guards in this repo failed the day they were audited because their
	pattern missed where the code actually was. `docs/UNIFICATION.md` §F1."""
	assert LAYOUT_AT.match("sm:grid-cols-2")
	assert LAYOUT_AT.match("sm:flex")
	assert LAYOUT_AT.match("sm:hidden")
	assert LAYOUT_AT.match("sm:w-96")
	assert LAYOUT_AT.match("!sm:items-end".lstrip("!"))
	# And cannot see the two that are allowed to stay.
	assert not LAYOUT_AT.match("sm:px-5")
	assert not LAYOUT_AT.match("sm:text-5xl")


def test_the_shell_and_the_css_name_the_same_number():
	"""The guard above is worthless if `breakpoint.js` moves and nobody looks."""
	source = where.spa("oneapp", "src/lib/shell/breakpoint.js").read_text()
	assert "MOBILE_MAX = 767" in source, (
		"the shell's breakpoint moved; the layout utilities have to move with it"
	)


def test_the_settings_exemption_is_only_the_settings_dialog():
	"""An exemption nobody checks is a hole. This one covers one directory, and
	the reason it exists is the library's own breakpoint — so if the settings
	panels stop living there, the exemption stops applying with them."""
	assert LIBRARY_GEOMETRY == "components/settings/"
	geometry = (
		ROOT / "apps/oneapp/frontend/src/modules/onespace/components/settings/geometry.js"
	).read_text()
	assert "max-sm:" in geometry, (
		"the settings reflow moved off the library's breakpoint; the exemption "
		"in test_layout_branches_at_the_shell_s_own_breakpoint should go with it"
	)


# --------------------------------------------------------------------------- #
# One type scale, two roles
#
# `text-p-*` and `text-*` carry the same sizes at different leading — 1.5–1.6
# against 1.15 — so one is prose and the other is labels. That is a good
# system and nobody wrote the rule down, so the choice was made by whoever
# typed the class: 111 elements were declared single-line with `truncate` and
# then given paragraph leading, which is about 4px of extra height on every
# one of them and most of why dense surfaces read loose.
# `docs/UNIFICATION.md` §A1.
# --------------------------------------------------------------------------- #

#: What says "this text is one line and will not wrap".
SINGLE_LINE = re.compile(r"\b(truncate|whitespace-nowrap|line-clamp-1)\b")

#: The prose scale. Sized for a paragraph, led for a paragraph.
PROSE_SIZE = re.compile(r"\btext-p-(xs|sm|base|lg)\b")

#: Which label class carries the same size, for the failure message.
SAME_SIZE = {"text-p-xs": "text-xs", "text-p-sm": "text-sm",
             "text-p-base": "text-base", "text-p-lg": "text-lg"}


@pytest.mark.parametrize("app", APPS)
def test_single_line_text_does_not_wear_paragraph_leading(app):
	offenders = []
	for blob, rel in class_lists(app):
		if not SINGLE_LINE.search(blob):
			continue
		for found in PROSE_SIZE.findall(blob):
			name = f"text-p-{found}"
			offenders.append(f"{rel}: `{name}` beside `truncate` — use `{SAME_SIZE[name]}`")
	assert not offenders, (
		"these are declared single-line and then given a paragraph's leading:\n"
		+ "\n".join(sorted(set(offenders)))
		+ "\n\n`text-p-*` is 1.5–1.6 and `text-*` is 1.15, at the same sizes. "
		"A label, a number, a chip, a cell or a crumb is `text-*`; anything "
		"that may run to a second line is `text-p-*`."
	)


def test_the_leading_scan_would_catch_one():
	"""A witness, because four guards in this repo failed their audit for want
	of one. `docs/UNIFICATION.md` §F1."""
	assert SINGLE_LINE.search("truncate text-p-sm text-ink-gray-5")
	assert PROSE_SIZE.findall("truncate text-p-sm text-ink-gray-5") == ["sm"]
	# And it does not fire on the two correct shapes.
	assert not PROSE_SIZE.findall("truncate text-sm text-ink-gray-5")
	assert not SINGLE_LINE.search("text-p-sm text-ink-gray-6")


# --------------------------------------------------------------------------- #
# Ink is asked for by role
#
# frappe-ui's grey scale is nine steps and seven of them were in use, but only
# three roles were being expressed: the thing you read, the thing beside it,
# and the thing you only notice when you look for it. Which grey said which
# was whatever the call site typed — `-6` against `-7` most of all, 79 uses
# scattered one or two to a file across forty-five files with no pattern in
# them. The roles are named in `scripts/spa/build.py`; these refuse the
# numbers the roles replaced. `docs/UNIFICATION.md` §A1.
# --------------------------------------------------------------------------- #

#: The four steps that now have a name. `-1`, `-2`, `-3`, `-4` and `-9` keep
#: their numbers: they are edge levels with jobs of their own — a hairline, a
#: disabled control, a placeholder, black over a photograph.
NUMBERED_INK = re.compile(r"\b(?:text|placeholder|fill|stroke|decoration)-ink-gray-[5-8]\b")

#: What to write instead.
INK_ROLE = {"5": "muted", "6": "secondary", "7": "secondary", "8": "primary"}


@pytest.mark.parametrize("app", APPS)
def test_ink_is_asked_for_by_role(app):
	offenders = []
	for blob, rel in class_lists(app):
		for found in NUMBERED_INK.findall(blob):
			prefix, _, step = found.rpartition("-")
			role = prefix.replace("-ink-gray", "-ink-") + INK_ROLE[step]
			offenders.append(f"{rel}: `{found}` — use `{role}`")
	assert not offenders, (
		"these ask for a grey by number where a role exists:\n"
		+ "\n".join(sorted(set(offenders)))
		+ "\n\n`ink-primary` is what you read, `ink-secondary` what is beside "
		"it, `ink-muted` what you only notice when you look. The numbers that "
		"are left — 1 to 4, and 9 — are edge levels, not quieter versions of "
		"these."
	)


def test_the_ink_scan_would_catch_one():
	assert NUMBERED_INK.findall("truncate text-sm text-ink-gray-7") == ["text-ink-gray-7"]
	assert NUMBERED_INK.findall("hover:text-ink-gray-8") == ["text-ink-gray-8"]
	# And leaves the roles, the edge levels and the other ink families alone.
	assert not NUMBERED_INK.findall("text-ink-secondary text-ink-gray-4 text-ink-red-3")


def test_the_two_quietest_greys_are_one_colour_in_dark():
	"""Why `ink-muted` is `-5` and `-4` is not simply a quieter version of it.

	Read off frappe-ui's own token data: in dark mode `ink-gray-4` and
	`ink-gray-5` both resolve to `darkMode/gray/400`. They are the same colour.
	So a design that separates two things by putting one at `-4` and the other
	at `-5` separates them in light and not at all in dark — which is why the
	role stops at `-5` and `-4` means placeholder or disabled rather than
	"quieter than muted".

	If upstream ever gives them different values this fails, and the right
	answer is then to look again rather than to edit the number here.
	"""
	import json

	colors = json.loads(
		(ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/tailwind/generated/colors.json")
		.read_text()
	)
	dark = colors["themedVariables"]["dark"]["ink"]
	assert dark["gray-4"] == dark["gray-5"], (
		"ink-gray-4 and ink-gray-5 are different colours in dark now — the "
		"comment in scripts/spa/build.py and this test's premise are stale"
	)
	# And in light they are genuinely apart, which is what made the mistake
	# invisible to anyone working in one theme.
	light = colors["themedVariables"]["light"]["ink"]
	assert light["gray-4"] != light["gray-5"]


# --------------------------------------------------------------------------- #
# A shadow is a height, and a height has a name
#
# Three floating bars sat at three elevations — the undo bar at `xl`, the drop
# bar at `lg`, the selection bar at `2xl` — which is not a design, it is the
# order they were written in. Three names now: `raised` for a card in the flow,
# `floating` for a panel anchored inside a surface, `over` for something fixed
# above the whole page. Flat is no class at all.
# `docs/UNIFICATION.md` §A1.
# --------------------------------------------------------------------------- #

RAW_SHADOW = re.compile(r"(?<![\w-])!?shadow(?:-(?:sm|base|md|lg|xl|2xl))?(?![\w-])")


@pytest.mark.parametrize("app", APPS)
def test_shadows_are_named_by_height(app):
	offenders = []
	for blob, rel in class_lists(app):
		for found in RAW_SHADOW.findall(blob):
			offenders.append(f"{rel}: `{found}`")
	assert not offenders, (
		"these name a shadow by its step rather than by its height:\n"
		+ "\n".join(sorted(set(offenders)))
		+ "\n\n`shadow-raised` is a card in the flow of the page. "
		"`shadow-floating` is a panel anchored inside a surface — a popover, a "
		"menu, a cluster of controls over a map. `shadow-over` is fixed above "
		"the whole page — a drawer, a toast, the selection bar. Flat is no "
		"class at all."
	)


def test_the_shadow_scan_would_catch_one():
	assert RAW_SHADOW.findall("rounded-6 shadow-2xl bg-surface-elevation-2") == ["shadow-2xl"]
	assert RAW_SHADOW.findall("p-2 shadow") == ["shadow"]
	# The named heights pass, and so does anything that merely contains the word.
	assert not RAW_SHADOW.findall("shadow-raised shadow-floating shadow-over")
	assert not RAW_SHADOW.findall("drop-shadow text-white")


# --------------------------------------------------------------------------- #
# The second use of an arbitrary value is a token
#
# Used once, `h-[62vh]` is a one-off. Used in two files it is a measurement
# nobody named, re-derived at each call site and free to drift — which it did:
# two print previews doing the same job, one at 62vh and one at 70vh. The
# tokens are in `scripts/spa/build.py`. `docs/UNIFICATION.md` §A1.
# --------------------------------------------------------------------------- #

ARBITRARY = re.compile(r"(?<![\w-])!?[a-z][a-z0-9-]*-\[[^\]\s]+\](?![\w-])")


def test_an_arbitrary_value_is_used_in_one_file_only():
	homes = {}
	for app in APPS:
		for blob, rel in class_lists(app):
			for found in ARBITRARY.findall(blob):
				homes.setdefault(found.lstrip("!"), set()).add(f"{app}/{rel}")
	spread = {value: files for value, files in homes.items() if len(files) > 1}
	assert not spread, (
		"these arbitrary values are written out in more than one file:\n"
		+ "\n".join(
			f"  {value} — {', '.join(sorted(files))}" for value, files in sorted(spread.items())
		)
		+ "\n\nThe second call site is the moment it becomes a measurement "
		"with a name. Add it to `theme.extend` in scripts/spa/build.py."
	)


def test_the_arbitrary_scan_reads_real_arbitrary_values():
	"""It found some — a scan that matches nothing passes vacuously."""
	found = {
		value
		for app in APPS
		for blob, _ in class_lists(app)
		for value in ARBITRARY.findall(blob)
	}
	assert len(found) >= 20, f"only {len(found)} arbitrary values seen — the scan is broken"
	assert ARBITRARY.findall("mx-auto max-w-[940px] p-4") == ["max-w-[940px]"]
	assert not ARBITRARY.findall("max-w-measure rounded-6")


def test_the_two_type_scales_have_the_same_steps():
	"""No hole to step outside of.

	A1 asked whether `text-2xs` had a prose sibling, on the reasoning that a
	scale with a gap in it is one people work around. It has: frappe-ui's own
	token data carries the same ten steps in both families, so the choice
	between them is always a choice of *role* and never of availability.
	"""
	import json

	typography = json.loads(
		(ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/tailwind/generated/typography.json")
		.read_text()
	)
	label = set(typography["fontSize"])
	prose = set(typography["paragraph"])
	assert prose <= label, f"the prose scale has steps the label scale lacks: {prose - label}"
	assert "2xs" in prose, "text-p-2xs is gone; text-2xs now has no sibling"


# --------------------------------------------------------------------------- #
# The bordered rectangle is a component
#
# `rounded-6 border border-outline-… bg-surface-…` was 33 class lists in 25
# files, in thirteen spellings differing only in ground and padding. It is the
# most duplicated markup in the product and the thing a reader sees more of
# than anything else, so every new one was a fresh decision about a number.
# `shared/components/Panel.vue` is the one version. `docs/UNIFICATION.md` §A2.
# --------------------------------------------------------------------------- #

def test_the_panel_shape_is_a_component():
	offenders = []
	for app in APPS:
		for blob, rel in class_lists(app):
			classes = blob.split()
			if (
				"rounded-6" in classes
				and any(c.startswith("border-outline-") for c in classes)
				and any(c.startswith("bg-surface-") for c in classes)
			):
				offenders.append(f"{app}/{rel}: {blob[:80]}")
	assert not offenders, (
		"these draw a panel by hand:\n"
		+ "\n".join(sorted(set(offenders)))
		+ "\n\n<Panel> has the radius and the border built in and takes "
		"`ground` (base / raised / sunken), `pad` (none / tight / normal / "
		"loose / bar), `elevation` and `tone`. Anything else it does not own "
		"still goes in `class`."
	)


def test_the_panel_scan_would_catch_one():
	def hits(blob):
		classes = blob.split()
		return (
			"rounded-6" in classes
			and any(c.startswith("border-outline-") for c in classes)
			and any(c.startswith("bg-surface-") for c in classes)
		)

	assert hits("flex flex-col gap-3 rounded-6 border border-outline-gray-2 bg-surface-base p-4")
	# A panel call site keeps its layout classes, and those must not trip it.
	assert not hits("flex flex-col gap-3")
	# Nor must a rounded thing that is not a panel: a chip, a card with no
	# border, a dropzone whose ground is conditional.
	assert not hits("rounded-6 bg-surface-gray-3 px-3 py-2")
	assert not hits("rounded-6 border border-dashed border-outline-gray-2 py-12")


def test_the_panel_component_is_generated_for_both_bundles():
	"""The signup page draws panels too, and a panel that looks different on
	the way in is the first thing a customer sees."""
	for app in APPS:
		path = where.spa(app, "src/components/Panel.vue")
		assert path.exists(), f"{app} has no Panel.vue at {path}"
		text = path.read_text()
		assert "Generated by scripts/gen_frontend.py" in text
		for name in ("GROUND", "PAD", "ELEVATION"):
			assert f"const {name}" in text, f"{app}: Panel lost {name}"


# --------------------------------------------------------------------------- #
# Nothing lives in shared/ until two modules need it
#
# `shared/` fills up with things that *look* general and then the next surface
# that needs the same thing builds its own — which is F1's root cause with the
# folder name attached. PresenceStrip was the case in point: the document
# editor imported it and the workbook hand-rolled the same row of faces in
# vendored CSS. `docs/UNIFICATION.md` §A2.
# --------------------------------------------------------------------------- #

def _module_of(path: str) -> str:
	"""Which module a file belongs to, or 'shared'."""
	parts = path.split("/")
	if parts[0] == "modules":
		return parts[1]
	return parts[0]


def test_a_shared_component_is_shared():
	"""Two modules, or one other shared file — otherwise it is not shared.

	A part used only by another shared component (RecordPicker inside
	RecordPanel) is a private part of something that *is* shared, which is
	fine. A part used by one module is a file in the wrong folder. A part used
	by nobody is dead.
	"""
	root = where.spa("oneapp", "")
	sources = {
		path: path.read_text()
		for path in root.rglob("*")
		if path.suffix in (".vue", ".js") and path.is_file()
	}
	offenders = []
	for path in sorted((root / "shared/components").rglob("*.vue")):
		spec = str(path.relative_to(root))
		importers = {
			_module_of(str(other.relative_to(root)))
			for other, text in sources.items()
			if other != path and spec in text
		}
		if len(importers) < 2 and importers != {"shared"}:
			offenders.append(
				f"{spec}: imported by {sorted(importers) or 'nobody'}"
			)
	assert not offenders, (
		"these are in shared/ without being shared:\n"
		+ "\n".join(offenders)
		+ "\n\nEither the second caller exists and should be using it, or it "
		"belongs beside the one module that does, or it is dead."
	)


# --------------------------------------------------------------------------- #
# A row has five states and they must all be legible at once
#
# `bg-surface-gray-2` was the hover, the selected file, the open mail thread,
# the current version and the open record — one colour carrying three
# different statements. The engine's own rows had no hover at all, and
# `focus-visible` appeared once in the whole built stylesheet.
# `shared/lib/rowstate.js` is the one version. `docs/UNIFICATION.md` §B4.
# --------------------------------------------------------------------------- #

#: A row is a repeated element that responds to a pointer or a click.
ROW_ELEMENT = re.compile(r"<[a-zA-Z][\w.-]*\b[^>]*\bv-for=", re.S)

#: What a row may not decide for itself any more.
OWN_STATE = re.compile(r"hover:bg-surface-|\bfocus-visible:")


def test_a_row_does_not_invent_its_own_states():
	"""The states are `rowState()`'s to give. A row that paints its own hover
	is a row that disagrees with the one on the next screen — which is how a
	hovered file and a selected file ended up the same colour."""
	root = where.spa("oneapp", "")
	offenders = []
	for path in sorted(root.rglob("*.vue")):
		rel = path.relative_to(root).as_posix()
		if rel.startswith("modules/onesheet/lib/"):
			continue
		text = path.read_text()
		for tag in ROW_ELEMENT.findall(text):
			if OWN_STATE.search(tag):
				offenders.append(f"{rel}: {re.sub(r'[$]s+', ' ', tag)[:90]}")
	assert not offenders, (
		"these repeated rows paint their own hover or focus:\n"
		+ "\n".join(sorted(set(offenders)))
		+ "\n\n`rowState({ selected, open, lifted, drop })` from "
		"`@/shared/lib/rowstate` is the one answer — hover lighter than "
		"selection, focus a ring, open a leading edge."
	)


def test_the_row_scan_would_catch_one():
	assert ROW_ELEMENT.search('<div v-for="one in rows" class="hover:bg-surface-gray-2">')
	assert OWN_STATE.search('class="hover:bg-surface-gray-2"')
	assert OWN_STATE.search('class="focus-visible:ring-2"')
	# A row that asks for the shared answer passes, and a non-repeated element
	# with its own hover — a button, a menu item — is not a row.
	assert not OWN_STATE.search(':class="rowState({ open })"')
	assert not ROW_ELEMENT.search('<button class="hover:bg-surface-gray-2">')


def test_the_five_states_are_five_different_things():
	"""Read off the module rather than asserted twice: hover and selection are
	different fills, and open and focus are neither of them."""
	source = where.spa("oneapp", "src/lib/rowstate.js").read_text()
	# The right-hand side up to the next declaration, with the quoting and the
	# `+` of a wrapped string taken out — two of these are long enough to be
	# written over two lines and a scan that read only the first would pass
	# vacuously on whichever half it happened to see.
	states = {
		name: re.sub(r"['\"+\s]+", " ", body).strip()
		for name, body in re.findall(
			r"export const (\w+) =(.*?)(?=\n\n|\nexport |\n/\*)", source, re.S
		)
	}
	assert states["HOVER"] != states["SELECTED"], "hover and selection are one colour again"
	assert "hover:bg-surface-gray-1" in states["HOVER"], "hover is no longer the lighter step"
	assert "bg-surface-gray-2" in states["SELECTED"]
	# Open is an edge and focus is a ring — the two decisions that let all
	# five stack on one row.
	assert "before:" in states["OPEN"] and "bg-" not in states["OPEN"].replace("before:bg-", "")
	assert "ring" in states["FOCUS"] and "bg-" not in states["FOCUS"]
	# And both are painted in the workspace's own accent, which is what
	# `lib/shell/theme.js` puts into these two tokens.
	assert "surface-gray-10" in states["OPEN"]
	assert "outline-gray-8" in states["FOCUS"]
	theme = where.spa("oneapp", "src/lib/shell/theme.js").read_text()
	assert "'--surface-gray-10'" in theme and "'--outline-gray-8'" in theme, (
		"the accent no longer paints the tokens the open edge and the focus "
		"ring read — they are now a grey that says nothing"
	)


def test_a_cell_does_not_compete_with_the_row_it_is_in():
	"""An editable cell greyed under the pointer while the row did nothing, so
	the cell read as the thing about to be acted on — and clicking it opens
	the record. Its affordance hangs off the row's hover now."""
	cell = where.spa(
		"oneapp", "src/components/screen/bodies/EditableCell.vue"
	).read_text()
	assert "hover:bg-surface" not in cell, "the cell paints its own fill again"
	assert "group-hover/row:" in cell, "the cell no longer follows the row's hover"
	source = where.spa("oneapp", "src/lib/rowstate.js").read_text()
	assert "group/row" in source, "nothing names the group the cell hangs off"


# --------------------------------------------------------------------------- #
# One row, and one fill under the pointer.
#
# Seventeen surfaces hand-rolled a line in a list, and they disagreed about
# everything: the padding, whether the whole row was the hit target, what
# hovering looked like. `shared/components/Row.vue` is the one version and
# `lib/rowstate.js` is the one vocabulary. `docs/UNIFICATION.md` §A2 and §B4.
# --------------------------------------------------------------------------- #

def test_one_hover_fill_and_it_is_here():
	"""There were five, and nobody had decided on any of them.

	`gray-1`, `gray-2`, `gray-3`, `white/15` and `white/10`, which meant a
	tile in the space switcher lit up harder than the row in the list beside
	it. The fill lives in `lib/rowstate.js` now and everything else imports
	it — a call site that wants a different one is saying the product should
	have two, which is a decision and belongs in that file.
	"""
	offenders = []
	for app in APPS:
		root = ROOT / f"apps/{app}/frontend/src"
		for path in sorted(root.rglob("*")):
			if path.suffix not in {".vue", ".js"} or not path.is_file():
				continue
			rel = path.relative_to(root)
			if rel.name == "rowstate.js" or is_vendored(path):
				continue
			if "hover:bg-" in path.read_text():
				offenders.append(f"{app}/{rel}")
	assert not offenders, (
		"these spell a hover fill of their own:\n"
		+ "\n".join(sorted(set(offenders)))
		+ "\n\nCompose <Row>, or import HOVER from lib/rowstate for something "
		"that is not a row."
	)


def test_the_hover_scan_reads_both_extensions():
	"""A class set in a `.js` const is the case the .vue-only scan missed —
	`SpaceSwitcher`'s TILE was exactly that shape, in a `.vue` script block."""
	seen = set()
	for app in APPS:
		root = ROOT / f"apps/{app}/frontend/src"
		seen |= {p.suffix for p in root.rglob("*") if p.suffix in {".vue", ".js"}}
	assert seen == {".vue", ".js"}


def test_a_row_is_a_component_now():
	"""The seventeen, and what each one stopped spelling for itself."""
	source = where.spa("oneapp", "src/components/Row.vue").read_text()
	# It derives the element rather than being told: a clickable `<div>` is
	# what four of the hand-rolled ones were, and neither the keyboard nor a
	# screen reader can reach one.
	assert "RouterLink" in source and "'button'" in source and "attrs.onClick" in source
	# And it goes through the one vocabulary rather than repeating its order.
	assert "rowState(" in source


def test_row_reaches_the_surfaces_that_had_their_own():
	"""Named rather than counted: a count goes stale quietly, a name does not."""
	adopted = [
		"src/pages/Mail.vue",
		"src/components/notifications/NotificationList.vue",
		"src/components/versions/VersionPanel.vue",
		"src/components/screen/record/AttachmentGallery.vue",
		"src/components/screen/record/RecordShowcase.vue",
		"src/components/screen/views/TallyMenu.vue",
		"src/components/settings/LegalSettings.vue",
	]
	missing = [
		one for one in adopted
		if "components/Row.vue" not in where.spa("oneapp", one).read_text()
	]
	assert not missing, f"these stopped composing <Row>: {missing}"


# --------------------------------------------------------------------------- #
# One picker.
#
# Five dialogs asked one question over a narrowable set and each had its own
# search, its own debounce and its own empty line — and four of them could not
# be driven from the keyboard. `docs/UNIFICATION.md` §A2.
# --------------------------------------------------------------------------- #

#: The `*Picker.vue` files that are not a search-and-choose dialog, and what
#: each one is instead. A new name here is a claim that wants reading: the
#: point of the list is that adding to it is visible.
NOT_A_DIALOG_PICKER = {
	# A field, not a dialog. A Link is an `Autocomplete` inside the form, and
	# putting a modal in the middle of typing a record is the change nobody
	# asked for.
	"LinkPicker.vue": "a field",
	# Three popovers over a grid of glyphs. One question, no list to narrow:
	# a grid is scanned rather than read, and a search box over twenty-six
	# icons is narrowing something you can already see.
	"IconPicker.vue": "a popover grid",
	"MarkerPicker.vue": "a popover grid",
	"ColorPicker.vue": "a popover grid",
	# Several answers and an order, which is two things `Picker` deliberately
	# does not do — a `multiple` prop with one caller is how a component
	# starts becoming two.
	"ColumnPicker.vue": "multi-select with an order",
	# Three tabs, one of which is a picker. The other two are an upload and a
	# camera, and they belong to §D3's one upload surface rather than here.
	"FilePicker.vue": "a three-tab attach dialog",
	# Somebody else's code, vendored whole.
	"PivotFieldPicker.vue": "vendored",
}


def test_a_picker_is_the_picker():
	offenders = []
	for app in APPS:
		root = ROOT / f"apps/{app}/frontend/src"
		for path in sorted(root.rglob("*Picker.vue")):
			if path.name == "Picker.vue" or path.name in NOT_A_DIALOG_PICKER:
				continue
			if "components/Picker.vue" not in path.read_text():
				offenders.append(f"{app}/{path.relative_to(root)}")
	assert not offenders, (
		"these ask one question over a narrowable set and answer it alone:\n"
		+ "\n".join(offenders)
		+ "\n\nCompose <Picker>, or say in NOT_A_DIALOG_PICKER what this is "
		"instead."
	)


def test_the_exemptions_still_exist():
	"""A name left behind after its file went is a hole in the guard nobody
	can see. `RolePicker.vue` was the reason this is here: it was in no
	import in the SPA at all, and the only thing that found it was counting."""
	names = set()
	for app in APPS:
		root = ROOT / f"apps/{app}/frontend/src"
		names |= {p.name for p in root.rglob("*Picker.vue")}
	stale = sorted(set(NOT_A_DIALOG_PICKER) - names)
	assert not stale, f"these are exempted and no longer exist: {stale}"


def test_the_picker_drives_from_the_keyboard():
	"""The half of this that did not exist anywhere: four of the five could
	only be used with a mouse, so the fastest way to choose a language was to
	type its name and then reach for the trackpad."""
	source = (ROOT / "apps/oneapp/frontend/src/shared/components/Picker.vue").read_text()
	for key in ("ArrowDown", "ArrowUp", "Home", "End", "Enter"):
		assert key in source, f"the picker no longer answers {key}"
	# On the search box, because that is where the caret is the whole time
	# somebody is choosing.
	assert 'data-slot="picker-search"' in source and "@keydown" in source


# --------------------------------------------------------------------------- #
# `shared/` is not an attic.
# --------------------------------------------------------------------------- #

def test_nothing_sits_in_shared_with_one_caller():
	"""A shared component with one caller is a file in the wrong folder.

	Six were extracted because they *looked* general, and then the next
	surface that needed the same thing built its own instead. The one
	allowance is a component whose single caller is itself in `shared/` —
	that is still not owned by a module, which is what the folder means.
	"""
	root = ROOT / "apps/oneapp/frontend/src"
	sources = {
		path: path.read_text()
		for path in root.rglob("*")
		if path.suffix in {".vue", ".js"} and path.is_file()
	}
	lonely = []
	for path in sorted((root / "shared/components").glob("*.vue")):
		callers = [
			other for other, text in sources.items()
			if other != path and f"shared/components/{path.name}" in text
		]
		if len(callers) >= 2:
			continue
		if len(callers) == 1 and "shared/" in str(callers[0].relative_to(root)):
			continue
		lonely.append(f"{path.name} ({len(callers)})")
	assert not lonely, (
		"these live in shared/ and are used once: "
		+ ", ".join(lonely)
		+ "\n\nMove it beside its caller, or give it its second."
	)


def test_no_row_is_given_an_element_and_a_click():
	"""`as` overrides what `<Row>` would have derived, and a click on a
	derived row is a `<button>`. Both together is a clickable `<li>` — which
	is the exact bug `<Row>` exists to stop, and the clause list in
	`LegalSettings` had it for one commit.
	"""
	offenders = []
	for app in APPS:
		root = ROOT / f"apps/{app}/frontend/src"
		for path in sorted(root.rglob("*.vue")):
			if path.name == "Row.vue":
				continue
			for use in re.finditer(r"<Row\b[^>]*?>", path.read_text(), re.S):
				tag = use.group(0)
				if re.search(r'\bas="', tag) and "@click" in tag:
					offenders.append(f"{app}/{path.relative_to(root)}")
	assert not offenders, (
		"these give <Row> both an element and a click, so the row is not "
		"focusable: " + ", ".join(sorted(set(offenders)))
		+ "\n\nDrop `as` and let it be the button, or move the click inside."
	)
