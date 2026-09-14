"""Every screen a space declares, checked against the doctype behind it.

This is the file the three ERPNext spaces needed to exist. A manifest is a
declaration about somebody else's schema, and **every way of getting one wrong
is silent**:

* `_columns` drops a field the doctype has not got, so a typo is one column
  fewer and no error;
* `_view_types` drops a view whose field does not resolve, so a screen that
  meant to open as a calendar opens as a list;
* `dashboard.shape` drops a widget whose kind, aggregate or field it does not
  recognise, and a dashboard with no surviving widgets is dropped whole — so a
  screen offering one shows no such tab at all;
* `showcase.shape` drops a fact naming a field that is not there.

Every one of those produces a screen that is *thinner than intended* rather
than broken, which is the hardest kind of mistake to notice and the easiest to
make: OneMobility's Deliveries dashboard declared four widgets in a vocabulary
that does not exist and drew nothing for months, and four of RUA's screens
offered a dashboard with no widgets behind it.

The field lists come from `tests/upstream.py` — the bench where there is one,
a checked-in snapshot where there is not — so these rules hold in CI, which has
neither ERPNext nor HRMS installed.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest

import upstream

ROOT = Path(__file__).resolve().parent.parent
SPACES = ROOT / "apps/oneapp_control/oneapp_control/spaces"


def declared(path: Path):
	"""One space module, read without a bench. These are declaration files —
	`json` is the only thing any of them imports."""
	spec = importlib.util.spec_from_file_location(f"screens_{path.stem}", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


MODULES = {p.stem: declared(p) for p in sorted(SPACES.glob("*.py"))
           if p.stem != "__init__"}

# One case per screen, so a failure names the screen rather than the space.
SCREENS = [
	(name, screen)
	for name, module in MODULES.items()
	for screen in getattr(module, "SCREENS", [])
	# The escape hatch: a component screen's doctype is a hint for the rail and
	# nothing queries its fields. `resolve` returns before reading any of this.
	if not screen.get("component")
]


def ids(case):
	return f"{case[0]}/{case[1]['screen']}"


def test_the_reader_found_the_screens():
	"""A glob that matches nothing turns every rule below into a pass."""
	assert len(MODULES) >= 6, f"only read {sorted(MODULES)}"
	assert len(SCREENS) > 50, f"only parsed {len(SCREENS)} screens"


def granted(name: str) -> set[str]:
	return {row[0] for row in getattr(MODULES[name], "DOCTYPES", [])}


def custom(name: str) -> dict[str, set[str]]:
	found: dict[str, set[str]] = {}
	for field in getattr(MODULES[name], "CUSTOM_FIELDS", []):
		found.setdefault(field["dt"], set()).add(field["fieldname"])
	return found


def pool(name: str, doctype: str) -> set[str]:
	"""Every fieldname a screen over this doctype may legitimately name."""
	return set(upstream.fields(doctype) or {}) | set(upstream.STANDARD) | \
		custom(name).get(doctype, set())


def kind_of(name: str, doctype: str, fieldname: str) -> str:
	if fieldname in custom(name).get(doctype, set()):
		return next(f["fieldtype"] for f in MODULES[name].CUSTOM_FIELDS
		            if f["dt"] == doctype and f["fieldname"] == fieldname)
	return upstream.fieldtype(doctype, fieldname)


def settings(screen: dict) -> dict:
	return json.loads(screen.get("view_settings") or "{}")


def _orders(name: str, screen: dict) -> list[tuple[str, str, list]]:
	"""Every list of *values* this screen names, with the field they belong to.

	Three places name one and they are the same idea — a board's column order,
	the columns it keeps off the board, and a widget's bucket order — and all
	three are keyed by value rather than by fieldname, so none of them can be
	checked the way a fieldname is. They are checked here instead, against what
	the field can actually hold.
	"""
	view = settings(screen)
	found = []

	board = view.get("board") or {}
	field = board.get("column_field") or screen.get("status_field") or ""
	for key in ("order", "hidden"):
		values = (board.get("arrangement") or {}).get(key)
		if values and field:
			found.append((f"board.arrangement.{key}", field, values))

	for widget in (view.get("dashboard") or {}).get("widgets") or []:
		if widget.get("order") and widget.get("group_by"):
			found.append((f"widget {widget.get('label')!r} order",
			              widget["group_by"], widget["order"]))
	return found


# --------------------------------------------------------------------------- #
# A. What a space reaches
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", sorted(MODULES))
def test_every_doctype_a_space_grants_is_a_doctype(name):
	"""A grant for a name nothing has heard of writes DocPerms for a table that
	does not exist, and `sync_permissions` skips it without a word — so the
	screen over it is empty and the manifest looks right."""
	for doctype in sorted(granted(name)):
		assert upstream.fields(doctype) is not None, (
			f"{name} grants {doctype!r}, which is neither ours, on a bench, nor "
			f"in tests/fixtures/upstream_fields.json"
		)


@pytest.mark.parametrize("name", sorted(MODULES))
def test_screens_sharing_a_heading_are_declared_together(name):
	"""The rail draws a heading when the group *changes* — `lib/shell/nav.js`
	compares each screen with the one before it — which keeps the model a flat
	ordered list rather than a tree the record pane would have to understand.

	The cost of that is a rule the declaration has to keep: a group interrupted
	by a screen from another one is drawn as two headings with the same word,
	and nothing anywhere says so. OneHR has seven groups and thirty screens,
	which is exactly the size at which somebody adds a screen in the wrong
	place.
	"""
	seen, previous = set(), None
	for screen in getattr(MODULES[name], "SCREENS", []):
		group = (screen.get("screen_group") or "").strip()
		if group != previous:
			assert group not in seen, (
				f"{name}/{screen['screen']} reopens the {group!r} heading, which "
				f"the rail draws a second time under the same word"
			)
			if previous is not None:
				seen.add(previous)
			previous = group


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_a_screen_shows_a_doctype_its_space_granted(case):
	"""`resolve` throws PermissionError for a screen outside the grant, which
	is a rail entry that opens on an error page."""
	name, screen = case
	assert screen["document_type"] in granted(name), (
		f"{name}/{screen['screen']} shows {screen['document_type']} and the "
		f"space does not grant it"
	)


# --------------------------------------------------------------------------- #
# B. Every fieldname a screen names
# --------------------------------------------------------------------------- #

def fieldnames(name: str, screen: dict) -> list[tuple[str, str]]:
	"""`(where, fieldname)` for every field this screen names, anywhere.

	Everything except the showcase's related screens, which are checked against
	a *different* doctype and get their own rule below.
	"""
	found = [("fields", f.strip())
	         for f in (screen.get("fields") or "").split(",") if f.strip()]
	if screen.get("status_field"):
		found.append(("status_field", screen["status_field"]))
	for clause in (screen.get("order_by") or "").split(","):
		if clause.strip():
			found.append(("order_by", clause.strip().split(" ")[0]))
	for key in ("filters", "field_icons"):
		for fieldname in json.loads(screen.get(key) or "{}"):
			found.append((key, fieldname))

	view = settings(screen)
	showcase = view.get("showcase") or {}
	for key in ("eyebrow_field", "badge_field", "blurb_field"):
		if showcase.get(key):
			found.append((f"showcase.{key}", showcase[key]))
	for fact in showcase.get("facts") or []:
		found.append(("showcase.facts", fact["field"]))

	for key, block in view.items():
		if key == "showcase" or not isinstance(block, dict):
			continue
		for inner, value in block.items():
			if inner.endswith("_field") and isinstance(value, str) and value:
				found.append((f"{key}.{inner}", value))
			if inner.endswith("_fields") and isinstance(value, list):
				found += [(f"{key}.{inner}", one) for one in value
				          if isinstance(one, str)]
	for widget in (view.get("dashboard") or {}).get("widgets") or []:
		for inner in ("group_by", "field", "series", "x_field", "y_field"):
			if widget.get(inner):
				found.append((f"widget {widget.get('label')!r}", widget[inner]))
		for fieldname in (widget.get("filters") or {}):
			found.append((f"widget {widget.get('label')!r} filters", fieldname))
	return found


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_every_field_a_screen_names_is_a_real_field(case):
	name, screen = case
	doctype = screen["document_type"]
	known = pool(name, doctype)
	for where, fieldname in fieldnames(name, screen):
		assert fieldname in known, (
			f"{name}/{screen['screen']}: {where} names {fieldname!r}, which "
			f"{doctype} has not got — it is dropped in silence"
		)


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_a_status_field_is_a_select(case):
	"""A badge over free text is a badge with no closed set of values to
	colour, and `valueTheme` then guesses from the words."""
	name, screen = case
	field = screen.get("status_field")
	if not field:
		return
	kind = kind_of(name, screen["document_type"], field)
	assert kind == "Select", (
		f"{name}/{screen['screen']}: {field!r} is a {kind or 'missing field'}, "
		f"and a status badge wants a Select"
	)


# --------------------------------------------------------------------------- #
# C. A view type that draws nothing is a view type nobody gets
# --------------------------------------------------------------------------- #

DATEABLE = ("Date", "Datetime")
MEASURED = ("Percent", "Int", "Float")
BOARDABLE = ("Select", "Link")


def offers(screen: dict) -> list[str]:
	return [one.strip() for one in (screen.get("view_types") or "").split(",")
	        if one.strip()]


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_a_view_type_a_screen_offers_has_what_it_needs(case):
	"""`_view_types` drops a type whose field is not declared. A screen that
	offers a calendar and names no date opens on its list instead, and the
	manifest goes on claiming the calendar."""
	name, screen = case
	view = settings(screen)

	def said(key, inner):
		return ((view.get(key) or {}).get(inner) or "").strip()

	needs = {
		"board": bool((screen.get("status_field") or "").strip()
		              or said("board", "column_field")),
		"calendar": bool(said("calendar", "start_field")),
		"gantt": bool((said("gantt", "start_field") or said("calendar", "start_field"))
		              and (said("gantt", "end_field") or said("calendar", "end_field"))),
		"tree": bool(said("tree", "parent_field")),
		"dashboard": bool((view.get("dashboard") or {}).get("widgets")),
		"map": bool(said("map", "point_field")
		            or (said("map", "lat_field") and said("map", "lon_field"))),
	}
	for one in offers(screen):
		assert needs.get(one, True), (
			f"{name}/{screen['screen']} offers {one!r} and declares nothing for "
			f"it to draw, so the type is dropped and the screen opens as a list"
		)


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_the_fields_a_view_type_reads_are_the_right_kind(case):
	"""Declared is not enough: `_calendar` drops a start field that is not a
	date, `_gantt` drops a progress field that is not a number, and `_board`
	drops a column field with no closed set of values."""
	name, screen = case
	doctype = screen["document_type"]
	view = settings(screen)

	def kind(fieldname):
		return kind_of(name, doctype, fieldname)

	for key in ("calendar", "gantt"):
		block = view.get(key) or {}
		for inner in ("start_field", "end_field"):
			if block.get(inner):
				assert kind(block[inner]) in DATEABLE, (
					f"{name}/{screen['screen']}: {key}.{inner} is "
					f"{block[inner]!r}, a {kind(block[inner])}"
				)

	progress = (view.get("gantt") or {}).get("progress_field")
	if progress:
		assert kind(progress) in MEASURED, (
			f"{name}/{screen['screen']}: a Gantt's progress is a fraction, and "
			f"{progress!r} is a {kind(progress)}"
		)

	column = (view.get("board") or {}).get("column_field")
	if column:
		assert kind(column) in BOARDABLE, (
			f"{name}/{screen['screen']}: a board's columns are the values of a "
			f"Select or a Link, and {column!r} is a {kind(column)}"
		)

	if column and kind(column) == "Link":
		# A Select carries its own order — the doctype lists its options in the
		# order somebody wrote them, and a board of them comes out right for
		# free. A Link has none: its columns are whatever values are on the
		# page, in whatever order they arrived, so a pipeline board drawn from
		# one is alphabetical by accident. The order is a decision and the
		# manifest is where decisions go.
		order = ((view.get("board") or {}).get("arrangement") or {}).get("order")
		assert order, (
			f"{name}/{screen['screen']}: the board is columns of {column!r}, "
			f"which is a Link and therefore has no order of its own — declare "
			f"one in view_settings.board.arrangement.order"
		)

	# And where it names values, every one of them is a value the field can
	# hold. A typo does not fail: `_ordered` and the board's arrangement keep an
	# unknown value out of the ranking and leave the column where it was, and a
	# misspelt name in `hidden` hides nothing. Both are a screen that quietly
	# looks like it did before the declaration.
	for where, field, order in _orders(name, screen):
		if kind(field) != "Select":
			continue
		options = {one.strip() for one in
		           (upstream.options(doctype, field) or "").split("\n") if one.strip()}
		unknown = [one for one in order if one not in options]
		assert not unknown, (
			f"{name}/{screen['screen']}: {where} orders {unknown}, which "
			f"{doctype}.{field} cannot hold"
		)

	parent = (view.get("tree") or {}).get("parent_field")
	if parent:
		assert kind(parent) == "Link", (
			f"{name}/{screen['screen']}: a tree nests by a Link, and {parent!r} "
			f"is a {kind(parent)}"
		)
		assert upstream.options(doctype, parent) == doctype, (
			f"{name}/{screen['screen']}: {parent!r} links at "
			f"{upstream.options(doctype, parent)!r} rather than at {doctype} — "
			f"that is a relation, not a hierarchy"
		)


VIEW_TYPES = ("list", "board", "calendar", "dashboard", "gantt", "grid", "map",
              "report", "tree")
# The two keys in `view_settings` that are not view types, both about how a
# screen draws *one* record: `showcase` is a hero's own declaration, and
# `record` is which page draws it at all. `spaceview.SHOWCASE` and
# `recordviews.RECORD`.
SHOWCASE = "showcase"
RECORD = "record"


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_every_view_settings_key_is_a_view_type(case):
	"""`_view_settings` keeps a block only if its key is a view type, and drops
	everything else without a word.

	`cards` is the name that made this worth a rule. It is what the *resolved*
	spec calls a card-shaped view's settings — `resolved["cards"]` — so it is
	the obvious thing to write in a manifest, and three spaces did. It is not a
	view type, the block never reached the browser, and the grids went on
	drawing whichever columns the list happened to be showing.
	"""
	name, screen = case
	for key in settings(screen):
		assert key in VIEW_TYPES or key in (SHOWCASE, RECORD), (
			f"{name}/{screen['screen']}: view_settings has a {key!r} block, "
			f"which is neither a view type nor one of the two about a single "
			f"record — it is dropped on the way out and nothing says so"
		)


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_every_record_view_a_screen_names_is_one_the_engine_draws(case):
	"""`view_settings.record.as` is a name out of a closed set, and a name
	outside it falls back to the form and the tabs — silently, which is right
	for a manifest that ran ahead of a deploy and wrong for a typo that will
	never be a name. The engine cannot tell those apart; this can."""
	from oneapp.onespace import recordviews

	name, screen = case
	asked = settings(screen).get(RECORD)
	if asked is None:
		return
	assert isinstance(asked, dict), f"{name}/{screen['screen']}: `record` is not a block"
	chosen = asked.get(recordviews.AS)
	assert chosen in recordviews.BUILT_RECORD_VIEWS, (
		f"{name}/{screen['screen']}: record view {chosen!r} is not one the "
		f"engine draws — it is {sorted(recordviews.BUILT_RECORD_VIEWS)}"
	)


# --------------------------------------------------------------------------- #
# D. The dashboard's closed vocabulary
# --------------------------------------------------------------------------- #

KINDS = {
	"number": (), "bar": ("group_by",), "line": ("group_by",),
	"area": ("group_by",), "donut": ("group_by",), "funnel": ("group_by",),
	"heatmap": ("group_by", "series"), "sankey": ("group_by", "series"),
	"scatter": ("x_field", "y_field"),
}
AGGREGATES = ("count", "sum", "avg", "min", "max")
NEEDS_FIELD = ("sum", "avg", "min", "max")
WIDTHS = (3, 4, 6, 8, 12)
GRAINS = ("day", "week", "month", "year")
# `dashboard.WIDGETS`. Past this the rest are cut off without a word.
WIDGETS = 12
# What an aggregate can be taken over. A Rating is a number Frappe stores as
# one; a Date is not, and averaging a Select is not a question.
MEASURABLE = ("Currency", "Float", "Int", "Percent", "Duration", "Rating")


@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_every_widget_is_one_the_server_will_draw(case):
	"""`dashboard.shape` drops a widget rather than passing it through, so a
	kind it does not know is a chart nobody ever sees."""
	name, screen = case
	widgets = (settings(screen).get("dashboard") or {}).get("widgets") or []
	assert len(widgets) <= WIDGETS, (
		f"{name}/{screen['screen']} declares {len(widgets)} widgets; only the "
		f"first {WIDGETS} are kept"
	)

	for widget in widgets:
		said = f"{name}/{screen['screen']}: widget {widget.get('label')!r}"
		assert widget.get("kind") in KINDS, (
			f"{said} is a {widget.get('kind')!r}, which is not one of the nine "
			f"— it is dropped whole"
		)
		aggregate = widget.get("aggregate") or "count"
		assert aggregate in AGGREGATES, f"{said} aggregates by {aggregate!r}"
		if widget.get("width") is not None:
			assert widget["width"] in WIDTHS, (
				f"{said} is {widget['width']} wide, which is not one of "
				f"{WIDTHS} — it falls back to six and the row stops adding up"
			)
		if widget.get("grain"):
			assert widget["grain"] in GRAINS, f"{said} is grained by {widget['grain']!r}"
		for needed in KINDS[widget["kind"]]:
			assert widget.get(needed), (
				f"{said} is a {widget['kind']} and names no {needed}"
			)
		if aggregate in NEEDS_FIELD:
			assert widget.get("field"), (
				f"{said} takes the {aggregate} of nothing"
			)
			kind = kind_of(name, screen["document_type"], widget["field"])
			assert kind in MEASURABLE, (
				f"{said} takes the {aggregate} of {widget['field']!r}, which is "
				f"a {kind}"
			)
		else:
			assert not widget.get("field"), (
				f"{said} counts rows and names a field; `_shaped` throws it "
				f"away, which means somebody wanted a count of distinct values "
				f"and this is not that"
			)


# --------------------------------------------------------------------------- #
# E. The showcase reaches other screens
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("case", SCREENS, ids=ids)
def test_a_showcase_tab_names_a_screen_and_a_field_on_it(case):
	"""A tab is another screen in the same space and the field on *that*
	screen's doctype pointing back here. `showcase.shape` keeps it whether or
	not either exists, deliberately — the checks happen when `rows` is asked —
	so a typo is a tab that opens on nothing."""
	name, screen = case
	showcase = settings(screen).get("showcase") or {}
	related = list(showcase.get("tabs") or [])
	if showcase.get("children"):
		related.append(showcase["children"])
	if not related:
		return

	by_screen = {one["screen"]: one for one in getattr(MODULES[name], "SCREENS", [])}
	for one in related:
		other = by_screen.get(one["screen"])
		assert other, (
			f"{name}/{screen['screen']}: a showcase tab names screen "
			f"{one['screen']!r}, which this space has not got"
		)
		theirs = other["document_type"]
		assert one["field"] in pool(name, theirs), (
			f"{name}/{screen['screen']}: the {one['screen']!r} tab filters "
			f"{theirs} by {one['field']!r}, which it has not got"
		)
		assert kind_of(name, theirs, one["field"]) in ("Link", "Dynamic Link"), (
			f"{name}/{screen['screen']}: the {one['screen']!r} tab filters "
			f"{theirs} by {one['field']!r}, which does not point at anything"
		)


# --------------------------------------------------------------------------- #
# F. The fields a space adds to somebody else's doctype
# --------------------------------------------------------------------------- #

FIELDS = [(name, field) for name, module in MODULES.items()
          for field in getattr(module, "CUSTOM_FIELDS", [])]


@pytest.mark.parametrize(
	"case", FIELDS, ids=lambda c: f"{c[0]}/{c[1]['dt']}.{c[1]['fieldname']}"
)
def test_a_custom_field_is_one_that_can_be_made(case):
	name, field = case
	assert field["fieldname"].startswith("custom_"), (
		f"{field['fieldname']} is not namespaced, so an app adding a field of "
		f"that name in its next release collides with it"
	)
	assert upstream.fields(field["dt"]) is not None, (
		f"{name} adds a field to {field['dt']!r}, which is not a doctype"
	)
	assert not upstream.has(field["dt"], field["fieldname"]), (
		f"{field['dt']}.{field['fieldname']} already exists upstream — the "
		f"sync skips a Custom Field whose name is taken, and the screen then "
		f"reads a field somebody else owns"
	)
	after = field.get("insert_after")
	if after:
		mine = {f["fieldname"] for f in MODULES[name].CUSTOM_FIELDS
		        if f["dt"] == field["dt"]}
		assert upstream.has(field["dt"], after) or after in mine, (
			f"{field['dt']}.{field['fieldname']} is inserted after {after!r}, "
			f"which is not a field of it — Frappe appends it to the end"
		)


# --------------------------------------------------------------------------- #
# G. The document that describes all this
#
# `docs/ARCHITECTURE.md`: "a fact that must not drift is read back by a test".
# `docs/ERP-SPACES.md` lists OneHR's seven headings and what is under each, and
# that list is the one thing in it somebody changes by accident — adding a
# screen to a group is one line in a manifest and nobody re-reads the prose.
# --------------------------------------------------------------------------- #

DOC = ROOT / "docs/ERP-SPACES.md"


def documented_groups() -> dict[str, list[str]]:
	"""OneHR's headings and their screens, as the document states them.

	Read out of the one shape the document writes them in — `**Heading** —
	Label, Label, Label` — so a line reformatted into a table fails the reader
	below rather than silently matching nothing.
	"""
	found = {}
	for line in DOC.read_text().splitlines():
		match = re.match(r"^\*\*([A-Za-z]+)\*\* — (.+)$", line.strip())
		if match:
			found[match.group(1)] = [one.strip() for one in match.group(2).split(",")]
	return found


def test_the_reader_found_the_headings():
	assert len(documented_groups()) == 7, (
		"docs/ERP-SPACES.md §5 no longer lists seven headings in the shape this "
		"reads, so the rule below is checking nothing"
	)


def test_the_document_lists_the_tables_configuration_actually_holds():
	"""The seventh heading became a screen, so it is read back differently.

	Setup was a `screen_group` and is now one Configuration screen with the
	tables as tabs, which is the same fact in a different shape — and the same
	thing somebody changes by accident, because adding a tab is one string in a
	list and nobody re-reads the prose.
	"""
	import json as _json

	screen = next(
		one for one in MODULES["onehr"].SCREENS
		if one["screen"] == "configuration"
	)
	settings = _json.loads(screen["view_settings"])
	labels = {one["screen"]: one["label"] for one in MODULES["onehr"].SCREENS}
	real = [labels[name] for name in settings["configuration"]["screens"]]

	said = DOC.read_text()
	for label in real:
		assert label in said, (
			f"docs/ERP-SPACES.md §5 does not mention {label!r}, which is a tab "
			f"on OneHR's Configuration"
		)
	# The count in words, because that is how the sentence reads. Spelt out
	# here rather than matched loosely: "thirteen tabs" going stale while
	# thirteen tables are declared is exactly the drift this file exists for.
	words = {12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
	         16: "sixteen"}
	assert f"whose {words.get(len(real), len(real))} tabs" in said, (
		f"docs/ERP-SPACES.md §5 should say Configuration holds "
		f"{words.get(len(real), len(real))} tables"
	)


def test_the_document_lists_the_screens_onehr_actually_has():
	real = {}
	for screen in MODULES["onehr"].SCREENS:
		real.setdefault(screen.get("screen_group") or "", []).append(screen["label"])

	for heading, labels in documented_groups().items():
		assert heading in real, (
			f"docs/ERP-SPACES.md names a {heading!r} heading OneHR has not got"
		)
		assert labels == real[heading], (
			f"docs/ERP-SPACES.md says {heading} is {labels} and OneHR says "
			f"{real[heading]}"
		)


# --------------------------------------------------------------------------- #
# H. And the snapshot itself
# --------------------------------------------------------------------------- #

def test_the_snapshot_is_still_what_the_bench_says():
	"""The one rule that keeps the fixture from becoming fiction.

	Skips where there is no bench, which is CI — there the snapshot is all
	there is and every rule above is reading it. On a machine with ERPNext and
	HRMS installed this is what notices a renamed field.
	"""
	apps = upstream.bench()
	if not apps:
		pytest.skip("no bench with doctype JSON; the snapshot is the only source")

	drifted = []
	for doctype, fields in sorted(upstream.snapshot().items()):
		real = upstream._off_bench(apps, doctype)
		if real is None:
			drifted.append(f"{doctype} is in the snapshot and not on the bench")
			continue
		gone = sorted(set(fields) - set(real))
		if gone:
			drifted.append(f"{doctype} no longer has {', '.join(gone[:6])}")

	assert not drifted, (
		"tests/fixtures/upstream_fields.json has drifted from the bench:\n  "
		+ "\n  ".join(drifted)
		+ "\nRun `python scripts/upstream_fields.py` and read the diff — a "
		"field that has gone is a manifest that now names nothing."
	)


# --------------------------------------------------------------------------- #
# Screens narrowed to their reader
#
# `onespace/mine.py` resolves the `@me` in a screen's filters. What it cannot
# check is whether the *declaration* makes sense, and there are two ways for one
# not to that are silent in the browser: a twin whose heading differs from its
# parent's opens that heading twice, and a twin declared anywhere but next to
# its parent is a "My leave" a reader will not find near Leave.
# --------------------------------------------------------------------------- #

def _narrowed(module) -> list[tuple[int, dict]]:
	"""Every screen of one space narrowed to whoever is reading it."""
	found = []
	for at, screen in enumerate(getattr(module, "SCREENS", [])):
		filters = json.loads(screen.get("filters") or "{}")
		for value in filters.values():
			text = value[1] if isinstance(value, list) else value
			if isinstance(text, str) and text.startswith("@me"):
				found.append((at, screen))
				break
	return found


def test_the_reader_found_the_twins():
	"""A reader that matches nothing turns the two rules below into passes."""
	total = sum(len(_narrowed(module)) for module in MODULES.values())
	assert total >= 4, f"only found {total} screens narrowed to their reader"


@pytest.mark.parametrize("name", sorted(MODULES))
def test_a_twin_is_declared_above_the_screen_it_narrows(name):
	"""`My leave` sits immediately above `Leave`, in Leave's own heading.

	Both halves matter and each fails quietly on its own. A different heading
	makes the rail draw that word twice with one entry between them — the rail
	draws a heading when the group *changes*. And a twin declared three screens
	away is a self-service view a reader will not find beside the thing it is
	about, which is the whole reason `docs/HORILLA.md` §3.1 is a finding rather
	than a preference.

	The parent is found by shape rather than by a declared link: a twin is
	`{**parent, …}`, so it is the next screen over the same doctype with the
	same heading and no `@me` of its own.
	"""
	module = MODULES[name]
	screens = module.SCREENS
	for at, twin in _narrowed(module):
		assert at + 1 < len(screens), (
			f"{name}/{twin['screen']} is narrowed to its reader and is the last "
			f"screen in the space, so it is above nothing"
		)
		parent = screens[at + 1]
		assert parent.get("document_type") == twin.get("document_type"), (
			f"{name}/{twin['screen']} is narrowed to its reader but the screen "
			f"below it is {parent['screen']!r}, over a different doctype"
		)
		assert (parent.get("screen_group") or "") == (twin.get("screen_group") or ""), (
			f"{name}/{twin['screen']} opens a heading its parent "
			f"{parent['screen']!r} is not in, so the rail draws one twice"
		)


@pytest.mark.parametrize("name", sorted(MODULES))
def test_a_twin_narrows_on_a_field_its_doctype_has(name):
	"""A filter naming a field the doctype has not got is one the query drops,
	and the screen then shows everybody's rows under a label saying it is
	yours."""
	module = MODULES[name]
	for _at, twin in _narrowed(module):
		fields = upstream.fields(twin["document_type"])
		for field in json.loads(twin.get("filters") or "{}"):
			assert field in fields, (
				f"{name}/{twin['screen']} narrows on {field!r}, which "
				f"{twin['document_type']} has not got"
			)
