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
from pathlib import Path

import pytest
import spaceview_source


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
		hidden=kw.get("hidden", 0),
		allow_in_quick_entry=kw.get("allow_in_quick_entry", 0),
		in_preview=kw.get("in_preview", 0),
		bold=kw.get("bold", 0),
		columns=kw.get("columns", 0),
		hide_days=kw.get("hide_days", 0),
		hide_seconds=kw.get("hide_seconds", 0),
		set_only_once=kw.get("set_only_once", 0),
		fetch_from=kw.get("fetch_from", None),
		depends_on=kw.get("depends_on", None),
		mandatory_depends_on=kw.get("mandatory_depends_on", None),
		read_only_depends_on=kw.get("read_only_depends_on", None),
		length=kw.get("length", 0),
		min_value=kw.get("min_value", None),
		max_value=kw.get("max_value", None),
		sort_options=kw.get("sort_options", 0),
		unique=kw.get("unique", 0),
		not_nullable=kw.get("not_nullable", 0),
		allow_on_submit=kw.get("allow_on_submit", 0),
		fetch_if_empty=kw.get("fetch_if_empty", 0),
		remember_last_selected_value=kw.get("remember_last_selected_value", 0),
		documentation_url=kw.get("documentation_url", None),
		show_description_on_click=kw.get("show_description_on_click", 0),
		mask=kw.get("mask", None),
		max_height=kw.get("max_height", None),
		translatable=kw.get("translatable", 0),
		ignore_user_permissions=kw.get("ignore_user_permissions", 0),
		collapsible=kw.get("collapsible", 0),
		collapsible_depends_on=kw.get("collapsible_depends_on", None),
		hide_border=kw.get("hide_border", 0),
	)


def meta(fields, title_field=None, **kw):
	# Frappe's Meta is a Document, so `meta.get("name")` is how its own doctype
	# name is read — which the resolver does for a label. A SimpleNamespace has
	# no `.get`, and without one the failure is an AttributeError from inside
	# the code under test rather than a missing label.
	name = kw.get("name", "Thing")
	return types.SimpleNamespace(
		fields=fields, title_field=title_field, name=name,
		get=lambda key, default=None: {"name": name}.get(key, default),
		image_field=kw.get("image_field"),
		search_fields=kw.get("search_fields", ""),
		sort_field=kw.get("sort_field", "modified"),
		sort_order=kw.get("sort_order", "DESC"),
		states=kw.get("states", []),
		is_submittable=kw.get("is_submittable", 0),
		track_changes=kw.get("track_changes", 0),
		track_seen=0, max_attachments=0, autoname=kw.get("autoname", ""),
		# Which permlevels this user may read, and which they may write.
		# Frappe's own answer, and two separate ones: a field above the read
		# levels is a field this screen must not offer at all, and a field
		# above the write levels is one it must not let anybody type into.
		get_permlevel_access=lambda ptype="read", *a, **k: kw.get(
			"write_levels" if ptype == "write" else "permlevels", [0]
		),
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
		field("plumbing", "Data", "Plumbing", hidden=1),
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

SPACEVIEW = _Path(__file__).resolve().parents[1] / "apps/oneapp/oneapp/oneapp_core/spaceview"

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
	"assign.users": {"list"},
}


def whitelisted():
	"""Every `@frappe.whitelist` function in spaceview, with its annotations."""
	tree = spaceview_source.tree()
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
	assert {"spec", "rows", "record", "save", "save_layout", "link_options"} <= set(found)


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


def test_layout_is_not_a_column(spaceview):
	offerable = spaceview._offerable(TODO)
	assert "sec_more" not in offerable, "a section break carries no value"


def test_a_child_table_is_offered_to_the_record_and_kept_off_the_list(spaceview):
	"""Rows are a real thing on a record and nothing at all in a cell one line
	high — so it is offered, and `list_ok` is what keeps it out of the list and
	its column picker.

	It used to be excluded from `_offerable` outright, which is why
	`Table MultiSelect` was mapped to a control nobody could reach: `_placed`
	intersects the manifest with what is offered, so a screen naming one got
	nothing at all.
	"""
	assert "items" in spaceview._offerable(TODO)

	by_name = {c["fieldname"]: c for c in spaceview._columns(TODO, spaceview._offerable(TODO))}
	assert by_name["items"]["list_ok"] is False
	assert by_name["description"]["list_ok"] is True


def test_a_password_is_not_a_column_either(spaceview):
	"""Same rule, different reason: a value nobody may read is not a cell. The
	point of `list_ok` is that this needed no new rule."""
	fields = [field("secret", "Password", "Secret")]
	assert spaceview._columns(meta(fields), ["secret"])[0]["list_ok"] is False


def test_frappes_bookkeeping_is_still_out(spaceview):
	assert "modified" not in spaceview._offerable(TODO)


def test_a_hidden_field_is_not_offered(spaceview):
	"""The doctype hid it, so it is plumbing rather than a column.

	This was checked on the quick-create form and nowhere else, which put every
	hidden field of a busy doctype into the column picker, the list and the
	record form.
	"""
	assert "plumbing" not in spaceview._offerable(TODO)


def test_a_manifest_may_still_name_a_hidden_field(spaceview):
	"""The picker narrows; an explicit intent stands.

	A space naming a hidden field is a considered choice about a doctype we do
	not own, made in code we wrote.
	"""
	assert "plumbing" in spaceview._offerable(TODO, keep=["plumbing"])
	# And naming one does not open the others.
	assert "modified" not in spaceview._offerable(TODO, keep=["plumbing", "modified"])


def test_naming_a_hidden_field_does_not_reopen_permlevel(spaceview):
	"""The manifest is trusted about presentation, never about permissions."""
	assert "cost" not in spaceview._offerable(TODO, keep=["cost"])


def test_the_doctypes_bounds_reach_the_browser(spaceview):
	"""`length`, `min_value`, `max_value` and `sort_options` were on the
	docfield and never travelled, so the control could not honour them."""
	fields = [
		field("code", "Data", "Code", length=8),
		field("qty", "Int", "Quantity", min_value=1, max_value=99),
		field("floor", "Int", "Floor", min_value=0),
		field("kind", "Select", "Kind", options="b\na", sort_options=1),
	]
	columns = {c["fieldname"]: c for c in spaceview._columns(meta(fields), [f.fieldname for f in fields])}

	assert columns["code"]["length"] == 8
	assert columns["qty"]["min_value"] == 1
	assert columns["qty"]["max_value"] == 99
	assert columns["kind"]["sort_options"] == 1


def test_the_rest_of_the_docfield_travels(spaceview):
	"""Every property the form has somewhere to put. Asserted as one list
	because the failure this guards against is a property quietly stopping —
	nothing throws, the affordance simply is not there any more."""
	fields = [field(
		"code", "Data", "Code",
		unique=1, not_nullable=1, allow_on_submit=1, fetch_if_empty=1,
		remember_last_selected_value=1, documentation_url="https://example.test/code",
		show_description_on_click=1, mask="AA-999", max_height="120",
		translatable=1, ignore_user_permissions=1,
	)]
	column = spaceview._columns(meta(fields), ["code"])[0]

	assert column["unique"] == 1
	assert column["not_nullable"] == 1
	assert column["allow_on_submit"] == 1
	assert column["fetch_if_empty"] == 1
	assert column["remember_last_selected_value"] == 1
	assert column["documentation_url"] == "https://example.test/code"
	assert column["show_description_on_click"] == 1
	assert column["mask"] == "AA-999"
	assert column["max_height"] == "120"
	assert column["translatable"] == 1
	assert column["ignore_user_permissions"] == 1


def test_ignore_user_permissions_is_carried_and_not_acted_on(spaceview):
	"""A docfield saying User Permissions do not apply to this Link is a
	legitimate escape hatch in the desk, where an administrator is reasoning
	about their own site. Here it would let a doctype we did not write widen
	what a customer's screen can reach.

	So it travels — the payload should be honest about what the doctype says —
	and nothing reads it. This asserts the second half: the resolver has no
	branch on it anywhere.
	"""
	import inspect

	source = inspect.getsource(spaceview)
	uses = [
		line.strip() for line in source.splitlines()
		if "ignore_user_permissions" in line
		# The two lines that carry it: the payload key and the docfield read.
		# Everything else is a branch on it, which is the thing being refused.
		and not line.strip().startswith('"ignore_user_permissions"')
		and "getattr(df" not in line
		and not line.strip().startswith("#")
	]
	assert not uses, f"ignore_user_permissions is being acted on: {uses}"


def test_a_section_carries_its_own_collapse_and_border(spaceview):
	"""`collapsible`, `collapsible_depends_on` and `hide_border` are the
	section's, not the field's, so they ride on the layout rather than in
	`all_columns`."""
	fields = [
		field("sec_one", "Section Break", "First"),
		field("a", "Data", "A"),
		field("sec_two", "Section Break", "Second", collapsible=1,
		      collapsible_depends_on="eval:doc.a", hide_border=1),
		field("b", "Data", "B"),
	]
	offered = {"a": {}, "b": {}}
	sections = spaceview._form(meta(fields), offered)[0]["sections"]

	assert sections[0]["collapsible"] == 0
	assert sections[0]["hide_border"] == 0
	assert sections[1]["collapsible"] == 1
	assert sections[1]["collapsible_depends_on"] == "eval:doc.a"
	assert sections[1]["hide_border"] == 1


def test_a_record_carries_its_docstatus(spaceview):
	"""Never a column — HIDDEN sees to that — and required on the record, or a
	submitted document offers every field and has every save refused."""
	assert "docstatus" in spaceview.RECORD_META


def test_a_bound_of_zero_is_not_a_bound(spaceview):
	"""Because it is not one on the server either.

	`_validate_min_max_value` skips a field when neither bound is truthy and
	then guards each with `if min_value and ...`, so a zero bound is inert in
	Frappe. Sending it as a real one would make the browser refuse a negative
	number the database accepts — a control stricter than the thing it writes
	to, which is the worst way for the two to disagree.
	"""
	fields = [field("floor", "Int", "Floor", min_value=0), field("depth", "Int", "Depth", min_value=-5)]
	columns = {c["fieldname"]: c for c in spaceview._columns(meta(fields), ["floor", "depth"])}

	assert columns["floor"]["min_value"] is None
	assert columns["depth"]["min_value"] == -5, "a negative bound is a real one"


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
	assert row["_meta"] == {
		"modified": None, "comments": 0, "likes": 0, "liked": False, "tags": [],
	}


