"""The eight bespoke record views, and the two things they must not redo.

`docs/CLEANUP.md` §3.2: `components/screen/records/` had eight pages that each
opened with the same `<section>` and the same header band — the same eleven
utilities, the same `flex min-w-0 flex-1` column, the same eyebrow and title
row. Seven of the eight were OnePeople's, written one after another, each from
the one before.

Nothing was wrong with any of them. What was wrong is that the ninth space
would have written a ninth copy, and the day the tab strip moves is the day
somebody edits eight files and misses one.

So the band is `RecordHead.vue`, the shell is `RecordPage.vue`, and the big
number at the trailing end is `RecordTally.vue`. This holds the views to them,
and holds the extraction to the thing it must not have broken.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WHERE = ROOT / "apps/oneapp/frontend/src/modules/onespace/components/screen/records"
E2E = ROOT / "apps/oneapp/frontend/e2e"
SRC = ROOT / "apps/oneapp/frontend/src"

#: The three that are the kit rather than a view.
KIT = {"RecordPage.vue", "RecordHead.vue", "RecordTally.vue"}


def views() -> list[pathlib.Path]:
	return sorted(one for one in WHERE.glob("*.vue") if one.name not in KIT)


VIEWS = views()


def template(path: pathlib.Path) -> str:
	"""Everything above `<script setup>`.

	Not `src[index("<template>"):index("</template>")]`, which is what this
	was and which stopped working the moment a view used a named slot: the
	first `</template>` is now the close of `<template #aside>`, a hundred
	lines short of the end. The guard went on passing and read a third of each
	file.
	"""
	src = path.read_text(encoding="utf-8")
	return src[:src.index("<script setup>")]


@pytest.mark.parametrize("path", VIEWS, ids=lambda p: p.stem)
def test_a_record_view_does_not_build_its_own_shell(path):
	"""`-mx-4 -mt-4` is the bleed that puts a record view above the tab strip,
	and it belongs to `RecordPage` — which is also where it can be changed
	once."""
	assert "-mx-4 -mt-4" not in template(path), (
		f"{path.name} builds its own shell; use <RecordPage name=\"…\">"
	)
	assert "<RecordPage" in template(path), f"{path.name} is not in a RecordPage"


@pytest.mark.parametrize("path", VIEWS, ids=lambda p: p.stem)
def test_a_record_view_does_not_build_its_own_band(path):
	"""The eleven-utility band. `PlaceRecord` is the one that legitimately has
	no band — no eyebrow, no badge, no trailing number — and it is a rule and
	two settings rather than a record about somebody.

	Checked by the two utilities that only ever appear together on that
	element, rather than by the whole string: a class list is order-dependent
	in the source and not in the browser, and a guard that fails on a reorder
	is a guard people delete."""
	body = template(path)
	if "<RecordHead" in body:
		assert "bg-surface-gray-1 px-4 py-5" not in body, (
			f"{path.name} uses RecordHead and still hand-rolls a band"
		)
		return

	assert path.name == "PlaceRecord.vue", (
		f"{path.name} draws a record without RecordHead. If its band really is "
		f"different, say so here; if it is the same band, use the component."
	)


@pytest.mark.parametrize("path", VIEWS, ids=lambda p: p.stem)
def test_a_record_view_does_not_redraw_the_tally(path):
	"""`text-2xl-semibold tabular-nums` over a caption: four views drew it
	identically. The digits are the reason it is one component — proportional
	figures make a column ripple, and this is the number a page is a judgement
	about."""
	body = template(path)
	assert "text-2xl-semibold tabular-nums" not in body, (
		f"{path.name} draws its own tally; use <RecordTally>"
	)


# --------------------------------------------------------------------------- #
# The contract the extraction could have broken
#
# `data-slot` is how a browser spec finds anything on these pages, so the slot
# names are an interface and not an implementation detail. Pulling a band into
# a component is exactly the kind of change that tidies `absence-kind`,
# `payslip-period` and `boarding-eyebrow` into one word — and the suite that
# would have caught it takes fifty minutes to run.
#
# So the names are listed. A view that gains one adds it here; a view that
# renames one has to notice it is renaming an interface.
# --------------------------------------------------------------------------- #

SLOT = re.compile(r'data-slot="([a-z][a-z0-9-]*)"')

#: Slots a static scan cannot see, because the view composes the name at run
#: time: `:data-slot="`payslip-${side.key}`"`, over a computed list of two.
#:
#: Listed rather than matched by a looser pattern. A regex permissive enough to
#: find these would be permissive enough to find anything, and the whole value
#: of the check below is that it is exact — so the honest thing is to name the
#: exception and keep the rest tight.
COMPOSED = {"payslip-earnings", "payslip-deductions"}

#: Every slot the eight views name, by view.
SLOTS = {
	"AbsenceRecord": {
		"absence-balance", "absence-because", "absence-days", "absence-kind",
		"absence-left", "absence-record", "absence-short", "absence-when",
		"absence-who",
	},
	"BoardingRecord": {
		"boarding-eyebrow", "boarding-no-steps", "boarding-record",
		"boarding-span", "boarding-step", "boarding-steps", "boarding-when",
		"boarding-who",
	},
	"CandidateRecord": {
		"candidate-eyebrow", "candidate-interviews", "candidate-name",
		"candidate-opening", "candidate-rating", "candidate-record",
		"candidate-stages",
	},
	"DayRecord": {
		"day-application", "day-checkins", "day-eyebrow", "day-flags",
		"day-leave", "day-no-checkins", "day-record", "day-when", "day-who",
		"day-worked",
	},
	"OpeningRecord": {
		"opening-applicants", "opening-eyebrow", "opening-funnel",
		"opening-overdue", "opening-pay", "opening-record", "opening-title",
		"opening-vacancies", "opening-when",
	},
	"PayslipRecord": {
		"payslip-days", "payslip-line", "payslip-net", "payslip-period",
		"payslip-record", "payslip-who",
	},
	"PersonRecord": {
		"person-eyebrow", "person-manager", "person-name", "person-portrait",
		"person-portrait-edit", "person-presence", "person-record",
		"person-reports", "person-year",
	},
	"PlaceRecord": {
		"place-here", "place-name", "place-network", "place-networks",
		"place-position", "place-record", "place-rule",
	},
}


@pytest.mark.parametrize("path", VIEWS, ids=lambda p: p.stem)
def test_a_view_names_the_slots_it_is_recorded_as_naming(path):
	"""Both directions. A slot that appears and is not listed is one nobody
	decided was an interface; a slot that is listed and has gone is a spec that
	will fail in fifty minutes' time."""
	body = template(path)
	found = set(SLOT.findall(body))

	# `RecordPage`, `RecordHead` and `RecordTally` write four of them from
	# props rather than from a `data-slot` in the view, so those are read off
	# the attributes — scoped to those three tags, because `name=` is also how
	# every `<Icon>` in the file names a glyph.
	found |= {f"{one}-record" for one in
	          re.findall(r'<RecordPage\s+name="([a-z][a-z0-9-]*)"', body)}
	found |= set(re.findall(r'<RecordTally[^>]*?\bname="([a-z][a-z0-9-]*)"',
	                        body, re.S))
	for prop in ("eyebrow-slot", "title-slot"):
		found |= set(re.findall(rf'{prop}="([a-z][a-z0-9-]*)"', body))

	said = SLOTS[path.stem]
	assert found == said, (
		f"{path.stem}: appears and unlisted {sorted(found - said)}; "
		f"listed and gone {sorted(said - found)}"
	)


