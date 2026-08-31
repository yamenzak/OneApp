"""A Link fills in the fields that say they come from it.

`fetch_from` on a docfield is `<link fieldname>.<field on the target>`, and
Frappe applies it on save whatever wrote the record — `set_fetch_from_value`
runs on every insert and update. So this endpoint changes no outcome; it changes
*when* you see it. Before, the field printed a note saying "From Assigned By",
stayed empty while the form was filled in, and was silently overwritten on save
by the value it was always going to hold. Somebody who typed into it watched
their own text disappear with no error and nothing to read.

The bounds matter more than the feature. The value arriving is a record id from
a browser, so a careless version of this is a way to read one field of any
doctype on the site.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPACEVIEW = ROOT / "apps/oneapp/oneapp/oneapp_core/spaceview.py"


def body() -> str:
	source = SPACEVIEW.read_text()
	start = source.index("def fetched(")
	return source[start:]


def test_the_source_field_has_to_be_on_this_screen():
	"""`_link_column` is the same bound `link_options` uses, and it throws a
	PermissionError rather than answering — so a request naming `hmac_secret`
	is refused rather than served an empty dict it might retry differently."""
	assert "_link_column(resolved, fieldname)" in body()


def test_the_source_field_has_to_be_a_link():
	"""Without this, any field on the screen could name any doctype: the target
	comes from the field's own `options`, and on a Data field that is whatever
	somebody put there — `Email`, `JSON`, or nothing."""
	text = body()
	assert '("Link", "Dynamic Link")' in text
	assert "frappe.PermissionError" in text


def test_the_target_doctype_is_never_a_parameter():
	"""`_link_target` reads the field's own options. A doctype from the request
	would make this a general-purpose reader for one field of any table."""
	assert "_link_target(resolved, column)" in body()


def test_only_fields_on_this_screen_are_answered():
	"""The reply is built from `all_columns`, so it cannot carry a field the
	screen does not show — including one above this person's permlevel, which
	`_columns` has already dropped."""
	text = body()
	assert 'resolved.get("all_columns")' in text
	assert 'source.startswith(prefix)' in text


def test_the_read_runs_the_callers_own_permissions():
	"""`frappe.db.get_value` applies them. A link to a record this person may
	not read answers nothing rather than leaking a field of it."""
	assert "frappe.db.get_value(target, value, fields, as_dict=True)" in body()


def test_one_read_for_every_field():
	"""A form with six fetched fields should not be six queries."""
	text = body()
	assert "sorted({spec[\"field\"] for spec in wanted.values()})" in text


def test_fetch_if_empty_travels_with_the_value():
	"""Frappe's own rule, and the difference between a convenience and a form
	that argues with you: `fetch_if_empty` fills a blank and leaves anything
	else alone. Without it, choosing a customer overwrites the company name
	somebody just corrected by hand."""
	assert '"only_if_empty": bool(one.get("fetch_if_empty"))' in body()

	form = (ROOT / "apps/oneapp/frontend/src/components/screen/FormSections.vue").read_text()
	assert "if (spec.only_if_empty && values.value[name]) continue" in form


def test_a_failed_lookup_leaves_the_form_alone():
	"""It is a convenience. If it fails the field stays as it was and the save
	still fills it — which is exactly the behaviour that existed before this
	call did, so there is nothing here worth interrupting somebody for."""
	form = (ROOT / "apps/oneapp/frontend/src/components/screen/FormSections.vue").read_text()
	fn = form[form.index("const wrote ="):]
	fn = fn[: fn.index("\n}\n")]
	assert "catch {" in fn, "a failed lookup now propagates out of the form"
	assert fn.count("return") >= 2, "the early exits are gone"


def test_a_link_with_nothing_fetching_from_it_is_not_a_request():
	"""Most Links are this. Answering `{}` early keeps a form that picks a
	region from making a round trip to be told nothing."""
	assert "if not wanted:" in body()
