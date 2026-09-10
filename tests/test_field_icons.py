"""One glyph per field, wherever that field is drawn.

The mark in front of a field's label is answered in one place —
`onespace/field_icons.py` — so the record, the list header, the column
picker, a child table's grid and the rail a document picks its tokens from
cannot disagree. Three claims are worth pinning.

**The fieldtype is the default.** A Date is a calendar and a Currency is a
wallet, and nobody has to say so.

**A manifest may overrule it, and the override is keyed by doctype.** A
screen declares it because that is where manifests are written and checked,
but an icon chosen for Project's status is Project's status everywhere —
including surfaces with no screen behind them, which is the whole reason
this is not a property the resolver passes down.

**A name outside the closed set is ignored.** Tailwind emits CSS only for
the lucide names it saw in a source file, so one that exists only in a
manifest would draw an empty box; falling back to the fieldtype's own is the
quiet, correct answer, and `tests/test_manifests.py` makes it loud for a
manifest we ship.
"""

import importlib
import sys

import pytest


@pytest.fixture
def icons(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp."):
			del sys.modules[name]
	mod = importlib.import_module("oneapp.onespace.field_icons")
	mod.forget()
	return mod


def declare(icons, monkeypatch, screens):
	"""Stand in for what the control plane synced onto this site."""
	sync = importlib.import_module("oneapp.onespace.sync")
	monkeypatch.setattr(sync, "state", lambda: {"spaces": [{"screens": screens}]})
	icons.forget()


def test_the_fieldtype_answers_when_nothing_says_otherwise(icons):
	assert icons.icon_for("Currency") == "lucide-wallet"
	assert icons.icon_for("Date", "Project", "expected_end_date") == "lucide-calendar"


def test_an_unknown_fieldtype_still_answers(icons):
	# A fieldtype Frappe added and we have not placed. A question mark is a
	# better answer than a blank, and better than raising on a page load.
	assert icons.icon_for("Warp Field") == "lucide-circle-help"


def test_a_screen_may_overrule_the_type(icons, monkeypatch):
	declare(icons, monkeypatch, [{
		"document_type": "Project",
		"field_icons": '{"status": "lucide-activity"}',
	}])
	assert icons.icon_for("Select", "Project", "status") == "lucide-activity"
	# And only that field, on only that doctype.
	assert icons.icon_for("Select", "Project", "priority") == "lucide-list"
	assert icons.icon_for("Select", "ToDo", "status") == "lucide-list"


def test_the_override_reaches_a_surface_with_no_screen(icons, monkeypatch):
	"""Keyed by doctype, which is the point: the rail a document picks its
	tokens from has no screen behind it and must still agree."""
	declare(icons, monkeypatch, [{
		"document_type": "Project", "field_icons": {"status": "lucide-activity"},
	}])
	assert icons.declared() == {"Project.status": "lucide-activity"}


def test_a_name_outside_the_closed_set_is_ignored(icons, monkeypatch):
	declare(icons, monkeypatch, [{
		"document_type": "Project",
		"field_icons": '{"status": "lucide-not-a-real-icon"}',
	}])
	assert icons.icon_for("Select", "Project", "status") == "lucide-list"


def test_a_broken_declaration_is_nothing_rather_than_an_error(icons, monkeypatch):
	declare(icons, monkeypatch, [{"document_type": "Project", "field_icons": "{oops"}])
	assert icons.declared() == {}


def test_a_screen_with_no_doctype_contributes_nothing(icons, monkeypatch):
	# A component screen: the doctype field is empty and the manifest is the
	# app's own business from there.
	declare(icons, monkeypatch, [{"field_icons": '{"status": "lucide-activity"}'}])
	assert icons.declared() == {}
