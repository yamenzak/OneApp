"""An app's screens, declared rather than written.

A screen is little more than a doctype and some fieldnames; what each field is
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
def spaceview(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import spaceview as module

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
		in_standard_filter=kw.get("in_standard_filter", 0),
		permlevel=kw.get("permlevel", 0),
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
		# Which permlevels this user may read. Frappe's own answer; a field
		# above them is a field this screen must not offer.
		get_permlevel_access=lambda *a, **k: kw.get("permlevels", [0]),
	)


TODO = meta(
	[
		field("description", "Small Text", "Description", in_list_view=1),
		field("status", "Select", "Status", options="Open\nClosed", in_standard_filter=1),
		field("priority", "Select", "Priority", options="High\nMedium\nLow",
		      in_standard_filter=1),
		field("date", "Date", "Due Date"),
		field("modified", "Datetime", "Last Modified", read_only=1),
		field("reference_name", "Data", "Reference", read_only=1),
		field("colour", "Color", "Colour"),
		field("sec_more", "Section Break", "More"),
		field("items", "Table", "Items", options="ToDo Item"),
		field("cost", "Currency", "Cost", permlevel=1),
	],
	title_field="description",
)


# --------------------------------------------------------------------------- #
# Columns come from the site, not from the manifest
# --------------------------------------------------------------------------- #

def test_a_column_takes_its_label_and_type_from_the_doctype(spaceview):
	"""The manifest names fieldnames. Everything a screen renders comes from the
	site, so a relabelled field is relabelled everywhere without a sync."""
	columns = spaceview._columns(TODO, ["description", "status"])

	assert [c["fieldname"] for c in columns] == ["description", "status"]
	assert columns[1]["label"] == "Status"
	assert columns[1]["options"] == "Open\nClosed"


def test_a_field_this_site_does_not_have_is_skipped(spaceview):
	"""One manifest serves sites on different versions, so a field that is not
	here is an absence rather than an error."""
	columns = spaceview._columns(TODO, ["description", "invented_last_week"])
	assert [c["fieldname"] for c in columns] == ["description"]


def test_a_read_only_field_is_shown_but_not_offered(spaceview):
	"""Better a record with a read-only field on it than a control that writes
	something the doctype will refuse."""
	reference = spaceview._columns(TODO, ["reference_name"])[0]
	assert reference["editable"] is False


def test_a_fieldtype_with_no_counterpart_is_shown_but_not_offered(spaceview):
	"""Colour, signature, geolocation. frappe-ui has no component for them, and
	a text box that writes a hex string into a Signature field is worse than a
	value someone can read."""
	colour = spaceview._columns(TODO, ["colour"])[0]
	assert colour["editable"] is False
	assert colour["cell"] == "color"


def test_frappes_own_bookkeeping_is_never_a_column(spaceview):
	"""`modified`, `owner`, `docstatus`. A manifest naming one is a mistake, and
	a customer reading it is always an accident."""
	assert spaceview._columns(TODO, ["modified", "owner", "docstatus"]) == []


def test_a_screen_that_names_no_columns_still_gets_a_list(spaceview):
	assert spaceview._default_fields(TODO) == ["description"]


def test_a_doctype_with_no_list_fields_falls_back_to_its_title(spaceview):
	plain = meta([field("subject"), field("owner"), field("body", "Text")],
	             title_field="subject")
	assert spaceview._default_fields(plain)[0] == "subject"


def test_frappes_bookkeeping_is_never_a_default_column(spaceview):
	"""`owner`, `docstatus` and friends are Frappe's, and a customer reading them
	is always an accident."""
	plain = meta([field("owner"), field("subject")])
	assert "owner" not in spaceview._default_fields(plain)


# --------------------------------------------------------------------------- #
# The allowlist
# --------------------------------------------------------------------------- #

def test_a_write_is_bounded_by_what_the_screen_shows(spaceview):
	"""Verified against a real site too: writing `reference_type` through a
	screen that shows four other fields leaves it untouched."""
	resolved = {"columns": spaceview._columns(
		TODO, ["description", "status", "reference_name", "colour"])}
	assert spaceview._writable(resolved) == {"description", "status"}


def test_a_screen_with_nothing_editable_writes_nothing(spaceview):
	resolved = {"columns": spaceview._columns(TODO, ["reference_name"])}
	assert spaceview._writable(resolved) == set()


def test_a_filter_that_is_not_an_object_is_dropped(spaceview):
	"""A filter arrives as free text an operator typed. Anything but an object
	is ignored rather than passed to the query layer."""
	assert spaceview._json('{"status": "Open"}') == {"status": "Open"}
	assert spaceview._json("[1, 2, 3]") == {}
	assert spaceview._json("not json at all") == {}
	assert spaceview._json(None) == {}


# --------------------------------------------------------------------------- #
# A saved or pending screen narrows a screen; it never widens one
#
# Filters, sort and columns are chosen in a browser, which means they are a
# string someone sent. Verified against a real site as well — a saved filter of
# `status: Closed` on a screen filtered to `status: Open` returns the same rows
# as before — but the merge rules themselves are pinned here.
# --------------------------------------------------------------------------- #

def resolved_todo(spaceview, fields=("description", "status", "priority", "date")):
	columns = spaceview._columns(TODO, list(fields))
	return {
		"doctype": "ToDo",
		"columns": list(columns),
		"all_columns": list(columns),
		"fields": [c["fieldname"] for c in columns] + ["name"],
		"filters": {"status": "Open"},
		"order_by": "modified desc",
	}


def offered_todo(spaceview, fields=("description", "status", "priority", "date")):
	return {c["fieldname"]: c for c in spaceview._columns(TODO, list(fields))}


def test_a_pending_filter_never_replaces_the_screens_own(spaceview):
	"""Both are applied; neither wins. A saved `status = Closed` on a screen
	filtered to `status = Open` returns nothing rather than quietly returning
	the screen's rows — which is what Frappe's desk does, and "no rows, and
	there is my filter" reads better than a filter that appears to be ignored."""
	out = spaceview._apply_overrides(
		resolved_todo(spaceview), {"filters": [["status", "=", "Closed"]]})
	applied = spaceview._all_filters(out, out["asked"])
	assert ["status", "=", "Open"] in applied
	assert ["status", "=", "Closed"] in applied


