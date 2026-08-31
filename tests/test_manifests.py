"""Every manifest, checked against itself and against the doctypes it names.

A manifest is small enough to hold in your head until there are four of them,
and then it is not. These are the rules that were being kept by hand — each one
written because something had already quietly stopped working, or would have.

The rules read the *declarations*, not a running site: the manifests live in
`entitlements/operator.py` and `entitlements/account.py` as literals, and the
doctypes live in the generator. Both are files, so a manifest that does not add
up fails here rather than on the first site somebody installs it on.

The one this exists for: eighteen screens declared a `status_field`, and not one
of the doctypes behind them declared a single Document State. The badges were
not colourless — `valueTheme` falls through to Frappe's word list and guesses
from the text. "Failed" came out red because it contains "fail", and "Draining"
came out gray because it matches nothing. Neither was a decision anybody made,
and "Claimed" and "Ignored" and "Adjustment" were all the same shade of nothing.
"""

import json
import re
from pathlib import Path

import pytest

from doctype_paths import slug as doctype_slug

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "apps/oneapp_control/oneapp_control"

# Frappe's own list, from `DocType State.color`. Ours to pick from, not to
# extend: `lib/fields.js` maps exactly these ten onto badge themes, so an
# eleventh renders gray and says nothing.
COLORS = {
	"Blue", "Cyan", "Gray", "Green", "Light Blue",
	"Orange", "Pink", "Purple", "Red", "Yellow",
}


def doctypes() -> dict:
	found = {}
	for app, module in (("oneapp_control", "control_plane"), ("oneapp", "oneapp_core")):
		root = ROOT / "apps" / app / app / module / "doctype"
		if not root.is_dir():
			continue
		for child in root.iterdir():
			path = child / f"{child.name}.json"
			if path.exists():
				doc = json.loads(path.read_text())
				found[doc["name"]] = doc
	return found


DOCTYPES = doctypes()

# Screens the operator console declares: (screen, label, icon, doctype, fields,
# status_field). Read out of the source rather than by importing it, because the
# module wants Frappe and this question does not.
SCREEN_ROW = re.compile(
	r'\(\s*"(?P<screen>[\w-]+)",\s*"[^"]*",\s*"[^"]*",\s*"(?P<doctype>[^"]+)",\s*\n?\s*'
	r'"(?P<fields>[^"]*)",\s*\n?\s*"(?P<status>\w*)"\s*\)',
	re.S,
)


def operator_screens() -> list[dict]:
	source = (CONTROL / "entitlements/operator.py").read_text()
	block = source[source.index("SCREENS = ("):source.index("COMPONENTS = (")]
	return [m.groupdict() for m in SCREEN_ROW.finditer(block)]


SCREENS = operator_screens()


def test_the_reader_found_the_screens():
	"""A regex that silently matches nothing turns every rule below into a pass."""
	assert len(SCREENS) > 15, f"only parsed {len(SCREENS)} screens out of the console"
	assert any(s["screen"] == "tenants" for s in SCREENS)


# --------------------------------------------------------------------------- #
# A status is a colour somebody chose
# --------------------------------------------------------------------------- #

STATUS_SCREENS = [s for s in SCREENS if s["status"]]


def test_most_screens_show_a_status():
	assert len(STATUS_SCREENS) > 10, "the status badges have gone"


@pytest.mark.parametrize("screen", STATUS_SCREENS, ids=lambda s: s["screen"])
def test_a_status_field_is_a_select_on_its_own_doctype(screen):
	doc = DOCTYPES.get(screen["doctype"])
	assert doc, f"{screen['screen']} names {screen['doctype']}, which is not ours"

	field = next(
		(f for f in doc["fields"] if f["fieldname"] == screen["status"]), None
	)
	assert field, (
		f"{screen['screen']} calls {screen['status']!r} its status and "
		f"{screen['doctype']} has no such field"
	)
	assert field["fieldtype"] == "Select", (
		f"{screen['screen']}: a status badge over a {field['fieldtype']} is a "
		f"badge over free text — there is no closed set of values to colour"
	)


@pytest.mark.parametrize("screen", STATUS_SCREENS, ids=lambda s: s["screen"])
def test_every_option_of_a_status_has_a_declared_colour(screen):
	"""The rule this file exists for.

	Not declaring one does not mean "no colour". `valueTheme` falls through to
	Frappe's word list and guesses from the text, so half the values come out
	right by accident and the rest come out gray — and which is which is not
	something anybody decided.
	"""
	doc = DOCTYPES[screen["doctype"]]
	field = next(f for f in doc["fields"] if f["fieldname"] == screen["status"])

	options = [o for o in (field.get("options") or "").split("\n") if o.strip()]
	declared = {state["title"] for state in doc.get("states") or []}

	missing = [o for o in options if o not in declared]
	assert not missing, (
		f"{screen['doctype']}.{screen['status']} is shown as a badge on the "
		f"{screen['screen']} screen, and {missing} have no declared colour — so "
		f"the word list guesses one. Add them to `states=` in gen_doctypes.py."
	)


