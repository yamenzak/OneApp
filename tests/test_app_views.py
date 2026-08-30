"""An app's screens, declared rather than written.

A view is little more than a doctype and some fieldnames; what each field is
called, what a Select offers, and whether this user may write it all come from
the tenant site, because that is where the doctype and the permissions live.

What these pin is the part that is not cosmetic: a screen is an allowlist twice
over. It can only be reached through an app the workspace is entitled to, and it
can only read a doctype that app's manifest granted or write a field it shows.
Those hold on a real site — `tests/` cannot reach one, so what is checked here is
the logic that decides them.
"""

import types

import pytest


@pytest.fixture
def appview(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import appview as module

	return module


def field(fieldname, fieldtype="Data", label=None, **kw):
	return types.SimpleNamespace(
		fieldname=fieldname, fieldtype=fieldtype, label=label or fieldname.title(),
		options=kw.get("options"), reqd=kw.get("reqd", 0),
		read_only=kw.get("read_only", 0), in_list_view=kw.get("in_list_view", 0),
	)


def meta(fields, title_field=None):
	return types.SimpleNamespace(fields=fields, title_field=title_field)


TODO = meta(
	[
		field("description", "Small Text", "Description", in_list_view=1),
		field("status", "Select", "Status", options="Open\nClosed"),
		field("priority", "Select", "Priority", options="High\nMedium\nLow"),
		field("date", "Date", "Due Date"),
		field("modified", "Datetime", "Last Modified", read_only=1),
	],
	title_field="description",
)


# --------------------------------------------------------------------------- #
# Columns come from the site, not from the manifest
# --------------------------------------------------------------------------- #

def test_a_column_takes_its_label_and_type_from_the_doctype(appview):
	"""The manifest names fieldnames. Everything a screen renders comes from the
	site, so a relabelled field is relabelled everywhere without a sync."""
	columns = appview._columns(TODO, ["description", "status"])

	assert [c["fieldname"] for c in columns] == ["description", "status"]
	assert columns[1]["label"] == "Status"
	assert columns[1]["options"] == "Open\nClosed"


def test_a_field_this_site_does_not_have_is_skipped(appview):
	"""One manifest serves sites on different versions, so a field that is not
	here is an absence rather than an error."""
	columns = appview._columns(TODO, ["description", "invented_last_week"])
	assert [c["fieldname"] for c in columns] == ["description"]


def test_a_read_only_field_is_shown_but_not_offered(appview):
	"""Better a record with a read-only field on it than a control that writes
	something the doctype will refuse."""
	modified = appview._columns(TODO, ["modified"])[0]
	assert modified["editable"] is False


def test_a_screen_that_names_no_columns_still_gets_a_list(appview):
	assert appview._default_fields(TODO) == ["description"]


def test_a_doctype_with_no_list_fields_falls_back_to_its_title(appview):
	plain = meta([field("subject"), field("owner"), field("body", "Text")],
	             title_field="subject")
	assert appview._default_fields(plain)[0] == "subject"


def test_frappes_bookkeeping_is_never_a_default_column(appview):
	"""`owner`, `docstatus` and friends are Frappe's, and a customer reading them
	is always an accident."""
	plain = meta([field("owner"), field("subject")])
	assert "owner" not in appview._default_fields(plain)


# --------------------------------------------------------------------------- #
# The allowlist
# --------------------------------------------------------------------------- #

def test_a_write_is_bounded_by_what_the_screen_shows(appview):
	"""Verified against a real site too: writing `reference_type` through a
	screen that shows four other fields leaves it untouched."""
	resolved = {"columns": appview._columns(TODO, ["description", "status", "modified"])}
	assert appview._writable(resolved) == {"description", "status"}


def test_a_screen_with_nothing_editable_writes_nothing(appview):
	resolved = {"columns": appview._columns(TODO, ["modified"])}
	assert appview._writable(resolved) == set()


def test_a_filter_that_is_not_an_object_is_dropped(appview):
	"""A filter arrives as free text an operator typed. Anything but an object
	is ignored rather than passed to the query layer."""
	assert appview._json('{"status": "Open"}') == {"status": "Open"}
	assert appview._json("[1, 2, 3]") == {}
	assert appview._json("not json at all") == {}
	assert appview._json(None) == {}