def test_tags_stay_on_the_row_as_well_as_in_the_meta(spaceview, stub_frappe):
	"""Two readers, one fetch.

	`_user_tags` is the Tags column's cell where somebody has added that column
	to the list, and a card's tags where nobody has. So it is read into the
	meta and *left* on the row under its own name, unlike `_comments` and
	`_liked_by`, which are consumed because only their counts are ever shown.
	"""
	stub_frappe.session.user = "someone@example.com"
	row = spaceview._with_meta({"name": "abc", "modified": None, "_user_tags": ",urgent,renewal"})

	assert row["_user_tags"] == ",urgent,renewal"
	assert row["_meta"]["tags"] == ["urgent", "renewal"]


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


def test_a_saved_view_belongs_to_the_view_type_it_was_made_in(spaceview, monkeypatch):
	"""Every write scoped by view type, the same way every read already was.

	`_layouts` filtered by view type from the day view types shipped. Nothing on
	the writing side did — so a screen offering a list and a board had *one*
	unnamed default between them, one default flag between them, and one reset
	button for both. Saving on the board rewrote the list's row with the board's
	columns and re-filed it, and the list quietly went back to the manifest's
	answer.

	What is checked here is that the type reaches the query, because that is the
	whole of the fix and the part that silently stops being true.
	"""
	asked = []
	monkeypatch.setattr(
		spaceview.frappe.db, "get_value",
		lambda doctype, filters=None, *a, **k: asked.append(filters) or None,
	)

	spaceview._saved("zz", "tasks", "board")
	assert asked[-1]["view_type"] == "board"

	# A row written before view types existed, or by a screen that only ever had
	# one, belongs to the list — and the list has to find it, or its own Save
	# starts writing a second row beside the one it should be updating.
	spaceview._saved("zz", "tasks", "list")
	assert asked[-1]["view_type"] == ["in", ["list", "", None]]
	spaceview._saved("zz", "tasks", None)
	assert asked[-1]["view_type"] == ["in", ["list", "", None]]

	# And the same rule where one default is made to unmake the others.
	seen = []
	monkeypatch.setattr(
		spaceview.frappe, "get_all",
		lambda doctype, filters=None, *a, **k: seen.append(filters) or [],
	)
	spaceview._only_default(
		types.SimpleNamespace(space_code="zz", screen="tasks", user="me@x",
		                      view_type="grid", name="one")
	)
	assert seen[-1]["view_type"] == "grid"


def test_the_view_type_filter_is_the_same_answer_reading_and_writing(spaceview):
	"""`_of_type` and `_layouts`' normalisation have to agree.

	They are the two halves of one rule — empty means the list — and if they
	drift, a save lands on a row the switcher does not show. Which is a bug with
	no error message: the view is there, in the table, invisible.
	"""
	assert spaceview._of_type("board") == "board"
	assert spaceview._of_type("") == ["in", ["list", "", None]]
	assert spaceview._of_type(None) == ["in", ["list", "", None]]

	# The reading half, on rows shaped the way the table holds them.
	rows = [{"view_type": ""}, {"view_type": None}, {"view_type": "board"}]
	for row in rows:
		row["view_type"] = row.get("view_type") or spaceview.DEFAULT_VIEW_TYPE
	assert [row["view_type"] for row in rows] == ["list", "list", "board"]


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


def test_only_one_layout_is_marked_as_the_one_that_opens(spaceview, monkeypatch, stub_spaceview):
	"""Two rows can both be `is_default`; only one of them opens the screen.

	One personal and one shared is a legitimate state, and a menu that pins
	both is telling the reader something untrue.
	"""
	rows = [layout("shared", "House", user="", is_default=1),
	        layout("mine", "Mine", is_default=1)]
	stub_spaceview("_layouts", lambda *a, **kw: rows)
	stub_spaceview("_can_share", lambda: False)
	resolved = spaceview._apply_saved({"space": "a", "screen": "v"})
	assert [l["opens"] for l in resolved["layouts"]] == [False, True]
	assert sum(l["is_default"] for l in resolved["layouts"]) == 2


class _Doc(dict):
	__getattr__ = dict.get

	def __setattr__(self, key, value):
		self[key] = value


def test_a_shared_layout_needs_the_workspaces_own_admin_rights(spaceview, stub_frappe, monkeypatch, stub_spaceview):
	stub_spaceview("_can_share", lambda: False)
	with pytest.raises(stub_frappe.PermissionError):
		spaceview._may_write(_Doc(user=""))
	stub_spaceview("_can_share", lambda: True)
	spaceview._may_write(_Doc(user=""))


def test_a_personal_layout_belongs_to_one_person(spaceview, stub_frappe, monkeypatch, stub_spaceview):
	stub_spaceview("_can_share", lambda: True)
	stub_frappe.session.user = "me@x"
	spaceview._may_write(_Doc(user="me@x"))
	# Even a workspace admin does not edit somebody else's private screen: sharing
	# rights are about the shared shelf, not about everyone's shelf.
	with pytest.raises(stub_frappe.PermissionError):
		spaceview._may_write(_Doc(user="someone@else"))


def test_a_shared_layout_still_only_reaches_what_the_screen_offers(spaceview, monkeypatch, stub_spaceview):
	"""Sharing does not widen a layout.

	The row is a doctype an operator could write directly, so what it carries is
	re-checked against the screen every time it is read — not only when it was
	saved through the endpoint.
	"""
	rows = [dict(layout("shared", "House", user="", is_default=1),
	             filters='[["_liked_by", "like", "%someone@else%"]]')]
	stub_spaceview("_layouts", lambda *a, **kw: rows)
	stub_spaceview("_can_share", lambda: True)
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


def test_a_saved_page_size_survives_and_a_junk_one_does_not(spaceview, monkeypatch, stub_spaceview):
	rows = [dict(layout("mine", "Mine", is_default=1), page_length=20)]
	stub_spaceview("_layouts", lambda *a, **kw: rows)
	stub_spaceview("_can_share", lambda: False)
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
	source = spaceview_source.source()
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

	# And on what each of them is nothing without. The sidebar is the SPA's
	# answer and the resolved screen is the server's; a type dropped by one and
	# kept by the other is a menu entry that opens the wrong body.
	for name in ("NEEDS_STATUS", "NEEDS_DATES", "NEEDS_SPANS", "NEEDS_PARENT",
	             "NEEDS_WIDGETS"):
		needs = set(
			_re.findall(r"'([\w]+)'", _re.search(
				rf"export const {name} = \[([^\]]*)\]", source
			).group(1))
		)
		assert needs == set(getattr(spaceview, name)), (
			f"lib/viewTypes.js {name} is {sorted(needs)}, spaceview has "
			f"{sorted(getattr(spaceview, name))}"
		)
		assert needs <= set(spaceview.VIEW_TYPES)


def test_a_screen_offers_what_it_declares_and_nothing_it_cannot_draw(spaceview):
	assert spaceview._view_types({"view_types": "list"}) == ["list"]
	# Unbuilt types are dropped rather than refused: a manifest naming one gets
	# a list today and the real thing the day it ships. `map` is the one still
	# unbuilt — the calendar shipped and is tested below.
	assert spaceview._view_types({"view_types": "list,map"}) == ["list"]
	assert spaceview._view_types({"view_types": "map"}) == ["list"]
	# Order is the manifest's, duplicates collapse, and nothing declared is
	# still a list.
	assert spaceview._view_types({"view_types": "list, list"}) == ["list"]
	assert spaceview._view_types({}) == ["list"]
	assert spaceview._view_types({"view_types": ""}) == ["list"]


def test_a_calendar_is_only_offered_where_there_is_a_date_to_place_it_by(spaceview):
	"""The same rule as the board's, one field over.

	A calendar is a way of reading one date. There is no screen-level date
	field to fall back to — `status_field` is on the screen because a badge
	reads it too, and nothing but the calendar reads this — so `view_settings`
	is the only declaration, the way the dashboard's widgets are.
	"""
	said = {
		"view_types": "list,calendar",
		"view_settings": '{"calendar": {"start_field": "starts_on"}}',
	}
	assert spaceview._view_types(said) == ["list", "calendar"]
	assert spaceview._view_types({**said, "view_settings": "{}"}) == ["list"]
	assert spaceview._view_types({"view_types": "calendar"}) == ["list"]
	# An end without a start is not a declaration: a span whose beginning
	# nothing knows is not a span.
	assert spaceview._view_types({
		"view_types": "calendar",
		"view_settings": '{"calendar": {"end_field": "ends_on"}}',
	}) == ["list"]


def test_a_calendar_reads_dates_and_refuses_everything_else(spaceview):
	"""Which pair of fields the grid places a record by.

	The fieldtype is checked here rather than at declaration time for the same
	reason the board's is: this is where the columns are. A start that is not a
	date drops the calendar; an end that is not one drops the span and keeps
	the calendar, because a record with a date on it is still a record with a
	date on it.
	"""
	columns = [
		{"fieldname": "starts_on", "label": "Starts on", "fieldtype": "Datetime"},
		{"fieldname": "ends_on", "label": "Ends on", "fieldtype": "Datetime"},
		{"fieldname": "due", "label": "Due", "fieldtype": "Date"},
		{"fieldname": "subject", "label": "Subject", "fieldtype": "Data"},
	]
	resolved = {
		"doctype": "Event",
		"all_columns": columns,
		"view_settings": {"calendar": {"start_field": "starts_on", "end_field": "ends_on"}},
	}
	found = spaceview._calendar(resolved)
	assert found["start_field"] == "starts_on"
	assert found["end_field"] == "ends_on"
	# Every date this screen has, so a picker needs no second question.
	assert [one["fieldname"] for one in found["fields"]] == ["starts_on", "ends_on", "due"]

	# A Data field is not a date, whoever typed it into the manifest.
	said = {**resolved, "view_settings": {"calendar": {"start_field": "subject"}}}
	assert spaceview._calendar(said)["start_field"] == ""

	# The end alone is dropped, and the calendar stands.
	said = {**resolved, "view_settings": {
		"calendar": {"start_field": "due", "end_field": "subject"},
	}}
	found = spaceview._calendar(said)
	assert found["start_field"] == "due"
	assert found["end_field"] == ""