def test_the_specs_only_select_slots_that_exist():
	"""The reading that makes the list worth keeping: a browser spec naming a
	slot nothing writes is a spec that fails on a page that is fine, fifty
	minutes after somebody pushed.

	Read across the **whole** SPA rather than across the eight views, because a
	view does not write all of its own slots. `FactRow` takes `slot-name` as a
	prop, so `candidate-facts` is a string in `CandidateRecord` and an
	attribute in `FactRow`; `person-balance` belongs to `LeaveBalance`
	entirely. The question this asks is "does anything write this", and the
	honest place to ask it is everywhere.
	"""
	written = set(COMPOSED)
	for one in sorted(SRC.rglob("*.vue")):
		text = one.read_text(encoding="utf-8")
		written |= set(SLOT.findall(text))
		written |= set(re.findall(r'slot-name="([a-z][a-z0-9-]*)"', text))
		written |= {f"{name}-record" for name in
		            re.findall(r'<RecordPage\s+name="([a-z][a-z0-9-]*)"', text)}
		written |= set(re.findall(r'<RecordTally[^>]*?\bname="([a-z][a-z0-9-]*)"',
		                          text, re.S))
		for prop in ("eyebrow-slot", "title-slot"):
			written |= set(re.findall(rf'{prop}="([a-z][a-z0-9-]*)"', text))

	prefixes = tuple(sorted({one.split("-")[0] for names in SLOTS.values()
	                         for one in names}))
	asked = set()
	for spec in sorted(E2E.glob("*.spec.js")):
		for name in re.findall(r'data-slot="?=?([a-z][a-z0-9-]*)', spec.read_text()):
			if name.startswith(prefixes) and name.count("-"):
				asked.add(name)

	assert asked, "no spec selected a record-view slot; this read nothing"
	assert asked <= written, (
		f"specs select slots nothing writes: {sorted(asked - written)}"
	)


def test_the_scan_found_the_views():
	assert len(VIEWS) == 8, [one.name for one in VIEWS]
	assert {one.stem for one in VIEWS} == set(SLOTS)
