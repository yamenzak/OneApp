"""Every property the SPA reads is one something is expected to declare.

`spaceview` reads fifty-odd properties off Frappe's metadata and hands them to
the browser. Each one is a feature: `bold` draws a column heavier, `fetch_from`
fills a field, `states` colours a badge. A property that reaches the SPA and
that nothing ever sets is a feature that has never once run — and it looks
exactly like a feature that works, because the fallback is always something
plausible.

Two of those turned up when this file was written:

  * `states` — read for badge colour, declared by **none** of our 37 doctypes.
    Eighteen screens showed a status badge, and every one of them fell through
    to `valueTheme`'s word list, which guesses from the text. "Failed" came out
    red because it contains "fail"; "Draining", "Claimed" and "Adjustment" all
    came out the same shade of nothing.
  * `search_fields` — read by the link picker for the line under each result,
    declared by none of our thirteen link targets. Picking a Shard showed its
    id and a blank line where "nuremberg · n1.frappe.cloud" belonged.

So this is an inventory, not a rule that everything must be set. Most of these
belong to a *tenant's* doctypes — ERPNext sets `permlevel` and `allow_on_submit`
and we never should — and the honest guard is that each is filed under a reason.
A new `getattr(df, …)` in `spaceview` that nobody has classified fails here.
"""

import glob
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPACEVIEW = ROOT / "apps/oneapp/oneapp/oneapp_core/spaceview.py"

# Set by at least one doctype of ours, and therefore exercised whenever the
# operator console renders. These are the ones a regression would show up in.
OURS = {
	"reqd", "read_only", "in_list_view", "in_standard_filter", "default",
	"description", "hidden", "precision", "unique", "set_only_once",
	"depends_on",
}

# Real, read, and correctly unset by us — they describe a *tenant's* doctypes.
# Our own are thirteen-field records an operator edits; ERPNext's are the ones
# with permlevels, submit workflows and fields that fetch from a link.
THEIRS = {
	"allow_in_quick_entry": "Frappe's quick entry, on doctypes that have one",
	"allow_on_submit": "only meaningful where a doctype is submittable",
	"bold": "an app's own emphasis on one field of a long form",
	"collapsible": "a section an app folds by default",
	"collapsible_depends_on": "…and the rule that decides when",
	"columns": "Frappe's grid width, which our forms do not use",
	"documentation_url": "a link an app author wrote for one field",
	"fetch_from": "a value that comes from a link — see spaceview.fetched",
	"fetch_if_empty": "…and whether it overwrites what was typed",
	"hide_border": "a section an app draws without a rule",
	"hide_days": "a Duration that counts in hours",
	"hide_seconds": "a Duration that stops at minutes",
	"ignore_user_permissions": "a link an app deliberately leaves unfiltered",
	"in_preview": "the fields a link's hover card shows",
	"length": "a column width an app caps",
	"link_filters": "a link an app narrows by another field",
	"mandatory_depends_on": "required only sometimes",
	"mask": "an input mask, which none of ours want",
	"max_height": "a text area an app bounds",
	"max_value": "a number an app bounds",
	"min_value": "…and the other end",
	"non_negative": "a number an app refuses below zero",
	"not_nullable": "a column an app insists on",
	"permlevel": "a field an app puts behind a second permission",
	"placeholder": "an app's own hint text",
	"read_only_depends_on": "editable only sometimes",
	"remember_last_selected_value": "a link that repeats the last pick",
	"show_description_on_click": "a description too long to print",
	"sort_options": "a Select the desk shows alphabetically",
	"translatable": "a field an app translates",
}

DOCTYPE_OURS = {
	"allow_rename", "autoname", "in_create", "sort_field", "sort_order",
	"states", "title_field", "track_changes", "search_fields",
}

DOCTYPE_THEIRS = {
	"image_field": "an avatar, on doctypes that carry a picture",
	"is_submittable": "none of ours are",
	"max_attachments": "a cap an app puts on its own uploads",
	"track_seen": "a read receipt, which none of ours want",
	"get_permlevel_access": "a method, not a property",
}


def read(pattern: str) -> set:
	source = SPACEVIEW.read_text()
	return set(re.findall(pattern, source))


def field_properties() -> set:
	props = read(r'getattr\(df, "(\w+)"') | read(r'\bdf\.(\w+)\b')
	# The four every field has; they are the payload, not a property.
	return props - {"get", "fieldname", "fieldtype", "options", "label"}


def doctype_properties() -> set:
	props = read(r'getattr\(meta, "(\w+)"') | read(r'\bmeta\.(\w+)\b')
	return props - {"get_field", "get", "fields", "name", "get_valid_columns", "permissions"}


def declared_anywhere() -> set:
	found = set()
	for path in glob.glob(str(ROOT / "apps/*/*/*/doctype/*/*.json")):
		doc = json.loads(Path(path).read_text())
		found |= {key for key, value in doc.items() if value}
		for field in doc.get("fields", []):
			found |= {key for key, value in field.items() if value}
	return found


def test_the_reader_found_the_properties():
	assert len(field_properties()) > 30, "the docfield scan matched almost nothing"
	assert len(doctype_properties()) > 8, "the doctype scan matched almost nothing"


def test_every_field_property_is_classified():
	"""The guard. A property added to the payload without a decision about who
	sets it is one that may already be dead."""
	unknown = field_properties() - OURS - set(THEIRS)
	assert not unknown, (
		f"spaceview now sends {sorted(unknown)} and nothing says who declares "
		f"them. Add each to OURS (and set it on a doctype) or to THEIRS with "
		f"the reason a tenant's app is the one that sets it."
	)


def test_every_doctype_property_is_classified():
	unknown = doctype_properties() - DOCTYPE_OURS - set(DOCTYPE_THEIRS)
	assert not unknown, (
		f"spaceview now sends {sorted(unknown)} at doctype level and nothing "
		f"says who declares them: {sorted(unknown)}"
	)


@pytest.mark.parametrize("prop", sorted(OURS | DOCTYPE_OURS))
def test_a_property_we_claim_to_set_is_actually_set(prop):
	"""The half that caught `states` and `search_fields`.

	Claiming a property is ours and then setting it nowhere is exactly the
	failure this file exists for — the SPA reads it, the fallback fires, and
	the feature looks like it works.
	"""
	assert prop in declared_anywhere(), (
		f"{prop} is listed as one of ours and no doctype sets it. Either set it "
		f"in gen_doctypes.py, or move it to THEIRS with the reason it belongs "
		f"to a tenant's app."
	)


def test_every_link_target_says_what_to_search():
	"""`search_fields` is what a picker prints under each result, and what it
	searches besides the id and the title. Without it a Shard picker offers
	`nuremberg-01` and a blank line."""
	docs = {}
	for path in glob.glob(str(ROOT / "apps/*/*/*/doctype/*/*.json")):
		doc = json.loads(Path(path).read_text())
		docs[doc["name"]] = doc

	targets = {
		field["options"]
		for doc in docs.values()
		for field in doc.get("fields", [])
		if field["fieldtype"] == "Link" and field.get("options") in docs
	}
	assert targets, "nothing links to anything of ours — the scan is wrong"

	silent = sorted(t for t in targets if not docs[t].get("search_fields"))
	assert not silent, (
		f"these are linked to and say nothing about what to search, so their "
		f"picker shows an id and a blank line: {silent}"
	)