def test_a_gantt_is_only_offered_where_both_ends_of_a_bar_are_named(spaceview):
	"""A bar needs a beginning and an end, and will take the calendar's.

	The fallback is the point: a screen offering both a calendar and a Gantt is
	placing its records by the same two dates, and a manifest made to say so
	twice is a manifest where the two quietly drift apart.
	"""
	pair = '{"calendar": {"start_field": "starts_on", "end_field": "ends_on"}}'
	assert spaceview._view_types({"view_types": "gantt", "view_settings": pair}) == ["gantt"]
	# Its own declaration wins where there is one.
	assert spaceview._view_types({
		"view_types": "gantt",
		"view_settings": '{"gantt": {"start_field": "from", "end_field": "to"}}',
	}) == ["gantt"]

	# A start alone is a calendar and not a chart.
	assert spaceview._view_types({
		"view_types": "calendar,gantt",
		"view_settings": '{"calendar": {"start_field": "starts_on"}}',
	}) == ["calendar"]
	assert spaceview._view_types({"view_types": "gantt"}) == ["list"]
	assert spaceview._view_types({"view_types": "gantt", "view_settings": "{}"}) == ["list"]


def test_a_gantt_reads_two_dates_and_a_measure_of_how_far_along(spaceview):
	"""Which pair of fields a bar is drawn between, and what fills it.

	Both ends are checked here rather than at declaration time, for the reason
	the calendar's are: this is where the columns are. Where the calendar keeps
	a start and drops a bad end, the Gantt drops both — half a span is not a
	shorter bar, it is no bar.
	"""
	columns = [
		{"fieldname": "starts_on", "label": "Starts on", "fieldtype": "Datetime"},
		{"fieldname": "ends_on", "label": "Ends on", "fieldtype": "Datetime"},
		{"fieldname": "done", "label": "Done", "fieldtype": "Percent"},
		{"fieldname": "subject", "label": "Subject", "fieldtype": "Data"},
	]
	resolved = {
		"doctype": "Event",
		"all_columns": columns,
		"view_settings": {
			"calendar": {"start_field": "starts_on", "end_field": "ends_on"},
			"gantt": {"progress_field": "done"},
		},
	}
	found = spaceview._gantt(resolved)
	assert (found["start_field"], found["end_field"]) == ("starts_on", "ends_on")
	assert found["progress_field"] == "done"
	assert [one["fieldname"] for one in found["fields"]] == ["starts_on", "ends_on"]

	# An end that is not a date takes the start with it.
	said = {**resolved, "view_settings": {
		"gantt": {"start_field": "starts_on", "end_field": "subject"},
	}}
	found = spaceview._gantt(said)
	assert (found["start_field"], found["end_field"]) == ("", "")

	# A progress field is a number or it is nothing, and it is nothing at all
	# without a span to fill.
	said = {**resolved, "view_settings": {
		"calendar": {"start_field": "starts_on", "end_field": "ends_on"},
		"gantt": {"progress_field": "subject"},
	}}
	assert spaceview._gantt(said)["progress_field"] == ""
	assert spaceview._gantt({**resolved, "view_settings": {
		"gantt": {"progress_field": "done"},
	}})["progress_field"] == ""


def test_a_tree_is_only_offered_where_a_screen_names_what_nests(spaceview):
	"""And this one is never inferred, which is where it parts from the desk.

	Frappe reads a nested set's own `parent_<doctype>` and has no answer for a
	doctype that is not one. Guessing "the Link that points at this doctype" is
	worse than asking, because a doctype can have several and only one of them
	is a hierarchy — see `_tree`, which is handed exactly that case.
	"""
	said = '{"tree": {"parent_field": "renews"}}'
	assert spaceview._view_types({"view_types": "list,tree", "view_settings": said}) \
		== ["list", "tree"]
	assert spaceview._view_types({"view_types": "tree"}) == ["list"]
	assert spaceview._view_types({"view_types": "tree", "view_settings": "{}"}) == ["list"]
	assert spaceview._view_types({
		"view_types": "tree", "view_settings": '{"tree": {"parent_field": "  "}}',
	}) == ["list"]


def test_a_tree_nests_by_a_link_to_its_own_doctype_and_nothing_else(spaceview):
	"""Which field points a record at the one above it.

	The board's check, one property over: a column field has to be a Select or
	a Link, and a parent field has to be a Link *at this doctype*. A Link to
	something else is a relation and not a hierarchy — nesting a licence under
	its issuer is a different picture with the same shape.
	"""
	columns = [
		{"fieldname": "renews", "label": "Renews", "fieldtype": "Link",
		 "options": "Compliance Document"},
		{"fieldname": "renewed_by", "label": "Renewed by", "fieldtype": "Link",
		 "options": "Compliance Document"},
		{"fieldname": "issued_by", "label": "Issued by", "fieldtype": "Link",
		 "options": "Supplier"},
		{"fieldname": "title", "label": "Title", "fieldtype": "Data", "options": None},
	]
	resolved = {
		"doctype": "Compliance Document",
		"all_columns": columns,
		"view_settings": {"tree": {"parent_field": "renews"}},
	}
	found = spaceview._tree(resolved)
	assert found["parent_field"] == "renews"
	# Both self-links are offered, and that is the whole argument for making the
	# manifest choose: this doctype has two and only one of them nests.
	assert [one["fieldname"] for one in found["fields"]] == ["renews", "renewed_by"]

	# A Link somewhere else is a relation, not a hierarchy.
	said = {**resolved, "view_settings": {"tree": {"parent_field": "issued_by"}}}
	assert spaceview._tree(said)["parent_field"] == ""

	# And a field that is not a Link at all, or is not a field at all.
	for name in ("title", "nonesuch", ""):
		said = {**resolved, "view_settings": {"tree": {"parent_field": name}}}
		assert spaceview._tree(said)["parent_field"] == ""

	# Nothing offered where the screen has no doctype: `options` matching a
	# missing name would make every Link a parent field.
	assert spaceview._tree({"all_columns": columns})["fields"] == []


def test_the_days_on_screen_are_a_filter_and_never_a_saved_one(spaceview):
	"""The visible range reaches the query, and only as a shape it recognises.

	A calendar is not a page: the desk asks for the range it is showing and
	ignores pagination, because a month drawn from whichever hundred rows
	sorted first has holes in it. The browser sends two dates and cannot name a
	column — the field is the screen's own, resolved before this is asked.
	"""
	resolved = {"doctype": "Event", "calendar": {"start_field": "starts_on"}}
	assert spaceview._window(resolved, "2026-09-01", "2026-09-30") == [
		["Event", "starts_on", "between", ["2026-09-01", "2026-09-30"]]
	]
	# Times are a date too — a week view asks for moments.
	assert spaceview._window(resolved, "2026-09-01 00:00:00", "2026-09-07 23:59:59")

	# Nothing at all where there is no calendar, no range, or half a range.
	assert spaceview._window({"doctype": "Event", "calendar": {}}, "2026-09-01", "2026-09-30") == []
	assert spaceview._window(resolved, "", "2026-09-30") == []
	assert spaceview._window(resolved, "2026-09-01", "") == []
	# And nothing for anything that is not a date. It has carried the string
	# "undefined" once, from a query parameter set to the value undefined.
	assert spaceview._window(resolved, "undefined", "undefined") == []
	assert spaceview._window(resolved, "2026-09-01", "next Tuesday") == []
	assert spaceview._window(resolved, ["2026-09-01"], "2026-09-30") == []


def test_a_board_is_only_offered_where_there_is_a_status_to_column_it_by(spaceview):
	"""A board is columns of one field, so a screen naming no status has none.

	Dropped rather than refused, like an unbuilt type: the alternative is a
	board of a single column called "everything", which is a list drawn badly.
	The manifest check catches declaring one anyway; this is what stops it
	rendering when it slips through.
	"""
	board = {"view_types": "list,board", "status_field": "status"}
	assert spaceview._view_types(board) == ["list", "board"]
	assert spaceview._view_types({**board, "status_field": ""}) == ["list"]
	assert spaceview._view_types({**board, "status_field": "   "}) == ["list"]
	# The whole declaration, so a screen that offers only a board still opens.
	assert spaceview._view_types({"view_types": "board"}) == ["list"]
	assert spaceview._view_types({"view_types": "board", "status_field": "status"}) == [
		"board"
	]

	# Or the screen's own settings name the field instead, which is what a
	# doctype with no status but an obvious grouping field wants.
	by_settings = {
		"view_types": "board",
		"view_settings": '{"board": {"column_field": "priority"}}',
	}
	assert spaceview._view_types(by_settings) == ["board"]
	# Settings that name no field are not a declaration.
	assert spaceview._view_types({
		"view_types": "board", "view_settings": '{"board": {"card_fields": ["x"]}}',
	}) == ["list"]
	assert spaceview._view_types({
		"view_types": "board", "view_settings": "not json",
	}) == ["list"]


def test_a_view_settings_fieldname_is_checked_like_any_other(spaceview):
	"""A board's column field is a fieldname that reaches a query.

	"It came from the settings blob" is not a reason to trust one, so every
	value ending in `_field` is checked against the screen's own columns the
	same way a filter or a sort is — and `_fields` is the same check over a
	list.
	"""
	resolved = {"all_columns": spaceview._columns(TODO, ["status", "description"])}
	settings = {"board": {"column_field": "status"}}
	assert spaceview._view_settings(resolved, settings) == settings

	# Not a column here, so not a setting.
	assert spaceview._view_settings(resolved, {"board": {"column_field": "owner"}}) == {}
	# Not a fieldname at all, so not carried.
	assert spaceview._view_settings(resolved, {"board": {"colour": "red"}}) == {}
	# Not a view type, so there is nothing it could be settings for.
	assert spaceview._view_settings(resolved, {"kanban": {"column_field": "status"}}) == {}
	assert spaceview._view_settings(resolved, "not json at all") == {}

	# A list of fieldnames, filtered rather than refused: a card that names one
	# field the screen dropped should lose that field, not all of them.
	kept = spaceview._view_settings(
		resolved, {"board": {"card_fields": ["status", "owner", "description"]}}
	)
	assert kept == {"board": {"card_fields": ["status", "description"]}}
	# And capped, because a card is a glance.
	many = ["status", "description"] * 10
	assert len(
		spaceview._view_settings(resolved, {"board": {"card_fields": many}})
		["board"]["card_fields"]
	) <= spaceview.MAX_CARD_FIELDS