def test_a_pending_filter_on_another_field_is_kept(spaceview):
	out = spaceview._apply_overrides(
		resolved_todo(spaceview), {"filters": [["priority", "=", "High"]]})
	assert out["asked"] == [["priority", "=", "High"]]


def test_clearing_the_filters_clears_them(spaceview):
	"""An empty list is a real answer, and a truthiness check would leave the
	saved filters standing while the controls showed none."""
	out = resolved_todo(spaceview)
	out["asked"] = [["priority", "=", "High"]]
	assert spaceview._apply_overrides(out, {"filters": []})["asked"] == []


def test_a_filter_on_a_field_the_screen_hides_is_dropped(spaceview):
	"""It would only narrow the list — and that is the point: someone watching
	which rows come back can read a field they were never shown, one guess at a
	time."""
	out = spaceview._apply_overrides(
		resolved_todo(spaceview), {"filters": [["owner", "=", "someone@x"]]})
	assert out["asked"] == []


# --- operators --------------------------------------------------------------

def test_an_operator_a_fieldtype_does_not_allow_is_dropped(spaceview):
	"""The allow list is Frappe's own, inverted. A Select has no `like` in its
	filter menu and has none here either."""
	offered = offered_todo(spaceview)
	assert spaceview._asked_filters(offered, [["status", "like", "Op"]]) == []
	assert spaceview._asked_filters(offered, [["description", "like", "van"]]) == [
		["description", "like", "van"]]


def test_an_operator_frappe_has_but_never_offers_is_dropped(spaceview):
	"""`regex` and the nested-set operators are in Frappe's OPERATOR_MAP and not
	in its filter menu. One is a way to spend a lot of database time; the other
	runs a subquery against a doctype this screen was never granted."""
	offered = offered_todo(spaceview)
	for operator in ("regex", "ilike", "descendants of", "ancestors of", "+"):
		assert spaceview._asked_filters(offered, [["description", operator, "x"]]) == [], operator


def test_a_value_must_be_the_shape_its_operator_takes(spaceview):
	offered = offered_todo(spaceview)

	# `is` is one of two words.
	assert spaceview._asked_filters(offered, [["date", "is", "set"]]) == [["date", "is", "set"]]
	assert spaceview._asked_filters(offered, [["date", "is", "anything"]]) == []

	# `between` is exactly two.
	assert spaceview._asked_filters(
		offered, [["date", "between", ["2026-01-01", "2026-02-01"]]]
	) == [["date", "between", ["2026-01-01", "2026-02-01"]]]
	assert spaceview._asked_filters(offered, [["date", "between", "2026-01-01"]]) == []
	assert spaceview._asked_filters(offered, [["date", "between", ["a", "b", "c"]]]) == []

	# `timespan` is one of Frappe's own words, because Frappe is what reads it.
	assert spaceview._asked_filters(offered, [["date", "timespan", "last week"]]) == [
		["date", "timespan", "last week"]]
	assert spaceview._asked_filters(offered, [["date", "timespan", "last fortnight"]]) == []

	# A scalar operator will not take a list.
	assert spaceview._asked_filters(offered, [["status", "=", ["Open", "Closed"]]]) == []


