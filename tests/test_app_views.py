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


def offered_todo(appview, fields=("description", "status", "priority", "date")):
	return {c["fieldname"]: c for c in appview._columns(TODO, list(fields))}


def test_a_pending_filter_never_replaces_the_screens_own(appview):
	"""Both are applied; neither wins. A saved `status = Closed` on a screen
	filtered to `status = Open` returns nothing rather than quietly returning
	the screen's rows — which is what Frappe's desk does, and "no rows, and
	there is my filter" reads better than a filter that appears to be ignored."""
	out = appview._apply_overrides(
		resolved_todo(appview), {"filters": [["status", "=", "Closed"]]})
	applied = appview._all_filters(out, out["asked"])
	assert ["status", "=", "Open"] in applied
	assert ["status", "=", "Closed"] in applied


def test_a_pending_filter_on_another_field_is_kept(appview):
	out = appview._apply_overrides(
		resolved_todo(appview), {"filters": [["priority", "=", "High"]]})
	assert out["asked"] == [["priority", "=", "High"]]


def test_clearing_the_filters_clears_them(appview):
	"""An empty list is a real answer, and a truthiness check would leave the
	saved filters standing while the controls showed none."""
	out = resolved_todo(appview)
	out["asked"] = [["priority", "=", "High"]]
	assert appview._apply_overrides(out, {"filters": []})["asked"] == []


def test_a_filter_on_a_field_the_screen_hides_is_dropped(appview):
	"""It would only narrow the list — and that is the point: someone watching
	which rows come back can read a field they were never shown, one guess at a
	time."""
	out = appview._apply_overrides(
		resolved_todo(appview), {"filters": [["owner", "=", "someone@x"]]})
	assert out["asked"] == []


# --- operators --------------------------------------------------------------

def test_an_operator_a_fieldtype_does_not_allow_is_dropped(appview):
	"""The allow list is Frappe's own, inverted. A Select has no `like` in its
	filter menu and has none here either."""
	offered = offered_todo(appview)
	assert appview._asked_filters(offered, [["status", "like", "Op"]]) == []
	assert appview._asked_filters(offered, [["description", "like", "van"]]) == [
		["description", "like", "van"]]


def test_an_operator_frappe_has_but_never_offers_is_dropped(appview):
	"""`regex` and the nested-set operators are in Frappe's OPERATOR_MAP and not
	in its filter menu. One is a way to spend a lot of database time; the other
	runs a subquery against a doctype this screen was never granted."""
	offered = offered_todo(appview)
	for operator in ("regex", "ilike", "descendants of", "ancestors of", "+"):
		assert appview._asked_filters(offered, [["description", operator, "x"]]) == [], operator


def test_a_value_must_be_the_shape_its_operator_takes(appview):
	offered = offered_todo(appview)

	# `is` is one of two words.
	assert appview._asked_filters(offered, [["date", "is", "set"]]) == [["date", "is", "set"]]
	assert appview._asked_filters(offered, [["date", "is", "anything"]]) == []

	# `between` is exactly two.
	assert appview._asked_filters(
		offered, [["date", "between", ["2026-01-01", "2026-02-01"]]]
	) == [["date", "between", ["2026-01-01", "2026-02-01"]]]
	assert appview._asked_filters(offered, [["date", "between", "2026-01-01"]]) == []
	assert appview._asked_filters(offered, [["date", "between", ["a", "b", "c"]]]) == []

	# `timespan` is one of Frappe's own words, because Frappe is what reads it.
	assert appview._asked_filters(offered, [["date", "timespan", "last week"]]) == [
		["date", "timespan", "last week"]]
	assert appview._asked_filters(offered, [["date", "timespan", "last fortnight"]]) == []

	# A scalar operator will not take a list.
	assert appview._asked_filters(offered, [["status", "=", ["Open", "Closed"]]]) == []


def test_in_takes_a_list_or_the_commas_someone_typed(appview):
	offered = offered_todo(appview)
	assert appview._asked_filters(offered, [["status", "in", ["Open", "Closed"]]]) == [
		["status", "in", ["Open", "Closed"]]]
	assert appview._asked_filters(offered, [["status", "in", "Open, Closed"]]) == [
		["status", "in", ["Open", "Closed"]]]
	assert appview._asked_filters(offered, [["status", "in", []]]) == []


def test_a_filter_that_is_not_three_parts_is_dropped(appview):
	offered = offered_todo(appview)
	for row in ("status", ["status"], ["status", "="], ["status", "=", "Open", "extra"],
	            {"status": "Open"}, None, 7):
		assert appview._asked_filters(offered, [row]) == [], row


def test_the_number_of_filters_and_values_is_bounded(appview):
	"""Not a permission boundary — every one is already a field the screen shows
	— but an unbounded list is a way to make one request cost a great deal."""
	offered = offered_todo(appview)
	many = [["description", "like", str(n)] for n in range(appview.MAX_FILTERS + 20)]
	assert len(appview._asked_filters(offered, many)) == appview.MAX_FILTERS

	huge = [["status", "in", [str(n) for n in range(appview.MAX_IN_VALUES + 50)]]]
	assert len(appview._asked_filters(offered, huge)[0][2]) == appview.MAX_IN_VALUES