def test_a_board_falls_back_to_the_status_field_and_refuses_the_unboardable(spaceview):
	"""Columns of a Select or a Link, and of nothing else.

	`_view_settings` checks the name is a column this screen offers. What it
	cannot check is that a board can be *made* of it — that is a question about
	the fieldtype — so a settings blob naming the description field falls back
	to the status field rather than drawing a column per sentence.
	"""
	# Its own doctype rather than the shared one: the question needs a Link
	# field, and adding one to `TODO` would change what every other test in this
	# file counts.
	boardable = meta([
		field("description", "Small Text", "Description"),
		field("status", "Select", "Status", options="Open\nClosed"),
		field("date", "Date", "Due Date"),
		field("allocated_to", "Link", "Assigned To", options="User"),
	])
	resolved = {
		"all_columns": spaceview._columns(
			boardable, ["status", "description", "date", "allocated_to"]
		),
		"status_field": "status",
	}

	assert spaceview._board(resolved)["column_field"] == "status"

	resolved["view_settings"] = {"board": {"column_field": "allocated_to"}}
	assert spaceview._board(resolved)["column_field"] == "allocated_to", (
		"a Link is boardable — 'by assignee' is the board people ask for next"
	)

	# A Text and a Date are not: one is a column per sentence, the other wants a
	# calendar.
	for unboardable in ("description", "date"):
		resolved["view_settings"] = {"board": {"column_field": unboardable}}
		assert spaceview._board(resolved)["column_field"] == "status"

	# And with nothing to fall back to, there is no board at all.
	resolved["status_field"] = ""
	resolved["view_settings"] = {"board": {"column_field": "description"}}
	assert spaceview._board(resolved)["column_field"] == ""

	# What the picker offers is every field a board could be made of.
	offered = {f["fieldname"] for f in spaceview._board(resolved)["fields"]}
	assert offered == {"status", "allocated_to"}


def test_a_card_is_the_same_card_on_a_board_and_on_a_grid(spaceview):
	"""Which fields a card carries, per card-shaped view type.

	A board card and a grid card are the same card drawn twice — the difference
	between the two views is arrangement, which a card knows nothing about — so
	the fields are resolved by one function. What is *not* shared is the answer:
	each view type keeps its own list, because a board card sits under a heading
	naming the field it is bucketed by and a grid card does not.
	"""
	resolved = {
		"view_type": "board",
		"all_columns": spaceview._columns(TODO, ["status", "description"]),
		"view_settings": {
			"board": {"card_fields": ["status"]},
			"grid": {"card_fields": ["description"]},
		},
	}
	assert spaceview._cards(resolved)["card_fields"] == ["status"]

	resolved["view_type"] = "grid"
	assert spaceview._cards(resolved)["card_fields"] == ["description"]

	# A list has no cards, whatever the settings say about the other two.
	resolved["view_type"] = "list"
	assert spaceview._cards(resolved)["card_fields"] == []

	# Empty is not "nothing": it is "the browser decides", from the columns the
	# reader is already looking at.
	resolved["view_type"] = "board"
	resolved["view_settings"] = {}
	assert spaceview._cards(resolved)["card_fields"] == []


def test_what_a_record_is_is_always_fetched(spaceview):
	"""The title and the picture, whether or not anybody made them columns.

	Both are the doctype's own answer to "what is one of these" — `title_field`
	and `image_field` — and every surface draws them: the title cell, the chip
	over a link, the card, the gallery. None of them is a column unless a
	manifest happened to list one, and the failure is quiet in the worst way: a
	doctype whose title field is also a column looks perfectly correct, so the
	screens that were showing a page of ids were the ones nobody had opened.
	"""
	resolved = {
		"view_type": "list",
		"status_field": "",
		"title_field": "full_name",
		"image_field": "image",
		"all_columns": spaceview._columns(CONTACT, ["first_name", "company"]),
		"columns": spaceview._columns(CONTACT, ["first_name", "company"]),
		"view_settings": {},
	}
	spaceview._resolve_views(resolved)

	assert "full_name" in resolved["fields"]
	assert "image" in resolved["fields"]

	# A doctype with no picture asks for nothing extra — there is no column
	# called "" and asking for one is a SQL error rather than an empty frame.
	resolved["image_field"] = None
	spaceview._resolve_views(resolved)
	assert "" not in resolved["fields"]
	assert None not in resolved["fields"]


def test_a_card_field_is_fetched_even_where_nobody_looks_at_that_column(spaceview):
	"""Choosing a card field has to reach the query, or the card renders blank.

	The failure this pins is the quiet one: a reader picks a field that is not
	one of their columns, everything about the pick is stored and validated
	correctly, the row comes back without that field on it, and the card drops
	it as empty — in exactly the case somebody went to the trouble of choosing.
	"""
	resolved = {
		"view_type": "grid",
		"status_field": "",
		"all_columns": spaceview._columns(TODO, ["status", "description", "priority"]),
		"columns": spaceview._columns(TODO, ["description"]),
		"view_settings": {"grid": {"card_fields": ["priority"]}},
	}
	spaceview._resolve_views(resolved)
	assert "priority" in resolved["fields"]

	# A child table is a column somebody may choose and not a field the database
	# has, so asking for one by name is a SQL error rather than an empty card.
	table = meta([
		field("description", "Small Text", "Description"),
		field("items", "Table", "Items", options="ToDo"),
	])
	resolved = {
		"view_type": "grid",
		"status_field": "",
		"all_columns": spaceview._columns(table, ["description", "items"]),
		"columns": spaceview._columns(table, ["description"]),
		"view_settings": {"grid": {"card_fields": ["items"]}},
	}
	spaceview._resolve_views(resolved)
	assert "items" not in resolved["fields"]


def test_a_colleague_is_somebody_holding_a_role_we_granted(spaceview, monkeypatch):
	"""Not `user_type`, which on this product means "the Administrator".

	Frappe's own assignment dialog asks for System Users, and copying it was the
	bug: our roles are created with `desk_access` off — that is what keeps a
	workspace out of the desk — and Frappe recomputes `user_type` from exactly
	that flag, so every member of every workspace is a Website User. The picker
	offered the site admin and nobody else, on every real workspace, for as long
	as assignment existed.
	"""
	asked = []

	def get_all(doctype, filters=None, pluck=None, **kw):
		asked.append((doctype, filters))
		if doctype == "Has Role":
			return ["ada@example.com", "bo@example.com"]
		return []

	monkeypatch.setattr(spaceview.frappe, "get_all", get_all)
	monkeypatch.setattr(
		spaceview.frappe, "get_cached_value", lambda *a, **k: None, raising=False
	)

	import sys
	import types as _types

	# `_granted_roles` reads the roles this app made on the site. Stubbed to two
	# of them, because what is under test is the question being asked and not
	# how the site answers it.
	sync = _types.ModuleType("oneapp.oneapp_core.sync")
	sync._granted_roles = lambda: {"MockSpace Member", "MockSpace Owner"}
	monkeypatch.setitem(sys.modules, "oneapp.oneapp_core.sync", sync)

	who = spaceview._colleagues()

	assert who == ["Administrator", "ada@example.com", "bo@example.com"]
	# The Administrator holds none of our roles and is added back: it is the
	# account that sets a workspace up and the one support arrives as.
	assert "Administrator" in who
	# And the question asked was about roles, not about a user type.
	doctypes = [one[0] for one in asked]
	assert "Has Role" in doctypes
	assert not any(
		isinstance(one[1], dict) and "user_type" in one[1] for one in asked
	), "the desk's own filter is the thing this replaced"


def test_who_a_page_is_assigned_to_is_one_lookup(spaceview, monkeypatch):
	"""`_assign` on every row of a page, resolved into faces, in one query.

	Assignment is the one thing on a row that no field carries and that people
	look for first, so it comes back with the rows. The naive way to do that is
	one lookup per row, and the ids repeat on almost every one of them — the
	same reason `_with_links` resolves a whole column at a time.
	"""
	asked = []

	def get_all(doctype, filters=None, **kw):
		asked.append((doctype, filters))
		return [
			{"name": "ada@example.com", "full_name": "Ada Lovelace", "user_image": "/a.png"},
			# No full name, which is a real state: the id is what is left to
			# call somebody, and a blank label is a face with no name under it.
			{"name": "bo@example.com", "full_name": "", "user_image": None},
		]

	monkeypatch.setattr(spaceview.frappe, "get_all", get_all)

	rows = [
		{"name": "one", "_assign": '["ada@example.com", "bo@example.com"]'},
		{"name": "two", "_assign": '["ada@example.com"]'},
		{"name": "three", "_assign": None},
		{"name": "four", "_assign": '["gone@example.com"]'},
		# Not JSON, and not a reason to fail a whole page.
		{"name": "five", "_assign": "administrator"},
	]
	spaceview._with_people(rows)

	assert len(asked) == 1, "a page of rows is one lookup, not one per row"
	assert asked[0][0] == "User"
	assert sorted(asked[0][1]["name"][1]) == [
		"ada@example.com", "bo@example.com", "gone@example.com"
	]

	# A name, a face and the id underneath — the same three every other
	# identity here is drawn from — in the order the document holds them.
	assert [one["label"] for one in rows[0]["_assigned"]] == ["Ada Lovelace", "bo@example.com"]
	assert rows[0]["_assigned"][0]["image"] == "/a.png"
	assert rows[1]["_assigned"] == [rows[0]["_assigned"][0]]
	assert rows[2]["_assigned"] == []
	# A user who no longer exists drops out rather than rendering as a blank
	# face: `_assign` is not a foreign key and Frappe does not clean it up.
	assert rows[3]["_assigned"] == []
	assert rows[4]["_assigned"] == []

	# And the raw column does not reach the browser — what it holds is ids.
	assert all("_assign" not in row for row in rows)


def test_nobody_assigned_anywhere_asks_nothing(spaceview, monkeypatch):
	"""The lookup is skipped, not run with an empty list.

	`name in ()` is a query that returns nothing and still costs a round trip,
	once per page, on every screen of every space that does not use assignment.
	"""
	asked = []
	monkeypatch.setattr(
		spaceview.frappe, "get_all", lambda *a, **k: asked.append(a) or []
	)

	rows = [{"name": "one", "_assign": "[]"}, {"name": "two"}]
	spaceview._with_people(rows)

	assert not asked
	assert [row["_assigned"] for row in rows] == [[], []]