def test_in_takes_a_list_or_the_commas_someone_typed(spaceview):
	offered = offered_todo(spaceview)
	assert spaceview._asked_filters(offered, [["status", "in", ["Open", "Closed"]]]) == [
		["status", "in", ["Open", "Closed"]]]
	assert spaceview._asked_filters(offered, [["status", "in", "Open, Closed"]]) == [
		["status", "in", ["Open", "Closed"]]]
	assert spaceview._asked_filters(offered, [["status", "in", []]]) == []


def test_a_filter_that_is_not_three_parts_is_dropped(spaceview):
	offered = offered_todo(spaceview)
	for row in ("status", ["status"], ["status", "="], ["status", "=", "Open", "extra"],
	            {"status": "Open"}, None, 7):
		assert spaceview._asked_filters(offered, [row]) == [], row


def test_the_number_of_filters_and_values_is_bounded(spaceview):
	"""Not a permission boundary — every one is already a field the screen shows
	— but an unbounded list is a way to make one request cost a great deal."""
	offered = offered_todo(spaceview)
	many = [["description", "like", str(n)] for n in range(spaceview.MAX_FILTERS + 20)]
	assert len(spaceview._asked_filters(offered, many)) == spaceview.MAX_FILTERS

	huge = [["status", "in", [str(n) for n in range(spaceview.MAX_IN_VALUES + 50)]]]
	assert len(spaceview._asked_filters(offered, huge)[0][2]) == spaceview.MAX_IN_VALUES


def test_a_like_gets_wildcards_unless_someone_wrote_their_own(spaceview):
	"""Frappe's own rule, so a box labelled "Contains" contains — and a person
	who writes `van%` still gets a prefix match."""
	offered = offered_todo(spaceview)
	assert spaceview._as_query_filters(offered, [["description", "like", "van"]]) == [
		["description", "like", "%van%"]]
	assert spaceview._as_query_filters(offered, [["description", "like", "van%"]]) == [
		["description", "like", "van%"]]


def test_the_old_dict_shape_still_reads(spaceview):
	"""Saved views written before filters had operators are still on disk. They
	are read as what they meant: Frappe's own default operator for the type."""
	offered = offered_todo(spaceview)
	assert spaceview._asked_filters(offered, {"description": "van", "status": "Open"}) == [
		["description", "like", "van"],
		["status", "=", "Open"],
	]


def test_pending_columns_intersect_with_what_the_screen_offers(spaceview):
	out = spaceview._apply_overrides(
		resolved_todo(spaceview), {"columns": ["description", "owner", "_liked_by"]})
	assert [c["fieldname"] for c in out["columns"]] == ["description"]


def test_pending_columns_that_name_nothing_real_leave_the_screen_alone(spaceview):
	before = resolved_todo(spaceview)
	out = spaceview._apply_overrides(dict(before), {"columns": ["owner"]})
	assert [c["fieldname"] for c in out["columns"]] == [c["fieldname"] for c in before["columns"]]


def test_order_by_is_rebuilt_from_parts(spaceview):
	"""It reaches the query layer, so it is never the string that arrived."""
	base = resolved_todo(spaceview)
	assert spaceview._safe_order(base, "date asc") == "date asc"
	# A field the screen does not show, a direction we do not know, and SQL.
	for hostile in ("owner asc", "date sideways", "(select 1) desc -- ",
	                "date asc, (select 1)", "", None):
		assert spaceview._safe_order(base, hostile) == "modified desc"


# --------------------------------------------------------------------------- #
# What a whitelisted method will accept
#
# Frappe validates a whitelisted method's arguments against its own annotations
# and answers a mismatch with a 417 before the body runs. That is a good thing,
# and it bites in a specific way: when filters became a list of triples and the
# annotation still said `str | dict`, every save from the browser was refused
# before reaching a line of the function — while every test here passed, because
# calling the function directly skips the check entirely.
#
# So the annotations are part of the wire contract, not documentation.
# --------------------------------------------------------------------------- #

import ast as _ast  # noqa: E402
import re as _re  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

APPVIEW = _Path(__file__).resolve().parents[1] / "apps/oneapp/oneapp/oneapp_core/spaceview.py"

# The parameters the SPA sends as JSON rather than as a query-string value, and
# the shapes it sends them in. Keyed by `method.param` where the shape belongs
# to the endpoint rather than to the word: `name` is one record on `save` and a
# whole selection on `remove`.
STRUCTURED = {
	"values": {"dict"},
	"filters": {"list", "dict"},
	"columns": {"list"},
	"overrides": {"dict"},
	"remove.name": {"list"},
}