@pytest.mark.parametrize("name", sorted(n for n, d in DOCTYPES.items() if d.get("states")))
def test_a_declared_state_is_a_real_option_in_a_real_colour(name):
	"""The inverse, and it catches a rename: a state whose title no longer
	matches any option is a colour that will never be used, and nothing else
	would ever say so."""
	doc = DOCTYPES[name]
	selects = {
		f["fieldname"]: [o for o in (f.get("options") or "").split("\n") if o.strip()]
		for f in doc["fields"]
		if f["fieldtype"] == "Select"
	}
	every_option = {value for options in selects.values() for value in options}

	for state in doc["states"]:
		assert state["color"] in COLORS, (
			f"{name}: {state['color']!r} is not one of Frappe's ten, so "
			f"`STATE_COLORS` maps it to gray"
		)
		assert state["title"] in every_option, (
			f"{name}: a state is declared for {state['title']!r} and no Select "
			f"on this doctype offers it — a renamed option leaves its colour behind"
		)


def test_the_ui_maps_every_colour_frappe_offers():
	"""A colour the doctype may hold and the SPA cannot read renders gray."""
	fields = (ROOT / "apps/oneapp/frontend/src/lib/fields.js").read_text()
	block = fields[fields.index("export const STATE_COLORS"):]
	block = block[: block.index("}")]
	for color in COLORS:
		assert f'"{color}"' in block, f"the SPA no longer maps {color}"


# --------------------------------------------------------------------------- #
# A screen only shows what the manifest granted
# --------------------------------------------------------------------------- #

def granted_doctypes() -> set:
	source = (CONTROL / "entitlements/operator.py").read_text()
	block = source[source.index("DOCTYPES = ("):source.index("SCREENS = (")]
	return set(re.findall(r'"([^"]+)"', block))


@pytest.mark.parametrize("screen", SCREENS, ids=lambda s: s["screen"])
def test_a_screen_shows_a_doctype_the_space_granted(screen):
	"""The manifest is an allowlist by construction: a doctype in no manifest is
	reachable by nobody. A screen over one that was never granted renders an
	empty list and a permission error, and the two look like an empty table."""
	assert screen["doctype"] in granted_doctypes(), (
		f"the {screen['screen']} screen shows {screen['doctype']}, which the "
		f"space's DOCTYPES list does not grant"
	)


@pytest.mark.parametrize("screen", SCREENS, ids=lambda s: s["screen"])
def test_every_column_a_screen_names_is_a_real_field(screen):
	"""A fieldname that does not exist is dropped silently on the way through
	`_columns` — the screen simply opens one column short, which reads as a
	design decision rather than a typo."""
	doc = DOCTYPES.get(screen["doctype"])
	if not doc:
		pytest.skip(f"{screen['doctype']} is not ours")

	known = {f["fieldname"] for f in doc["fields"]} | {"name", "modified", "owner", "creation"}
	named = [f.strip() for f in screen["fields"].split(",") if f.strip()]
	unknown = [f for f in named if f not in known]
	assert not unknown, (
		f"the {screen['screen']} screen names {unknown}, which {screen['doctype']} "
		f"does not have — the column is dropped and the screen opens short"
	)


# --------------------------------------------------------------------------- #
# ...and a glyph, from the same place
# --------------------------------------------------------------------------- #

def _state_icons() -> set:
	import sys

	sys.path.insert(0, str(ROOT / "scripts"))
	from app_icons import STATE_ICONS as icons

	return set(icons)


def test_every_status_value_earns_a_glyph():
	"""A badge carries a colour and an icon, and neither may be absent.

	Derived from the words rather than declared, because the alternative is
	typing an icon beside all fifty-odd Select options and the words already say
	it — `Failed` and `Broken` mean the same thing to a reader. What has to hold
	is that *every* value resolves to one: a list where half the badges carry a
	glyph reads as broken rather than as varied, which is why the fallback is a
	neutral tag rather than nothing.
	"""
	import sys

	sys.path.insert(0, str(ROOT / "scripts"))
	from app_icons import state_icon

	icons = _state_icons()
	unresolved = []
	for screen in STATUS_SCREENS:
		doc = DOCTYPES[screen["doctype"]]
		field = next(f for f in doc["fields"] if f["fieldname"] == screen["status"])
		for option in (field.get("options") or "").split("\n"):
			if not option.strip():
				continue
			got = state_icon(option)
			if got not in icons:
				unresolved.append(f"{screen['doctype']}.{option} -> {got!r}")
	assert not unresolved, (
		"these status values resolve to an icon outside the closed set, so "
		"Tailwind emits no CSS for them and the badge draws an empty box: "
		+ ", ".join(unresolved)
	)


def test_the_glyphs_reach_the_spa_as_literals():
	"""The closed-set argument, again. Tailwind emits CSS only for class names
	it finds written out in the source, so a glyph that exists only in Python
	draws nothing."""
	fields = (ROOT / "apps/oneapp/frontend/src/lib/fields.js").read_text()
	block = fields[fields.index("export const STATE_ICONS"):]
	block = block[: block.index("]")]
	for icon in _state_icons():
		assert f'"{icon}"' in block, f"{icon} is not written into the SPA"