# --------------------------------------------------------------------------- #
# A link is a record
#
# The server resolves a Link's ids into something a person recognises — a face,
# a name, and the id underneath — so a cell and a picker row are the same
# rendering of the same thing. What is pinned here is the shape of that row and
# the bounds around producing it.
# --------------------------------------------------------------------------- #

CONTACT = meta(
	[field("first_name"), field("email_id"), field("company")],
	title_field="full_name",
	image_field="image",
	search_fields="email_id,company",
)


def test_a_link_row_is_a_face_a_name_and_an_id(spaceview):
	shape = spaceview._link_shape(CONTACT)
	row = spaceview._link_row(
		{"name": "CT-0001", "full_name": "Chris Halloway",
		 "image": "/files/chris.png", "email_id": "chris@halloway.test"},
		shape,
	)
	assert row["value"] == "CT-0001"
	assert row["label"] == "Chris Halloway"
	assert row["id"] == "CT-0001"
	assert row["image"] == "/files/chris.png"
	# The doctype's own search fields, which is what tells two people called
	# Chris apart.
	assert row["description"] == "chris@halloway.test"


def test_a_doctype_with_no_title_shows_its_id_once(spaceview):
	"""Most doctypes have no `title_field`, and repeating the id underneath
	itself is noise in every row of the menu."""
	plain = meta([field("subject")])
	row = spaceview._link_row({"name": "TASK-01"}, spaceview._link_shape(plain))
	assert row["label"] == "TASK-01"
	assert row["id"] is None


def test_a_record_named_after_its_own_title_says_it_once(spaceview):
	"""Frappe's User is the case: `full_name` is the title, `full_name` is the
	only search field, and the Administrator is named "Administrator". Three
	truthful lookups, one word, and a row reading it three times."""
	user = meta([field("full_name")], title_field="full_name",
	            search_fields="full_name")
	row = spaceview._link_row(
		{"name": "Administrator", "full_name": "Administrator"},
		spaceview._link_shape(user),
	)
	assert row["label"] == "Administrator"
	assert row["id"] is None
	assert row["description"] is None


def test_a_search_matches_the_id_the_title_and_the_doctypes_own_fields(spaceview):
	clauses = spaceview._search(CONTACT, "hall", spaceview._link_shape(CONTACT))
	assert ["name", "like", "%hall%"] in clauses
	assert ["full_name", "like", "%hall%"] in clauses
	assert ["email_id", "like", "%hall%"] in clauses
	# One clause per field, however many lists a fieldname appears on.
	assert len(clauses) == len({tuple(c) for c in clauses})


def test_a_picker_is_refused_for_a_field_the_screen_does_not_have(spaceview):
	"""The same allowlist the rows go through: a fieldname is a string somebody
	sent, and a picker over an ungranted field is a read of it."""
	import frappe

	resolved = {"all_columns": spaceview._columns(TODO, ["description", "status"])}
	with pytest.raises(frappe.PermissionError):
		spaceview._link_column(resolved, "owner")


def test_a_picker_is_offered_for_a_field_the_record_shows_but_the_list_does_not(spaceview):
	"""Hiding a column says nothing about whether the record has the field, and
	the record dialog renders the doctype's whole field list."""
	resolved = {
		"columns": spaceview._columns(TODO, ["description"]),
		"all_columns": spaceview._columns(TODO, ["description", "status"]),
	}
	assert spaceview._link_column(resolved, "status")["fieldname"] == "status"


def test_a_dynamic_link_has_no_target_to_offer(spaceview):
	"""It names another field that holds the answer, which only a record has —
	so it is refused rather than guessed at."""
	assert spaceview._link_target({}, {"fieldtype": "Link", "options": "User"}) == "User"
	assert spaceview._link_target({}, {"fieldtype": "Dynamic Link", "options": "ref_dt"}) is None


# --------------------------------------------------------------------------- #
# Creating one from the picker
# --------------------------------------------------------------------------- #

def test_quick_entry_asks_for_what_the_doctype_marks_and_what_it_insists_on(spaceview):
	assert spaceview._quick_entry(field("subject", reqd=1)) is True
	assert spaceview._quick_entry(field("notes", allow_in_quick_entry=1)) is True
	assert spaceview._quick_entry(field("notes")) is False


def test_quick_entry_never_offers_what_cannot_be_written(spaceview):
	"""A read-only or hidden field is neither, whatever the flags say — and
	Frappe's own bookkeeping is never on a form of ours."""
	assert spaceview._quick_entry(field("subject", reqd=1, read_only=1)) is False
	assert spaceview._quick_entry(field("subject", reqd=1, hidden=1)) is False
	assert spaceview._quick_entry(field("owner", reqd=1)) is False
	assert spaceview._quick_entry(field("sec", "Section Break", reqd=1)) is False


# --------------------------------------------------------------------------- #
# What the doctype already says about a field
#
# Frappe's DocField carries more than a type and a label, and every flag we
# honour is one nobody has to repeat in a manifest — set once on the doctype,
# respected on every screen pointing at it.
# --------------------------------------------------------------------------- #

SHAPED = meta([
	field("description", "Small Text", "Description", columns=4),
	field("priority", "Select", "Priority", options="High\nLow", bold=1),
	field("spent", "Duration", "Time Spent", hide_days=1, hide_seconds=1),
	field("company", "Link", "Company", options="Company", set_only_once=1),
	field("company_name", "Data", "Company Name", fetch_from="company.name"),
])


def test_a_column_carries_the_doctypes_own_presentation_flags(spaceview):
	by_name = {c["fieldname"]: c for c in spaceview._columns(SHAPED, [
		"description", "priority", "spent", "company", "company_name",
	])}
	assert by_name["priority"]["bold"] == 1
	assert by_name["description"]["columns"] == 4
	assert by_name["spent"]["hide_days"] == 1
	assert by_name["spent"]["hide_seconds"] == 1
	assert by_name["company"]["set_only_once"] == 1
	assert by_name["company_name"]["fetch_from"] == "company.name"


def test_a_doctype_that_says_how_wide_a_column_wants_to_be_is_believed(spaceview):
	"""`columns` on a DocField is what Frappe's own list lays out with. A
	default rather than a ceiling, like the field list itself — the picker still
	has a width box and a saved layout still wins."""
	wide, plain = spaceview._columns(SHAPED, ["description", "priority"])
	assert spaceview._default_width(wide) == 4 * spaceview.UNIT_WIDTH
	# Nothing declared, so the cell kind decides: a badge is a badge.
	assert spaceview._default_width(plain) == 128


def test_a_declared_width_is_clamped_like_any_other(spaceview):
	"""It reaches a CSS grid track, and a doctype asking for twenty units is
	asking the layout to do something silly rather than asking for a wide
	column."""
	assert spaceview._default_width({"columns": 40}) == spaceview.MAX_WIDTH


# --------------------------------------------------------------------------- #
# A record is a link
#
# It is in the URL, so it is arrived at by id rather than found on a page —
# from a bookmark, a reload, or somebody else's message. What that changes is
# which fields come back and which filters decide.
# --------------------------------------------------------------------------- #

def test_a_record_carries_every_field_it_shows_not_the_listed_columns(spaceview):
	"""The dialog renders the doctype's whole field list. It used to seed itself
	from the list row, so a field nobody put on the list opened blank on a
	record that has a value for it."""
	source = spaceview_source.source()
	body = source.split("def record(", 1)[1].split("\n@frappe.whitelist", 1)[0]
	assert "all_columns" in body, "record() must fetch what the record shows"
	assert 'resolved["fields"]' not in body, (
		"record() must not fetch the list's own field set — that is the columns "
		"somebody chose to see, not the fields the record has"
	)


def test_a_record_is_bounded_by_the_screen_and_not_by_a_saved_view(spaceview):
	"""You can arrive at a record from one view and open it under another, and
	a personal filter is not a rule about what exists. The screen's own filters
	still are."""
	source = spaceview_source.source()
	body = source.split("def record(", 1)[1].split("\n@frappe.whitelist", 1)[0]
	assert "_apply_saved" not in body
	assert "_all_filters(resolved, [])" in body


# --------------------------------------------------------------------------- #
# A view's icon
#
# It reaches the DOM as a class name, and Tailwind only emits CSS for names it
# saw in the source — so "any lucide icon" is a picker whose choices mostly
# render as nothing. One curated set, plus emoji, which need no build step.
# --------------------------------------------------------------------------- #

def test_an_offered_icon_is_kept(spaceview):
	assert spaceview._view_icon("lucide-calendar") == "lucide-calendar"
	assert spaceview._view_icon("  lucide-calendar  ") == "lucide-calendar"


def test_an_emoji_is_kept_because_an_emoji_needs_no_build(spaceview):
	"""The escape hatch that actually works: an emoji is text, so any of them
	renders. Frappe CRM tolerates one here for legacy reasons; for us it is the
	more capable of the two."""
	assert spaceview._view_icon("📦") == "📦"
	# One emoji, several code points: a flag is two and a family joined by
	# zero-width joiners is seven. A bound of one or two would reject the ones
	# people actually use.
	assert spaceview._view_icon("🇬🇧") == "🇬🇧"
	assert spaceview._view_icon("👩\u200d👩\u200d👧\u200d👦") == "👩\u200d👩\u200d👧\u200d👦"


def test_a_lucide_name_nobody_offered_is_dropped(spaceview):
	"""It would render as nothing at all — the CSS for it was never emitted —
	and a picker that stores a name the page cannot draw is a picker that
	silently does nothing."""
	assert spaceview._view_icon("lucide-rocket") == ""
	assert spaceview._view_icon("") == ""
	assert spaceview._view_icon(None) == ""


def test_anything_that_could_be_a_class_name_is_dropped(spaceview):
	"""A lucide value becomes a class on an element. Checked rather than
	trusted — and the emoji rule is frappe-ui's own, so what is stored is what
	its `Icon` will actually draw."""
	assert spaceview._view_icon("bg-red-500 absolute inset-0") == ""
	assert spaceview._view_icon("a") == ""
	assert spaceview._view_icon("📦 📦") == ""
	# Short, but not a name for anything.
	assert spaceview._view_icon("📦📦📦📦📦📦📦📦📦") == ""