def whitelisted():
	"""Every `@frappe.whitelist` function in spaceview, with its annotations."""
	tree = _ast.parse(APPVIEW.read_text())
	found = {}
	for node in tree.body:
		if not isinstance(node, _ast.FunctionDef):
			continue
		if not any(
			isinstance(d, _ast.Call)
			and _ast.unparse(d.func).endswith("frappe.whitelist")
			for d in node.decorator_list
		):
			continue
		found[node.name] = {
			arg.arg: (_ast.unparse(arg.annotation) if arg.annotation else "")
			for arg in node.args.args
		}
	return found


def test_the_reader_found_the_whitelisted_methods():
	"""A parse that quietly matches nothing passes every test below."""
	found = whitelisted()
	assert {"spec", "rows", "save", "save_layout", "link_options"} <= set(found)


def test_a_structured_argument_admits_the_shape_the_spa_sends():
	for name, params in whitelisted().items():
		for param, annotation in params.items():
			expected = STRUCTURED.get(f"{name}.{param}", STRUCTURED.get(param, ()))
			for shape in expected:
				assert shape in annotation, (
					f"{name}({param}: {annotation}) — the SPA sends a {shape} here and "
					f"Frappe answers a mismatched annotation with a 417 before the "
					f"body runs"
				)


def test_every_argument_admits_a_string():
	"""A GET carries its arguments in the query string, where everything is
	text. An `int`-only annotation is fine — Frappe coerces those — but a
	`dict`-only one rejects the string form of the same value."""
	for name, params in whitelisted().items():
		for param, annotation in params.items():
			if annotation in ("int", "int | None"):
				continue
			assert "str" in annotation, f"{name}({param}: {annotation}) cannot take text"


# --------------------------------------------------------------------------- #
# The manifest's fields are a default, not a ceiling
#
# An app declaring `customer,status,total` is saying "start here". Someone who
# wants the due date on their list should not need a deploy to get it, so the
# column picker offers the doctype's own fields and the manifest decides which
# are on to begin with.
#
# That is a real widening, and what it does not open is the point of these.
# --------------------------------------------------------------------------- #

def test_the_whole_doctype_is_offerable(spaceview):
	offerable = spaceview._offerable(TODO)
	assert "date" in offerable
	assert "colour" in offerable


def test_a_field_above_this_users_permlevel_is_never_offered(spaceview):
	"""Frappe protects these separately, and a screen must not become a way
	around field-level permissions."""
	assert "cost" not in spaceview._offerable(TODO)

	# And it is offered to somebody who may read that level.
	privileged = meta(TODO.fields, title_field="description", permlevels=[0, 1])
	assert "cost" in spaceview._offerable(privileged)


def test_layout_and_child_tables_are_not_columns(spaceview):
	offerable = spaceview._offerable(TODO)
	assert "sec_more" not in offerable, "a section break carries no value"
	assert "items" not in offerable, "a child table is rows, not a value"


def test_frappes_bookkeeping_is_still_out(spaceview):
	assert "modified" not in spaceview._offerable(TODO)


def test_quick_filters_are_the_ones_the_doctype_marked(spaceview):
	"""Frappe's own answer — `in_standard_filter` plus the title field. The
	doctype already decided what people search this thing by."""
	columns = spaceview._columns(TODO, spaceview._offerable(TODO))
	assert spaceview._quick_filters(TODO, columns) == ["description", "status", "priority"]


# --------------------------------------------------------------------------- #
# What a row carries beside its columns
# --------------------------------------------------------------------------- #

def test_a_row_reports_its_comment_count_and_never_its_comments(spaceview, stub_frappe):
	"""`_comments` holds the text, the author and the timestamp of every
	comment. Only the count belongs in a list."""
	stub_frappe.session.user = "someone@example.com"
	row = spaceview._with_meta({
		"name": "abc",
		"modified": "2026-08-30 10:00:00",
		"_comments": '[{"comment": "a secret", "by": "boss@example.com"}, {"comment": "two"}]',
		"_liked_by": '["someone@example.com", "other@example.com"]',
	})

	assert "_comments" not in row
	assert "_liked_by" not in row
	assert row["_meta"]["comments"] == 2
	assert row["_meta"]["likes"] == 2
	assert row["_meta"]["liked"] is True
	assert "secret" not in str(row)


def test_a_row_with_no_comments_or_likes_still_reports(spaceview, stub_frappe):
	stub_frappe.session.user = "someone@example.com"
	row = spaceview._with_meta({"name": "abc", "modified": None})
	assert row["_meta"] == {"modified": None, "comments": 0, "likes": 0, "liked": False}