def test_a_badge_and_its_select_draw_the_same_glyph():
	"""One function, two callers. A value that looks one way being chosen and
	another way once chosen is the kind of thing nobody reports and everybody
	notices."""
	cell = (ROOT / "apps/oneapp/frontend/src/components/screen/FieldCell.vue").read_text()
	control = (ROOT / "apps/oneapp/frontend/src/components/screen/FieldControl.vue").read_text()
	assert "valueIcon(value, states)" in cell
	assert "valueIcon(value, props.states)" in control


# --------------------------------------------------------------------------- #
# Tab icons
#
# Every tab in OneSpace carries a glyph, and none of them is declared twice.
# Frappe has no icon property on a Tab Break, so the glyph is derived from the
# tab's own label — the same argument the status glyphs make, for the same
# reason: a doctype we do not own will never have a manifest entry and should
# still get something better than a bare word.
# --------------------------------------------------------------------------- #


def _tab_icons() -> tuple:
	import sys

	sys.path.insert(0, str(ROOT / "scripts"))
	from app_icons import DEFAULT_TAB_ICON, TAB_ICONS, TAB_ICON_WORDS, tab_icon

	return DEFAULT_TAB_ICON, TAB_ICONS, TAB_ICON_WORDS, tab_icon


def test_every_tab_glyph_is_in_the_closed_set():
	"""A name outside it emits no CSS and draws an empty box."""
	default, icons, words, _ = _tab_icons()
	stray = [icon for icon, _ in words if icon not in icons]
	assert not stray, f"these are derived and never written out: {stray}"
	assert default in icons


def test_every_tab_the_spa_names_earns_a_glyph():
	"""Every tab label written out in the SPA, resolved.

	Two kinds of tab reach `tabIcon`. The doctype's own Tab Breaks are one, and
	they cannot be enumerated here — our doctypes group with Section Breaks and
	declare no Tab Break at all, so the labels the derivation actually sees are
	ERPNext's and whatever a customer's site adds. That half is covered by the
	fallback being an icon rather than nothing.

	The other kind is the fixed tabs over a record, which *are* written out, as
	`tabIcon('Details')` and its three siblings. Those are the ones that can go
	wrong by being added without a thought, so those are the ones checked: a
	fifth tab whose label falls through to the neutral panel is named here
	rather than noticed in a screenshot.
	"""
	_, icons, _, tab_icon = _tab_icons()
	root = ROOT / "apps/oneapp/frontend/src"
	labels = sorted({
		match.group(1)
		for path in root.rglob("*.vue")
		for match in re.finditer(r"tabIcon\('([^']+)'", path.read_text())
	})
	assert len(labels) >= 4, f"only found {labels} — the record's tabs have moved"

	fell_through = {label: tab_icon(label) for label in labels}
	unresolved = [f"{k} -> {v!r}" for k, v in fell_through.items() if v not in icons]
	assert not unresolved, (
		"these resolve to an icon outside the closed set: " + ", ".join(unresolved)
	)
	# And none of them lands on the fallback: these four are ours, and a tab we
	# named ourselves earning the neutral panel means the word list is missing a
	# word rather than that the tab is unusual.
	default = _tab_icons()[0]
	bare = [k for k, v in fell_through.items() if v == default]
	assert not bare, (
		"these are our own tabs and they earn nothing but the neutral panel — "
		"add the word to TAB_ICON_WORDS: " + ", ".join(bare)
	)


def test_the_tab_glyphs_reach_the_spa_as_literals():
	"""The closed-set argument, again. Tailwind emits CSS only for class names
	it finds written out in the source."""
	_, icons, _, _ = _tab_icons()
	fields = (ROOT / "apps/oneapp/frontend/src/lib/fields.js").read_text()
	block = fields[fields.index("export const TAB_ICONS"):]
	block = block[: block.index("]")]
	for icon in icons:
		assert f'"{icon}"' in block, f"{icon} is not written into the SPA"


def test_a_declared_tab_icon_is_one_of_ours():
	"""The manifest override, checked.

	`tab_icons` on a screen names an icon per tab label — the escape hatch for a
	tab whose words earn the wrong glyph. The browser falls back to the derived
	one when the name is not in the set, so a typo is quiet rather than broken;
	this is what makes it loud for a manifest we ship.
	"""
	_, icons, _, _ = _tab_icons()
	offenders = []
	for path in sorted((ROOT / "apps").rglob("*.py")):
		source = path.read_text()
		if '"tab_icons"' not in source:
			continue
		for match in re.finditer(r'"tab_icons"\s*:\s*(\'\'\'|"""|")(.*?)\1', source, re.S):
			try:
				declared = json.loads(match.group(2))
			except ValueError:
				offenders.append(f"{path.name}: tab_icons is not JSON")
				continue
			for label, icon in (declared or {}).items():
				if icon not in icons:
					offenders.append(f"{path.name}: {label} -> {icon!r}")
	assert not offenders, (
		"these declared tab icons are outside the closed set, so the browser "
		"quietly falls back to the derived one: " + ", ".join(offenders)
	)