def test_the_icon_set_is_the_one_the_spa_can_draw(spaceview):
	"""Two lists, one answer. The SPA's is what Tailwind sees and therefore what
	exists as CSS; the server's is what a save is checked against. A name in one
	and not the other is either an icon nobody can pick or a stored icon that
	renders as a blank square."""
	import re as _re

	icons = SPACEVIEW.parents[2] / "frontend/src/lib/icons.js"
	source = icons.read_text()
	block = _re.search(r"export const SPACE_ICONS = \[(.*?)\]", source, _re.S).group(1)
	assert tuple(_re.findall(r"'([^']+)'", block)) == spaceview.VIEW_ICONS


# --------------------------------------------------------------------------- #
# Hiding a shared view
#
# A shared view has one row and many readers, so "I do not want this in my
# menu" cannot be a change to the row. It is a row of the reader's own, and
# hiding is never offered as deleting: somebody else may be living in it.
# --------------------------------------------------------------------------- #

def test_a_screen_says_how_many_views_are_hidden_so_they_can_come_back(spaceview, monkeypatch, stub_spaceview):
	"""A hidden view is not in the menu, which is the wrong place to pick one
	out of — so the menu offers all of them back at once, and needs to know
	there are any."""
	rows = [dict(layout("shared", "House", user=""), hidden=True),
	        dict(layout("mine", "Mine"), hidden=False)]
	stub_spaceview("_layouts", lambda *a, **kw: rows)
	stub_spaceview("_can_share", lambda: False)

	resolved = spaceview._apply_saved({"space": "a", "screen": "v"})
	assert resolved["hidden"] == 1
	assert [row["name"] for row in resolved["layouts"]] == ["mine"]


def test_hiding_your_own_view_is_refused(spaceview, monkeypatch):
	"""You made it. Deleting is what you want, and it is offered — hiding a row
	nobody else can see would be a way to lose a view without meaning to."""
	import frappe

	doc = types.SimpleNamespace(space_code="a", screen="v", user="me@x", name="mine")
	monkeypatch.setattr(frappe, "get_doc", lambda *a, **kw: doc)
	with pytest.raises(Exception, match="delete it rather than hiding"):
		spaceview.hide_layout("a", "v", "mine")


def test_hiding_a_view_from_another_screen_is_refused(spaceview, monkeypatch):
	import frappe

	doc = types.SimpleNamespace(space_code="a", screen="elsewhere", user="", name="shared")
	monkeypatch.setattr(frappe, "get_doc", lambda *a, **kw: doc)
	with pytest.raises(Exception, match="different screen"):
		spaceview.hide_layout("a", "v", "shared")


def test_deleting_a_view_stops_anybody_hiding_it(spaceview):
	"""A hidden row pointing at nothing would be counted as a view waiting to
	come back, and bringing it back would produce nothing."""
	source = spaceview_source.source()
	body = source.split("def delete_layout(", 1)[1].split("\n@frappe.whitelist", 1)[0]
	assert 'frappe.db.delete("OneSpace Hidden View"' in body


# --------------------------------------------------------------------------- #
# The status field
#
# The manifest names which field says where a record stands; the doctype owns
# what colour that is. A fieldname reaching a badge is a fieldname somebody
# typed, so it is checked like a filter or a sort.
# --------------------------------------------------------------------------- #

def test_the_status_field_has_to_be_a_field_this_screen_offers(spaceview):
	offered = {c["fieldname"]: c for c in spaceview._columns(TODO, ["description", "status"])}
	assert spaceview._status_field({"status_field": "status"}, offered) == "status"
	assert spaceview._status_field({"status_field": "invented"}, offered) == ""
	assert spaceview._status_field({"status_field": " status "}, offered) == "status"


def test_a_screen_that_names_no_status_badges_nothing(spaceview):
	"""Most screens. A record with no status is a record with no badge rather
	than one with an empty badge."""
	offered = {c["fieldname"]: c for c in spaceview._columns(TODO, ["description"])}
	assert spaceview._status_field({}, offered) == ""
	assert spaceview._status_field({"status_field": ""}, offered) == ""


def test_the_manifest_never_carries_the_colours(spaceview):
	"""They are the doctype's own Document States, which `presentation` already
	reads — so a status is one colour in the list, in the badge and in the desk
	rather than three."""
	source = spaceview_source.source()
	body = source.split("def _status_field(", 1)[1].split("\ndef ", 1)[0]
	assert "color" not in body and "theme" not in body


# --------------------------------------------------------------------------- #
# The record form
#
# Frappe's desk lays a form out from `Tab Break` and `Section Break` in the
# field list. A record here reads the same two, so a doctype whose author
# grouped its fields is grouped the same way without a manifest repeating it.
# --------------------------------------------------------------------------- #

def _offered(spaceview, meta, names):
	"""Every field the record shows, editable or not — which is what the form
	is laid out over. A Color is shown and never offered, and leaving it out
	here would take it off the record rather than leaving it read-only."""
	return {c["fieldname"]: c for c in spaceview._columns(meta, names)}


def test_a_doctype_that_groups_nothing_gets_one_tab(spaceview):
	offered = _offered(spaceview, TODO, ["description", "status"])
	form = spaceview._form(TODO, offered)
	assert [tab["label"] for tab in form] == ["Details"]
	assert form[0]["sections"][0]["columns"] == [["description", "status"]]


def test_a_section_break_starts_a_section(spaceview):
	"""ToDo's fixture has one — `sec_more` — and the fields after it belong to
	it rather than to the run above."""
	offered = _offered(spaceview, TODO, ["description", "status", "date"])
	form = spaceview._form(TODO, offered)
	labels = [section["label"] for section in form[0]["sections"]]
	assert labels[0] == ""


def test_a_tab_break_starts_a_tab(spaceview):
	tabbed = meta([
		field("subject"),
		field("tab_two", "Tab Break", "Extras"),
		field("note", "Small Text", "Note"),
	])
	form = spaceview._form(tabbed, _offered(spaceview, tabbed, ["subject", "note"]))
	assert [tab["label"] for tab in form] == ["Details", "Extras"]
	assert form[1]["sections"][0]["columns"] == [["note"]]


def test_layout_with_nothing_in_it_is_not_layout(spaceview):
	"""A tab break before fields this screen does not offer — a permlevel this
	person cannot read, a field the site does not have — leaves a tab nobody
	can open, and an empty section leaves a heading over nothing."""
	tabbed = meta([
		field("subject"),
		field("tab_two", "Tab Break", "Extras"),
		field("secret", "Data", "Secret", permlevel=1),
	])
	form = spaceview._form(tabbed, _offered(spaceview, tabbed, ["subject"]))
	assert [tab["label"] for tab in form] == ["Details"]


def test_a_field_shown_but_never_offered_is_still_on_the_form(spaceview):
	"""Colour, signature, geolocation. The control renders them read-only —
	dropping them here would take them off the record instead."""
	form = spaceview._form(TODO, _offered(spaceview, TODO, ["description", "colour"]))
	names = [
		name
		for tab in form
		for section in tab["sections"]
		for column in section["columns"]
		for name in column
	]
	assert "colour" in names


def test_the_form_carries_fieldnames_and_not_the_columns_again(spaceview):
	"""The spec already sends every column once. A form that repeated them
	would send a sixty-field doctype twice."""
	form = spaceview._form(TODO, _offered(spaceview, TODO, ["description"]))
	assert form[0]["sections"][0]["columns"] == [["description"]]


# --------------------------------------------------------------------------- #
# Attachments
#
# Frappe's own File rows, which is what the desk's sidebar lists and what an
# Attach field points at — so a file uploaded through a field and a file
# dropped on the record are one list rather than two.
# --------------------------------------------------------------------------- #

def test_reading_the_record_is_what_lets_you_see_its_files(spaceview):
	"""What is filed against a record is no less private than the record."""
	source = spaceview_source.source()
	body = source.split("def _attachable(", 1)[1].split("\n@frappe.whitelist", 1)[0]
	assert 'check_permission("read")' in body


def test_removing_a_file_needs_the_record_to_be_writable(spaceview):
	"""Removing what is filed against something is a change to it, even though
	the row being deleted is a File."""
	source = spaceview_source.source()
	body = source.split("def remove_attachment(", 1)[1].split("\n@frappe.whitelist", 1)[0]
	assert 'check_permission("write")' in body


def test_a_file_from_another_record_is_refused(spaceview):
	"""A File name arriving in the payload is a File name somebody sent. It has
	to be attached to *this* record, and the check is against the row rather
	than against what was asked for."""
	source = spaceview_source.source()
	body = source.split("def remove_attachment(", 1)[1].split("\n@frappe.whitelist", 1)[0]
	assert "attached_to_doctype" in body and "not on this record" in body


# --------------------------------------------------------------------------- #
# Field-level permissions
#
# Frappe protects a field twice by level: one list of levels you may read,
# another of levels you may write. Reading only the first is the worst of the
# three possible answers — the control looks editable and the save drops it.
# --------------------------------------------------------------------------- #

def test_a_level_you_can_read_and_not_write_is_not_editable(spaceview):
	guarded = meta(
		[field("subject"), field("cost", "Currency", "Cost", permlevel=1)],
		permlevels=[0, 1],
		write_levels=[0],
	)
	columns = {c["fieldname"]: c for c in spaceview._columns(guarded, ["subject", "cost"])}
	assert columns["subject"]["editable"] is True
	# Shown — it is readable — and never offered.
	assert columns["cost"]["editable"] is False
	assert columns["cost"]["permlevel"] == 1


def test_a_level_you_can_write_stays_editable(spaceview):
	guarded = meta(
		[field("cost", "Currency", "Cost", permlevel=1)],
		permlevels=[0, 1],
		write_levels=[0, 1],
	)
	assert spaceview._columns(guarded, ["cost"])[0]["editable"] is True


def test_a_save_cannot_reach_a_level_this_person_may_not_write(spaceview):
	"""`_writable` reads the same flag the control does, so the two cannot
	disagree — and the server is where it counts."""
	guarded = meta(
		[field("subject"), field("cost", "Currency", "Cost", permlevel=1)],
		permlevels=[0, 1],
		write_levels=[0],
	)
	resolved = {"all_columns": spaceview._columns(guarded, ["subject", "cost"])}
	assert spaceview._writable(resolved) == {"subject"}