def test_favourites_can_only_ever_mean_the_person_asking(spaceview, stub_frappe):
	"""`_liked_by` is a JSON array of user ids. A filter naming it could be
	pointed at a colleague and would answer what they had liked, so this is a
	flag the server expands rather than a filter a browser writes."""
	stub_frappe.session.user = "someone@example.com"
	assert spaceview._favourite_filter() == ["_liked_by", "like", "%someone@example.com%"]

	# And the column itself is not offerable, so no filter can name it.
	offered = offered_todo(spaceview)
	assert spaceview._asked_filters(offered, [["_liked_by", "like", "%boss%"]]) == []


def test_the_id_can_be_filtered_even_though_it_is_not_a_column(spaceview):
	"""Frappe's list gives `name` a box of its own above every list, and it is
	the one thing everybody searches by. It is not a column — it lives under the
	title — so it is described rather than looked up."""
	resolved = resolved_todo(spaceview)
	assert spaceview._asked_filters(
		spaceview._filterable(resolved), [["name", "like", "kos"]]
	) == [["name", "like", "kos"]]


def test_the_id_is_still_not_offered_as_a_column(spaceview):
	"""Filterable and offerable are two questions. Answering both from one list
	would put the id in the column picker, where it duplicates the title cell."""
	assert "name" not in spaceview._offerable(TODO)
	out = spaceview._apply_overrides(resolved_todo(spaceview), {"columns": ["name"]})
	assert "name" not in [c["fieldname"] for c in out["columns"]]


def test_a_write_is_bounded_by_the_doctype_not_by_the_manifest(spaceview):
	"""The record dialog shows the doctype's whole field list now, so a write
	has to reach the same set — a control that looks editable and is silently
	discarded is worse than one that is not offered.

	What still bounds it: the doctype must be one the app granted, Frappe's own
	write permission decides, `read_only` is not editable, a field above this
	user's permlevel is not in `all_columns`, and bookkeeping never is.
	"""
	resolved = {
		"columns": spaceview._columns(TODO, ["description"]),
		"all_columns": spaceview._columns(TODO, spaceview._offerable(TODO)),
	}
	writable = spaceview._writable(resolved)

	# Outside the manifest's list, and writable.
	assert "date" in writable
	# Read-only stays read-only.
	assert "reference_name" not in writable
	# No frappe-ui control means no write, whatever else is true.
	assert "colour" not in writable
	# Above this user's permlevel: never offered, so never writable.
	assert "cost" not in writable
	# Bookkeeping, always.
	assert "modified" not in writable


# --------------------------------------------------------------------------- #
# A column is a fieldname, a width and where it sticks
#
# All three are the reader's, not ours: which columns, how wide, and whether one
# stays put while the rest scroll. We pin nothing by default — guessing that for
# somebody is how the activity column ended up glued to an edge nobody asked
# for.
# --------------------------------------------------------------------------- #

def offerable_todo(spaceview):
	return {c["fieldname"]: c for c in
	        [*spaceview._columns(TODO, spaceview._offerable(TODO)), spaceview._meta_column()]}


def test_activity_is_a_column_like_any_other(spaceview):
	"""Every list carries when a row changed and what has been said about it —
	and a person who does not want that should be able to drop it the same way
	they drop anything else."""
	offered = offerable_todo(spaceview)
	assert spaceview.META_COLUMN in offered

	placed = spaceview._placed(offered, [{"fieldname": spaceview.META_COLUMN}])
	assert placed and placed[0]["cell"] == "meta"


def test_activity_is_never_asked_of_the_database(spaceview):
	"""It is a column and not a field. Asking for it is a SQL error rather than
	an empty cell."""
	offered = offerable_todo(spaceview)
	placed = spaceview._placed(offered, [{"fieldname": "status"},
	                                   {"fieldname": spaceview.META_COLUMN}])
	fields = spaceview._fetch_fields(placed)
	assert "status" in fields
	assert spaceview.META_COLUMN not in fields
	assert "name" in fields


def test_a_width_is_clamped_rather_than_trusted(spaceview):
	"""It reaches a CSS grid track. A browser sending 900000 is asking the
	layout to do something silly, not asking for a wide column."""
	offered = offerable_todo(spaceview)
	wide = spaceview._placed(offered, [{"fieldname": "status", "width": 900000}])
	assert wide[0]["width"] == spaceview.MAX_WIDTH

	thin = spaceview._placed(offered, [{"fieldname": "status", "width": 1}])
	assert thin[0]["width"] == spaceview.MIN_WIDTH

	junk = spaceview._placed(offered, [{"fieldname": "status", "width": "wide"}])
	assert junk[0]["width"] == spaceview._default_width(offered["status"])


