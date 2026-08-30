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
	"""A DocField, with every attribute the resolver reads.

	Every one of them, deliberately: a fake that is missing an attribute the
	real thing has does not fail where the code is wrong, it fails where the
	fake is thin — and the two read identically in a traceback.
	"""
	return types.SimpleNamespace(
		fieldname=fieldname, fieldtype=fieldtype, label=label or fieldname.title(),
		options=kw.get("options"), reqd=kw.get("reqd", 0),
		read_only=kw.get("read_only", 0), in_list_view=kw.get("in_list_view", 0),
		description=kw.get("description"), placeholder=kw.get("placeholder"),
		precision=kw.get("precision"), non_negative=kw.get("non_negative", 0),
		default=kw.get("default"), link_filters=kw.get("link_filters"),
	)


def meta(fields, title_field=None, **kw):
	return types.SimpleNamespace(
		fields=fields, title_field=title_field,
		image_field=kw.get("image_field"),
		sort_field=kw.get("sort_field", "modified"),
		sort_order=kw.get("sort_order", "DESC"),
		states=kw.get("states", []),
		is_submittable=kw.get("is_submittable", 0),
		track_changes=kw.get("track_changes", 0),
		track_seen=0, max_attachments=0, autoname=kw.get("autoname", ""),
	)


TODO = meta(
	[
		field("description", "Small Text", "Description", in_list_view=1),
		field("status", "Select", "Status", options="Open\nClosed"),
		field("priority", "Select", "Priority", options="High\nMedium\nLow"),
		field("date", "Date", "Due Date"),
		field("modified", "Datetime", "Last Modified", read_only=1),
		field("reference_name", "Data", "Reference", read_only=1),
		field("colour", "Color", "Colour"),
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
	reference = appview._columns(TODO, ["reference_name"])[0]
	assert reference["editable"] is False


def test_a_fieldtype_with_no_counterpart_is_shown_but_not_offered(appview):
	"""Colour, signature, geolocation. frappe-ui has no component for them, and
	a text box that writes a hex string into a Signature field is worse than a
	value someone can read."""
	colour = appview._columns(TODO, ["colour"])[0]
	assert colour["editable"] is False
	assert colour["cell"] == "color"


def test_frappes_own_bookkeeping_is_never_a_column(appview):
	"""`modified`, `owner`, `docstatus`. A manifest naming one is a mistake, and
	a customer reading it is always an accident."""
	assert appview._columns(TODO, ["modified", "owner", "docstatus"]) == []


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
	resolved = {"columns": appview._columns(
		TODO, ["description", "status", "reference_name", "colour"])}
	assert appview._writable(resolved) == {"description", "status"}


def test_a_screen_with_nothing_editable_writes_nothing(appview):
	resolved = {"columns": appview._columns(TODO, ["reference_name"])}
	assert appview._writable(resolved) == set()


def test_a_filter_that_is_not_an_object_is_dropped(appview):
	"""A filter arrives as free text an operator typed. Anything but an object
	is ignored rather than passed to the query layer."""
	assert appview._json('{"status": "Open"}') == {"status": "Open"}
	assert appview._json("[1, 2, 3]") == {}
	assert appview._json("not json at all") == {}
	assert appview._json(None) == {}


# --------------------------------------------------------------------------- #
# A saved or pending view narrows a screen; it never widens one
#
# Filters, sort and columns are chosen in a browser, which means they are a
# string someone sent. Verified against a real site as well — a saved filter of
# `status: Closed` on a screen filtered to `status: Open` returns the same rows
# as before — but the merge rules themselves are pinned here.
# --------------------------------------------------------------------------- #

def resolved_todo(appview, fields=("description", "status", "priority", "date")):
	columns = appview._columns(TODO, list(fields))
	return {
		"doctype": "ToDo",
		"columns": list(columns),
		"all_columns": list(columns),
		"fields": [c["fieldname"] for c in columns] + ["name"],
		"filters": {"status": "Open"},
		"order_by": "modified desc",
	}


def test_a_pending_filter_cannot_loosen_the_screens_own(appview):
	out = appview._apply_overrides(resolved_todo(appview), {"filters": {"status": "Closed"}})
	assert out["filters"]["status"] == "Open"


def test_a_pending_filter_on_another_field_is_kept(appview):
	out = appview._apply_overrides(resolved_todo(appview), {"filters": {"priority": "High"}})
	assert out["filters"] == {"status": "Open", "priority": "High"}


def test_a_free_text_filter_becomes_a_contains_match(appview):
	"""A value from a browser is never passed through as an operator: `["=",
	"x"]` arriving in a filter would be a query someone else wrote."""
	out = appview._apply_overrides(resolved_todo(appview), {"filters": {"description": "van"}})
	assert out["filters"]["description"] == ["like", "%van%"]


def test_a_pending_filter_on_a_field_the_screen_hides_is_dropped(appview):
	"""It would only narrow the list — and that is the point: someone watching
	which rows come back can read a field they were never shown, one guess at a
	time."""
	out = appview._apply_overrides(resolved_todo(appview), {"filters": {"owner": "someone@x"}})
	assert "owner" not in out["filters"]


def test_a_filter_value_may_never_carry_its_own_operator(appview):
	"""Frappe's filter syntax lets a value be `["in", […]]` or `["descendants
	of", …]`. Passing one through hands the query layer a question the screen
	never granted."""
	for hostile in (["in", ["Open", "Closed"]], ["like", "%"], {"x": 1}, ("=", "Open")):
		out = appview._apply_overrides(resolved_todo(appview),
		                               {"filters": {"priority": hostile}})
		assert "priority" not in out["filters"], hostile


def test_a_saved_filter_is_stored_as_what_was_asked_not_as_a_query(appview):
	"""So a text filter can be read back into the box someone typed it into —
	`["like", "%van%"]` in a text box is not what they wrote."""
	offered = {c["fieldname"]: c for c in appview._columns(
		TODO, ["description", "status"])}
	asked = appview._asked_filters(offered, {"description": "van", "status": "Open"})
	assert asked == {"description": "van", "status": "Open"}

	query = appview._as_query_filters(offered, asked)
	assert query == {"description": ["like", "%van%"], "status": "Open"}


def test_pending_columns_intersect_with_what_the_screen_offers(appview):
	out = appview._apply_overrides(
		resolved_todo(appview), {"columns": ["description", "owner", "_liked_by"]})
	assert [c["fieldname"] for c in out["columns"]] == ["description"]


def test_pending_columns_that_name_nothing_real_leave_the_screen_alone(appview):
	before = resolved_todo(appview)
	out = appview._apply_overrides(dict(before), {"columns": ["owner"]})
	assert [c["fieldname"] for c in out["columns"]] == [c["fieldname"] for c in before["columns"]]


def test_order_by_is_rebuilt_from_parts(appview):
	"""It reaches the query layer, so it is never the string that arrived."""
	base = resolved_todo(appview)
	assert appview._safe_order(base, "date asc") == "date asc"
	# A field the screen does not show, a direction we do not know, and SQL.
	for hostile in ("owner asc", "date sideways", "(select 1) desc -- ",
	                "date asc, (select 1)", "", None):
		assert appview._safe_order(base, hostile) == "modified desc"