def test_a_like_gets_wildcards_unless_someone_wrote_their_own(appview):
	"""Frappe's own rule, so a box labelled "Contains" contains — and a person
	who writes `van%` still gets a prefix match."""
	offered = offered_todo(appview)
	assert appview._as_query_filters(offered, [["description", "like", "van"]]) == [
		["description", "like", "%van%"]]
	assert appview._as_query_filters(offered, [["description", "like", "van%"]]) == [
		["description", "like", "van%"]]


def test_the_old_dict_shape_still_reads(appview):
	"""Saved views written before filters had operators are still on disk. They
	are read as what they meant: Frappe's own default operator for the type."""
	offered = offered_todo(appview)
	assert appview._asked_filters(offered, {"description": "van", "status": "Open"}) == [
		["description", "like", "van"],
		["status", "=", "Open"],
	]


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
from pathlib import Path as _Path  # noqa: E402

APPVIEW = _Path(__file__).resolve().parents[1] / "apps/oneapp/oneapp/oneapp_core/appview.py"

# The parameters the SPA sends as JSON rather than as a query-string value, and
# the shapes it sends them in.
STRUCTURED = {
	"values": {"dict"},
	"filters": {"list", "dict"},
	"columns": {"list"},
	"overrides": {"dict"},
}


def whitelisted():
	"""Every `@frappe.whitelist` function in appview, with its annotations."""
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
	assert {"spec", "rows", "save", "save_view", "link_options"} <= set(found)


def test_a_structured_argument_admits_the_shape_the_spa_sends():
	for name, params in whitelisted().items():
		for param, annotation in params.items():
			for shape in STRUCTURED.get(param, ()):
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

def test_the_whole_doctype_is_offerable(appview):
	offerable = appview._offerable(TODO)
	assert "date" in offerable
	assert "colour" in offerable


def test_a_field_above_this_users_permlevel_is_never_offered(appview):
	"""Frappe protects these separately, and a screen must not become a way
	around field-level permissions."""
	assert "cost" not in appview._offerable(TODO)

	# And it is offered to somebody who may read that level.
	privileged = meta(TODO.fields, title_field="description", permlevels=[0, 1])
	assert "cost" in appview._offerable(privileged)


def test_layout_and_child_tables_are_not_columns(appview):
	offerable = appview._offerable(TODO)
	assert "sec_more" not in offerable, "a section break carries no value"
	assert "items" not in offerable, "a child table is rows, not a value"


def test_frappes_bookkeeping_is_still_out(appview):
	assert "modified" not in appview._offerable(TODO)


def test_quick_filters_are_the_ones_the_doctype_marked(appview):
	"""Frappe's own answer — `in_standard_filter` plus the title field. The
	doctype already decided what people search this thing by."""
	columns = appview._columns(TODO, appview._offerable(TODO))
	assert appview._quick_filters(TODO, columns) == ["description", "status", "priority"]


# --------------------------------------------------------------------------- #
# What a row carries beside its columns
# --------------------------------------------------------------------------- #

def test_a_row_reports_its_comment_count_and_never_its_comments(appview, stub_frappe):
	"""`_comments` holds the text, the author and the timestamp of every
	comment. Only the count belongs in a list."""
	stub_frappe.session.user = "someone@example.com"
	row = appview._with_meta({
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


def test_a_row_with_no_comments_or_likes_still_reports(appview, stub_frappe):
	stub_frappe.session.user = "someone@example.com"
	row = appview._with_meta({"name": "abc", "modified": None})
	assert row["_meta"] == {"modified": None, "comments": 0, "likes": 0, "liked": False}


def test_favourites_can_only_ever_mean_the_person_asking(appview, stub_frappe):
	"""`_liked_by` is a JSON array of user ids. A filter naming it could be
	pointed at a colleague and would answer what they had liked, so this is a
	flag the server expands rather than a filter a browser writes."""
	stub_frappe.session.user = "someone@example.com"
	assert appview._favourite_filter() == ["_liked_by", "like", "%someone@example.com%"]

	# And the column itself is not offerable, so no filter can name it.
	offered = offered_todo(appview)
	assert appview._asked_filters(offered, [["_liked_by", "like", "%boss%"]]) == []


def test_the_id_can_be_filtered_even_though_it_is_not_a_column(appview):
	"""Frappe's list gives `name` a box of its own above every list, and it is
	the one thing everybody searches by. It is not a column — it lives under the
	title — so it is described rather than looked up."""
	resolved = resolved_todo(appview)
	assert appview._asked_filters(
		appview._filterable(resolved), [["name", "like", "kos"]]
	) == [["name", "like", "kos"]]


def test_the_id_is_still_not_offered_as_a_column(appview):
	"""Filterable and offerable are two questions. Answering both from one list
	would put the id in the column picker, where it duplicates the title cell."""
	assert "name" not in appview._offerable(TODO)
	out = appview._apply_overrides(resolved_todo(appview), {"columns": ["name"]})
	assert "name" not in [c["fieldname"] for c in out["columns"]]


def test_a_write_is_bounded_by_the_doctype_not_by_the_manifest(appview):
	"""The record dialog shows the doctype's whole field list now, so a write
	has to reach the same set — a control that looks editable and is silently
	discarded is worse than one that is not offered.

	What still bounds it: the doctype must be one the app granted, Frappe's own
	write permission decides, `read_only` is not editable, a field above this
	user's permlevel is not in `all_columns`, and bookkeeping never is.
	"""
	resolved = {
		"columns": appview._columns(TODO, ["description"]),
		"all_columns": appview._columns(TODO, appview._offerable(TODO)),
	}
	writable = appview._writable(resolved)

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