def test_a_pin_is_one_of_two_edges(spaceview):
	offered = offerable_todo(spaceview)
	for pin, expected in (("left", "left"), ("right", "right"), ("middle", None),
	                      (None, None), (["left"], None)):
		placed = spaceview._placed(offered, [{"fieldname": "status", "pin": pin}])
		assert placed[0]["pin"] == expected, pin


def test_a_column_the_screen_does_not_offer_is_dropped(spaceview):
	offered = offerable_todo(spaceview)
	assert spaceview._placed(offered, [{"fieldname": "owner", "width": 200}]) == []


def test_the_order_someone_chose_is_the_order_they_get(spaceview):
	offered = offerable_todo(spaceview)
	placed = spaceview._placed(offered, [{"fieldname": "date"}, {"fieldname": "status"}])
	assert [c["fieldname"] for c in placed] == ["date", "status"]


def test_the_comma_separated_shape_still_reads(spaceview):
	"""Views saved before a column carried a width are still on disk."""
	offered = offerable_todo(spaceview)
	placed = spaceview._placed(offered, "description,status")
	assert [c["fieldname"] for c in placed] == ["description", "status"]
	assert all(c["width"] and c["pin"] is None for c in placed)


def test_a_json_string_of_columns_reads_the_same_as_a_list(spaceview):
	"""It arrives as a string from the browser and as a string out of the
	database, and as a list from a direct call. The one call site that forgot to
	parse it stored an empty list and silently kept the screen's defaults —
	which looks exactly like a save that worked."""
	offered = offerable_todo(spaceview)
	wanted = [{"fieldname": "status", "width": 200, "pin": "left"}]

	from json import dumps
	assert spaceview._placed(offered, dumps(wanted)) == spaceview._placed(offered, wanted)
	assert spaceview._placed(offered, dumps(wanted))[0]["width"] == 200
	assert spaceview._placed(offered, dumps(wanted))[0]["pin"] == "left"


def test_grouping_names_a_column_the_screen_offers(spaceview):
	resolved = resolved_todo(spaceview)
	resolved["all_columns"] = spaceview._columns(TODO, spaceview._offerable(TODO))

	assert spaceview._group_by(resolved, "status") == "status"
	assert spaceview._group_by(resolved, "owner") == "", "a field the screen hides"
	assert spaceview._group_by(resolved, spaceview.META_COLUMN) == "", "not a field"
	assert spaceview._group_by(resolved, "name") == "", "one group per row is not a grouping"
	assert spaceview._group_by(resolved, "") == ""
	assert spaceview._group_by(resolved, None) == ""


def test_grouping_sorts_by_the_group_first(spaceview):
	"""The page is one query. A group whose rows are scattered through it
	renders as the same heading three times."""
	resolved = resolved_todo(spaceview)
	resolved["all_columns"] = spaceview._columns(TODO, spaceview._offerable(TODO))

	resolved["group_by"] = ""
	assert spaceview._grouped_order(resolved) == "modified desc"

	resolved["group_by"] = "status"
	assert spaceview._grouped_order(resolved) == "status asc, modified desc"

	# Already leading with it, so nothing to add.
	resolved["order_by"] = "status desc"
	assert spaceview._grouped_order(resolved) == "status desc"


# --------------------------------------------------------------------------- #
# Saved views are named layouts
#
# Frappe's `List Filter` doctype is the framework's answer to this, and it is
# the one to follow: a layout has a name, and `for_user` empty means everybody.
# Frappe CRM built its own before the framework had one — a good design, but a
# parallel one, and a parallel one is the thing that drifts.
# --------------------------------------------------------------------------- #

def layout(name, label="", user="me@x", is_default=0, view_type="list"):
	return {
		"name": name, "label": label, "user": user, "is_default": is_default,
		"shared": not user, "mine": user == "me@x", "view_type": view_type,
		"filters": "[]", "order_by": "", "columns": "[]", "view_settings": "{}",
		"page_length": 0, "group_by": "", "favourites": 0,
	}


def test_my_own_default_outranks_the_workspaces(spaceview):
	"""A shared default is a starting point, not an override.

	An operator marking a screen as the workspace's default is saying "start
	here"; someone who has since chosen their own has already answered that.
	"""
	rows = [layout("shared", "House", user="", is_default=1),
	        layout("mine", "Mine", is_default=1)]
	assert spaceview._default_layout(rows)["name"] == "mine"


def test_the_workspaces_default_opens_a_screen_nobody_has_answered_for(spaceview):
	rows = [layout("shared", "House", user="", is_default=1), layout("other", "Other")]
	assert spaceview._default_layout(rows)["name"] == "shared"


def test_nothing_is_default_when_nothing_is_marked(spaceview):
	assert spaceview._default_layout([layout("a", "A"), layout("b", "B")]) is None