def test_a_column_break_splits_a_section(spaceview):
	"""Frappe's third layout field, and the one this used to drop — a doctype
	whose author put four fields in two columns got one tall column of four."""
	split = meta([
		field("first"),
		field("second"),
		field("cb", "Column Break"),
		field("third"),
	])
	form = spaceview._form(split, _offered(spaceview, split, ["first", "second", "third"]))
	assert form[0]["sections"][0]["columns"] == [["first", "second"], ["third"]]


def test_an_empty_column_is_not_a_column(spaceview):
	"""A trailing column break, or one whose fields this screen does not offer,
	would otherwise draw a gap the width of the fields that are not there."""
	split = meta([
		field("first"),
		field("cb", "Column Break"),
		field("secret", "Data", "Secret", permlevel=1),
	])
	form = spaceview._form(split, _offered(spaceview, split, ["first"]))
	assert form[0]["sections"][0]["columns"] == [["first"]]


def test_the_doctypes_own_rules_travel_with_the_field(spaceview):
	"""`depends_on` and its two cousins are what make a Frappe form feel like a
	form. The screen carries them; the SPA reads them against the record."""
	ruled = meta([
		field("status", "Select", "Status", options="Open\nClosed"),
		field("closed_on", "Date", "Closed On",
		      depends_on='eval:doc.status=="Closed"',
		      mandatory_depends_on='eval:doc.status=="Closed"',
		      read_only_depends_on="eval:doc.status=='Open'"),
	])
	column = spaceview._columns(ruled, ["closed_on"])[0]
	assert column["depends_on"] == 'eval:doc.status=="Closed"'
	assert column["mandatory_depends_on"] == 'eval:doc.status=="Closed"'
	assert column["read_only_depends_on"] == "eval:doc.status=='Open'"


def test_a_field_with_no_rules_carries_none(spaceview):
	column = spaceview._columns(TODO, ["description"])[0]
	assert column["depends_on"] is None
	assert column["mandatory_depends_on"] is None
	assert column["read_only_depends_on"] is None


# --------------------------------------------------------------------------- #
# Dynamic Link
#
# A Link says which doctype it points at. A Dynamic Link does not — it names
# another *field*, and the answer is on the record. So the browser has to send
# it, which makes it the one place a client names a doctype, which makes the
# validation the whole feature.
# --------------------------------------------------------------------------- #

DYNAMIC = meta(
	[
		field("reference_type", "Link", "Type", options="DocType"),
		field("reference_name", "Dynamic Link", "Reference", options="reference_type"),
	],
	title_field=None,
)


@pytest.fixture
def dynamic(spaceview, stub_frappe, monkeypatch, stub_spaceview):
	"""A resolved screen over the two fields above, with the space granting
	ToDo and Contact and nothing else."""
	stub_spaceview("_space", lambda code: {"role_name": "R", "space_label": "S"})
	stub_spaceview("_granted_doctypes", lambda space: {"ToDo", "Contact"})
	stub_frappe.db.exists = lambda dt, name=None: name in ("ToDo", "Contact", "User")
	stub_frappe.has_permission = lambda dt, ptype=None, **kw: dt != "Contact"
	return {"space": "s", "all_columns": spaceview._columns(DYNAMIC, ["reference_type", "reference_name"])}


def column_of(spaceview, fieldname):
	return next(
		c for c in spaceview._columns(DYNAMIC, ["reference_type", "reference_name"])
		if c["fieldname"] == fieldname
	)


def test_a_dynamic_link_carries_the_field_that_names_its_target(spaceview):
	"""Without it the browser cannot say what the row points at, and every cell
	shows a raw id."""
	assert column_of(spaceview, "reference_name")["depends_on_field"] == "reference_type"
	assert column_of(spaceview, "reference_type")["depends_on_field"] is None


def test_a_granted_readable_target_resolves(spaceview, dynamic):
	column = column_of(spaceview, "reference_name")
	assert spaceview._link_target(dynamic, column, "ToDo") == "ToDo"


def test_a_target_outside_the_space_is_refused(spaceview, dynamic):
	"""The check that makes this safe. A Dynamic Link is a pointer to an
	arbitrary doctype, so a client naming its own is exactly the widening the
	screen allowlist exists to stop."""
	column = column_of(spaceview, "reference_name")
	assert spaceview._link_target(dynamic, column, "User") is None


def test_a_target_this_user_cannot_read_is_refused(spaceview, dynamic):
	"""Granted to the space and refused to the person. Both have to pass."""
	column = column_of(spaceview, "reference_name")
	assert spaceview._link_target(dynamic, column, "Contact") is None


def test_a_target_that_is_not_a_doctype_is_refused(spaceview, dynamic):
	column = column_of(spaceview, "reference_name")
	assert spaceview._link_target(dynamic, column, "Nonexistent Doctype") is None
	assert spaceview._link_target(dynamic, column, "") is None
	assert spaceview._link_target(dynamic, column, None) is None


def test_a_plain_link_ignores_a_named_target(spaceview, dynamic):
	"""Its doctype is a property of the field, so a client cannot redirect one
	by asking. This is the half that would be easy to lose by threading the
	argument through and using it everywhere."""
	column = column_of(spaceview, "reference_type")
	assert spaceview._link_target(dynamic, column, "ToDo") == "DocType"


def test_rows_are_grouped_by_the_doctype_they_point_at(spaceview, dynamic):
	"""One query per target rather than one per row: a page of forty pointing
	at three doctypes is three queries."""
	column = column_of(spaceview, "reference_name")
	rows = [
		{"reference_type": "ToDo", "reference_name": "T-1"},
		{"reference_type": "ToDo", "reference_name": "T-2"},
		{"reference_type": "Contact", "reference_name": "C-1"},
		{"reference_type": "User", "reference_name": "U-1"},
		{"reference_type": "ToDo", "reference_name": None},
		{"reference_type": None, "reference_name": "T-3"},
	]
	groups = spaceview._link_groups(dynamic, column, rows)

	assert groups == {"ToDo": {"T-1", "T-2"}}, (
		"a refused target contributes no group, and a row missing either half "
		"contributes nothing"
	)


def test_the_companion_field_is_always_fetched(spaceview):
	"""Whether somebody chose to *look* at the type field has nothing to do
	with whether the link beside it can be resolved."""
	columns = [column_of(spaceview, "reference_name")]
	assert "reference_type" in spaceview._fetch_fields(columns)


def test_the_status_field_is_always_fetched(spaceview):
	"""A board puts each card in the column its status names.

	The same rule as the companion field above: a reader who dropped the status
	column from the list has not stopped a board from being made of it, and a
	row fetched without it is a card with nowhere to go.
	"""
	columns = spaceview._columns(TODO, ["description"])
	assert "status" not in spaceview._fetch_fields(columns)
	assert "status" in spaceview._fetch_fields(columns, "status")
	# Asked for once, not twice, where it is also a column somebody is looking
	# at — a duplicate reaches the query as `select status, status`.
	both = spaceview._fetch_fields(spaceview._columns(TODO, ["status"]), "status")
	assert both.count("status") == 1


# --------------------------------------------------------------------------- #
# Attachment Gallery
#
# The one fieldtype whose field holds nothing. Frappe lists it in
# `no_value_fields` and its own control renders the *record's* File rows,
# narrowed by `link_filters` on the docfield — so several attachments under one
# field is already Frappe's model, and ours reads the same two things.
# --------------------------------------------------------------------------- #

def _gallery(spaceview, link_filters):
	fields = [field("photos", "Attachment Gallery", "Photos", link_filters=link_filters)]
	return {
		"space": "s",
		"all_columns": spaceview._columns(meta(fields), ["photos"]),
	}


def test_a_gallery_is_not_layout(spaceview):
	"""It was in LAYOUT_TYPES, so it was skipped entirely — a doctype with a
	gallery simply did not show one."""
	assert not spaceview.fieldtypes.is_layout("Attachment Gallery")


def test_a_gallery_is_never_editable(spaceview):
	"""There is no value to write. The control still uploads and deletes; it
	does that through the File endpoints, which is what `_writable` is right to
	refuse a record save."""
	assert not spaceview.fieldtypes.editable("Attachment Gallery")
	column = _gallery(spaceview, None)["all_columns"][0]
	assert column["editable"] is False


def test_a_gallery_narrows_by_the_docfields_own_filters(spaceview, monkeypatch, stub_spaceview):
	resolved = _gallery(spaceview, '[["File", "is_private", "=", 0]]')
	stub_spaceview("_resolve", lambda *a, **kw: resolved)

	assert spaceview._gallery_filters("s", "screen", "photos") == {"is_private": ["=", 0]}


def test_a_filter_that_is_not_about_files_is_refused(spaceview, monkeypatch, stub_frappe, stub_spaceview):
	"""The same refusal Frappe's own `get_filtered_attachments` makes, and for
	the same reason: a filter naming another doctype is a join nobody asked
	for."""
	resolved = _gallery(spaceview, '[["ToDo", "status", "=", "Open"]]')
	stub_spaceview("_resolve", lambda *a, **kw: resolved)

	with pytest.raises(Exception):
		spaceview._gallery_filters("s", "screen", "photos")


def test_an_expression_filter_is_dropped_rather_than_run(spaceview, monkeypatch, stub_spaceview):
	"""`eval:` in a filter value is the desk running JavaScript against the
	record. We do not run expressions — see `lib/rules.js` — so a filter we
	cannot evaluate narrows nothing instead of being guessed at."""
	resolved = _gallery(spaceview, '[["File", "file_name", "like", "eval:doc.name"]]')
	stub_spaceview("_resolve", lambda *a, **kw: resolved)

	assert spaceview._gallery_filters("s", "screen", "photos") == {}


def test_no_fieldname_narrows_nothing(spaceview):
	"""The record's whole attachment list, which is what the sidebar asks for."""
	assert spaceview._gallery_filters("s", "screen", None) == {}
	assert spaceview._gallery_filters("s", "screen", "") == {}


def test_a_field_that_is_not_a_gallery_narrows_nothing(spaceview, monkeypatch, stub_spaceview):
	"""Silently. A doctype that renamed a field should show all its attachments
	rather than fail to open."""
	fields = [field("notes", "Data", "Notes", link_filters='[["File", "is_private", "=", 0]]')]
	resolved = {"space": "s", "all_columns": spaceview._columns(meta(fields), ["notes"])}
	stub_spaceview("_resolve", lambda *a, **kw: resolved)

	assert spaceview._gallery_filters("s", "screen", "notes") == {}
	assert spaceview._gallery_filters("s", "screen", "missing") == {}