def test_a_layout_that_was_asked_for_wins_over_the_default(spaceview):
	rows = [layout("mine", "Mine", is_default=1), layout("other", "Other")]
	assert spaceview._chosen_layout(rows, "other")["name"] == "other"


def test_a_bookmark_to_a_deleted_layout_falls_back(spaceview):
	"""A link to a screen somebody has since deleted still opens the screen.

	Throwing here would turn a stale bookmark into a page that cannot be
	reached at all, which is a worse answer than the screen's own default.
	"""
	rows = [layout("mine", "Mine", is_default=1)]
	assert spaceview._chosen_layout(rows, "gone")["name"] == "mine"
	assert spaceview._chosen_layout([], "gone") is None


def test_only_one_layout_is_marked_as_the_one_that_opens(spaceview, monkeypatch):
	"""Two rows can both be `is_default`; only one of them opens the screen.

	One personal and one shared is a legitimate state, and a menu that pins
	both is telling the reader something untrue.
	"""
	rows = [layout("shared", "House", user="", is_default=1),
	        layout("mine", "Mine", is_default=1)]
	monkeypatch.setattr(spaceview, "_layouts", lambda *a: rows)
	monkeypatch.setattr(spaceview, "_can_share", lambda: False)
	resolved = spaceview._apply_saved({"space": "a", "screen": "v"})
	assert [l["opens"] for l in resolved["layouts"]] == [False, True]
	assert sum(l["is_default"] for l in resolved["layouts"]) == 2


class _Doc(dict):
	__getattr__ = dict.get

	def __setattr__(self, key, value):
		self[key] = value


def test_a_shared_layout_needs_the_workspaces_own_admin_rights(spaceview, stub_frappe, monkeypatch):
	monkeypatch.setattr(spaceview, "_can_share", lambda: False)
	with pytest.raises(stub_frappe.PermissionError):
		spaceview._may_write(_Doc(user=""))
	monkeypatch.setattr(spaceview, "_can_share", lambda: True)
	spaceview._may_write(_Doc(user=""))


def test_a_personal_layout_belongs_to_one_person(spaceview, stub_frappe, monkeypatch):
	monkeypatch.setattr(spaceview, "_can_share", lambda: True)
	stub_frappe.session.user = "me@x"
	spaceview._may_write(_Doc(user="me@x"))
	# Even a workspace admin does not edit somebody else's private screen: sharing
	# rights are about the shared shelf, not about everyone's shelf.
	with pytest.raises(stub_frappe.PermissionError):
		spaceview._may_write(_Doc(user="someone@else"))


def test_a_shared_layout_still_only_reaches_what_the_screen_offers(spaceview, monkeypatch):
	"""Sharing does not widen a layout.

	The row is a doctype an operator could write directly, so what it carries is
	re-checked against the screen every time it is read — not only when it was
	saved through the endpoint.
	"""
	rows = [dict(layout("shared", "House", user="", is_default=1),
	             filters='[["_liked_by", "like", "%someone@else%"]]')]
	monkeypatch.setattr(spaceview, "_layouts", lambda *a: rows)
	monkeypatch.setattr(spaceview, "_can_share", lambda: True)
	resolved = spaceview._apply_saved({
		"space": "a", "screen": "v", "doctype": "ToDo",
		"columns": spaceview._columns(TODO, ["description"]),
		"all_columns": spaceview._columns(TODO, ["description"]),
		"order_by": "modified desc",
	})
	assert resolved["asked"] == []


# --------------------------------------------------------------------------- #
# Paging
#
# A list that stops at its first page and says nothing reads as "that is all of
# them". Frappe CRM's footer is the answer: a page size, a load-more, and a
# count of what actually matches.
# --------------------------------------------------------------------------- #

def test_a_page_size_is_one_the_footer_offers(spaceview):
	"""Not clamped to a range — checked against the set.

	The footer is four buttons, so a number that is not one of them did not come
	from the footer. Clamping would turn 10,000 into the largest page we offer
	and quietly answer a request nobody made.
	"""
	for size in spaceview.PAGE_SIZES:
		assert spaceview._page_length(size) == size
		assert spaceview._page_length(str(size)) == size
	for junk in (0, None, "", 37, 10_000, -20, "twenty", [50]):
		assert spaceview._page_length(junk) == 0


def test_the_page_size_ceiling_is_the_largest_the_footer_offers(spaceview):
	"""`rows` bounds `limit` separately, and the two have to agree — a footer
	button the endpoint would refuse is a button that does nothing."""
	assert max(spaceview.PAGE_SIZES) == spaceview.MAX_PAGE
	assert spaceview.PAGE in spaceview.PAGE_SIZES