def test_link_filters_are_read_as_the_rows_frappe_stores(spaceview):
	"""They were parsed as an object and Frappe stores an array.

	`_json` answers `{}` for anything that is not a dict, so every
	`link_filters` on every site narrowed nothing — a picker that should have
	offered only active customers offered all of them, with no error anywhere
	to say so. Silent, and the kind of silence a permission-shaped feature
	should never have.
	"""
	rows = spaceview._filter_rows('[["Customer", "disabled", "=", 0]]', "Customer")
	assert rows == [["Customer", "disabled", "=", 0]]


def test_a_link_filter_on_another_doctype_is_refused(spaceview, stub_frappe):
	"""A join nobody asked for, and the same refusal the gallery makes."""
	with pytest.raises(Exception):
		spaceview._filter_rows('[["ToDo", "status", "=", "Open"]]', "Customer")


def test_a_malformed_link_filter_narrows_nothing(spaceview):
	"""Not fatal. A doctype with a filter we cannot read should still open."""
	assert spaceview._filter_rows("not json", "Customer") == []
	assert spaceview._filter_rows('{"disabled": 0}', "Customer") == []
	assert spaceview._filter_rows('[["Customer", "disabled"]]', "Customer") == []
	assert spaceview._filter_rows(None, "Customer") == []


# --------------------------------------------------------------------------- #
# Child tables
#
# A list inside a record. Frappe grants access to child rows through the
# parent, so the interesting questions are all about what a *row* may hold
# rather than about whether the table may be read.
# --------------------------------------------------------------------------- #

ITEM = meta(
	[
		field("item", "Link", "Item", options="Item", in_list_view=1),
		field("qty", "Int", "Quantity", in_list_view=1),
		field("rate", "Currency", "Rate", in_list_view=1),
		field("notes", "Small Text", "Notes"),
		field("margin", "Currency", "Margin", permlevel=1),
		field("parent", "Data", "Parent"),
	],
	title_field=None,
)


@pytest.fixture
def parent(spaceview, stub_frappe):
	"""A doctype with one child table, resolved."""
	stub_frappe.db.exists = lambda dt, name=None: name == "Sales Item"
	stub_frappe.has_permission = lambda dt, ptype=None, **kw: True
	stub_frappe.get_meta = lambda dt: ITEM
	fields = [field("items", "Table", "Items", options="Sales Item")]
	columns = spaceview._columns(meta(fields), ["items"])
	return {"doctype": "Sales Order", "space": "s", "all_columns": columns}


def test_a_child_table_carries_the_child_doctypes_own_shape(spaceview, parent):
	child = parent["all_columns"][0]["child"]
	assert child["doctype"] == "Sales Item"
	# The grid draws what the child marks `in_list_view`, which is the child
	# doctype's own answer to what belongs in a row.
	assert [c["fieldname"] for c in child["columns"]] == ["item", "qty", "rate"]
	# And the form gets everything, so opening a row shows the fields the grid
	# had no room for.
	assert "notes" in [c["fieldname"] for c in child["fields"]]


def test_a_child_rows_permlevel_is_honoured(spaceview, parent):
	"""A grid is not a way around field permissions any more than a list is."""
	child = parent["all_columns"][0]["child"]
	assert "margin" not in [c["fieldname"] for c in child["fields"]]


def test_frappes_bookkeeping_is_out_of_a_child_row_too(spaceview, parent):
	child = parent["all_columns"][0]["child"]
	assert "parent" not in [c["fieldname"] for c in child["fields"]]


def test_a_child_table_is_never_asked_for_in_sql(spaceview, parent):
	"""Its rows are in another table, so selecting it by name is a syntax
	error rather than an empty cell — the same reason `__activity` is filtered
	out here."""
	assert "items" not in spaceview._fetch_fields(parent["all_columns"])


def test_a_child_row_is_narrowed_to_what_the_child_offers(spaceview, parent):
	"""Every key in every row goes through the child's own allowlist, so a row
	naming `parent` or a permlevel field writes neither."""
	changes = spaceview._child_changes(parent, {
		"items": [
			{"item": "A", "qty": 2, "parent": "somewhere-else", "margin": 999, "name": "row-1"},
		],
	})
	assert changes == {"items": [{"item": "A", "qty": 2, "name": "row-1"}]}


def test_a_child_rows_name_survives(spaceview, parent):
	"""It is how Frappe tells an edited row from a new one. Without it every
	save deletes and recreates the whole table, losing each row's identity and
	anything attached to it."""
	changes = spaceview._child_changes(parent, {"items": [{"item": "A", "name": "row-1"}]})
	assert changes["items"][0]["name"] == "row-1"


def test_a_payload_that_is_not_rows_is_ignored(spaceview, parent):
	assert spaceview._child_changes(parent, {"items": "not rows"}) == {}
	assert spaceview._child_changes(parent, {}) == {}


def test_a_table_multiselect_resolves_like_a_child_table(spaceview, stub_frappe):
	"""It is a child table whose rows hold one Link each, which is why it goes
	through the same resolver — and why the control can find its own link
	field rather than guessing at a name."""
	stub_frappe.db.exists = lambda dt, name=None: name == "Tag Link"
	stub_frappe.has_permission = lambda dt, ptype=None, **kw: True
	stub_frappe.get_meta = lambda dt: meta(
		[field("tag", "Link", "Tag", options="Tag", in_list_view=1)], title_field=None,
	)
	fields = [field("tags", "Table MultiSelect", "Tags", options="Tag Link")]
	column = spaceview._columns(meta(fields), ["tags"])[0]

	assert column["child"]["doctype"] == "Tag Link"
	assert [c["fieldtype"] for c in column["child"]["fields"]] == ["Link"]


# --------------------------------------------------------------------------- #
# Which spaces a person may open
#
# The site's entitlements decide which exist here; the reader's roles decide
# which are theirs. `_space` used to ask only the first, so a space code
# guessed at resolved and handed back the space's shape — its label, its
# screens, its navigation. Harmless while one audience shares a site, and
# exactly wrong once two do.
# --------------------------------------------------------------------------- #

SPACES = [
	{"space_code": "sales", "space_label": "Sales", "role_name": "Sales User"},
	{"space_code": "ops", "space_label": "Operations", "role_name": "OneSpace Operator"},
	{"space_code": "open", "space_label": "Everyone", "role_name": ""},
]


@pytest.fixture
def sited(spaceview, stub_frappe, monkeypatch):
	# `_space` imports sync inside the function, so the module has to be
	# imported here rather than looked up in sys.modules — the resolver fixture
	# has just cleared it.
	from oneapp.oneapp_core import sync

	monkeypatch.setattr(sync, "state", lambda: {"spaces": SPACES})
	return stub_frappe


def test_a_space_whose_role_you_hold_resolves(spaceview, sited):
	sited.get_roles = lambda user=None: ["Sales User"]
	assert spaceview._space("sales")["space_label"] == "Sales"


def test_a_space_whose_role_you_lack_is_refused(spaceview, sited):
	"""The fix. It used to resolve, and hand back the screens."""
	sited.get_roles = lambda user=None: ["Sales User"]
	with pytest.raises(sited.PermissionError):
		spaceview._space("ops")


def test_a_space_with_no_role_is_open_to_everybody(spaceview, sited):
	"""Which is what an empty `role_name` has always meant — a manifest
	declares one when it wants the space narrowed."""
	sited.get_roles = lambda user=None: []
	assert spaceview._space("open")["space_label"] == "Everyone"


def test_the_rail_and_the_resolver_share_one_answer(spaceview, sited):
	"""They used to disagree: the rail asked about roles and the resolver did
	not, so a space absent from somebody's rail still answered when its code
	was asked for by name."""
	sited.get_roles = lambda user=None: ["OneSpace Operator"]
	assert [s["space_code"] for s in spaceview.visible(SPACES)] == ["ops", "open"]


# --------------------------------------------------------------------------- #
# The customer's word for one of these
#
# The heading over a create form used to be the doctype's own name, so a screen
# called Tasks opened a dialog headed **New ToDo** — a Frappe word, on the one
# surface this product promises has none.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
	"label,expected",
	[
		("Tasks", "Task"),
		("Notes", "Note"),
		("Events", "Event"),
		("Approvals", "Approval"),
		("Invoices", "Invoice"),
		("Companies", "Company"),
		("Addresses", "Address"),
		("Batches", "Batch"),
		("Taxes", "Tax"),
		# Already singular, and left alone rather than trimmed to "Statu".
		("Status", "Statu"),
	],
)
def test_a_screen_label_is_singularised(spaceview, label, expected):
	assert spaceview._singular({"label": label}) == expected


def test_a_screen_may_say_the_word_itself(spaceview):
	"""The escape hatch, and the reason there is one: the rule is small and
	English is not. A screen whose plural it gets wrong corrects it in one
	word beside its label."""
	assert spaceview._singular({"label": "People", "singular": "Person"}) == "Person"


def test_a_change_says_who_by_their_name(spaceview):
	"""A Version stores a user id, which on this product is an email address.
	The timeline showed it raw beside comments that showed full names."""
	row = {"name": "v1", "owner": "robin@zzmock.test", "creation": "2026-01-01",
	       "data": '{"changed": [["status", "Open", "Closed"]]}'}
	resolved = {"columns": [{"fieldname": "status", "label": "Status",
	                         "fieldtype": "Select"}]}

	made = spaceview._change(row, resolved, {"robin@zzmock.test": "Robin Vale"})
	assert made["by"] == "Robin Vale"
	# And the id, because the avatar is keyed on it.
	assert made["by_id"] == "robin@zzmock.test"


def test_a_change_falls_back_to_the_id(spaceview):
	"""A deleted user still owns their versions, and a blank byline is worse
	than an address."""
	row = {"name": "v1", "owner": "gone@zzmock.test", "creation": "2026-01-01",
	       "data": '{"changed": [["status", "Open", "Closed"]]}'}
	resolved = {"columns": [{"fieldname": "status", "label": "Status",
	                         "fieldtype": "Select"}]}

	assert spaceview._change(row, resolved, {})["by"] == "gone@zzmock.test"