def test_a_saved_page_size_survives_and_a_junk_one_does_not(spaceview, monkeypatch):
	rows = [dict(layout("mine", "Mine", is_default=1), page_length=20)]
	monkeypatch.setattr(spaceview, "_layouts", lambda *a: rows)
	monkeypatch.setattr(spaceview, "_can_share", lambda: False)
	resolved = spaceview._apply_saved({
		"space": "a", "screen": "v", "doctype": "ToDo", "page_length": spaceview.PAGE,
		"columns": spaceview._columns(TODO, ["description"]),
		"all_columns": spaceview._columns(TODO, ["description"]),
		"order_by": "modified desc",
	})
	assert resolved["page_length"] == 20

	rows[0]["page_length"] = 999
	resolved = spaceview._apply_saved({
		"space": "a", "screen": "v", "doctype": "ToDo", "page_length": spaceview.PAGE,
		"columns": spaceview._columns(TODO, ["description"]),
		"all_columns": spaceview._columns(TODO, ["description"]),
		"order_by": "modified desc",
	})
	assert resolved["page_length"] == spaceview.PAGE


def test_the_count_goes_through_the_same_permissions_as_the_rows(spaceview):
	"""`get_list`, not `db.count`.

	`db.count` skips the permission query and User Permissions, so it can be
	larger than the list it labels — and "12 of 400" over twelve rows is worse
	than no count at all.
	"""
	source = APPVIEW.read_text()
	body = source[source.index("def _total("):]
	body = body[: body.index("\n\n\n")]
	# Code only — the docstring names `db.count` to say why it is not used.
	code = body[body.index('"""', body.index('"""') + 3) + 3 :]
	assert "frappe.get_list(" in code
	assert "db.count" not in code
	# A SQL function written as a string is refused at runtime, and only at
	# runtime — the dict form is the one Frappe accepts.
	assert '{"COUNT": "*"}' in body


# --------------------------------------------------------------------------- #
# View types
#
# A screen is looked at through one of several types. Only the list is built;
# the rest are named so a manifest can declare one before it ships, and so the
# vocabulary lives in one place rather than in three components.
# --------------------------------------------------------------------------- #

VIEW_TYPES_JS = (
	_Path(__file__).resolve().parents[1]
	/ "apps/oneapp/frontend/src/lib/viewTypes.js"
)


def test_the_two_halves_agree_on_what_a_view_type_is(spaceview):
	"""The server decides what a saved layout is tagged with; the SPA decides
	what the sidebar offers. A type in one and not the other is a menu entry
	that resolves to nothing, or a stored layout no switcher will show."""
	source = VIEW_TYPES_JS.read_text()
	declared = set(_re.findall(r"^  (\w+): \{", source, _re.M))
	assert declared == set(spaceview.VIEW_TYPES), (
		f"lib/viewTypes.js has {sorted(declared)}, spaceview has "
		f"{sorted(spaceview.VIEW_TYPES)}"
	)

	built = set(_re.findall(r"^  (\w+): \{[^}]*built: true", source, _re.M | _re.S))
	assert built == set(spaceview.BUILT_VIEW_TYPES)


def test_a_screen_offers_what_it_declares_and_nothing_it_cannot_draw(spaceview):
	assert spaceview._view_types({"view_types": "list"}) == ["list"]
	# Unbuilt types are dropped rather than refused: a manifest naming one gets
	# a list today and the real thing the day it ships.
	assert spaceview._view_types({"view_types": "list,board"}) == ["list"]
	assert spaceview._view_types({"view_types": "board"}) == ["list"]
	# Order is the manifest's, duplicates collapse, and nothing declared is
	# still a list.
	assert spaceview._view_types({"view_types": "list, list"}) == ["list"]
	assert spaceview._view_types({}) == ["list"]
	assert spaceview._view_types({"view_types": ""}) == ["list"]


def test_a_view_settings_fieldname_is_checked_like_any_other(spaceview):
	"""A board's column field is a fieldname that reaches a query.

	"It came from the settings blob" is not a reason to trust one, so every
	value ending in `_field` is checked against the screen's own columns the
	same way a filter or a sort is.
	"""
	resolved = {"all_columns": spaceview._columns(TODO, ["status", "description"])}
	kept = spaceview._view_settings(resolved, {"column_field": "status"})
	assert kept == {"column_field": "status"}
	# Not a column here, so not a setting.
	assert spaceview._view_settings(resolved, {"column_field": "owner"}) == {}
	# Not a fieldname at all, so not carried.
	assert spaceview._view_settings(resolved, {"colour": "red"}) == {}
	assert spaceview._view_settings(resolved, "not json at all") == {}
