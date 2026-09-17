"""The workspace's own word for a screen somebody else named.

`docs/ONECRM.md` stage 7, `onespace/words.py`. **Deal** and **Lead** are the
house words of one industry. They are the right default and they are the wrong
answer for a charity with donors, a clinic with referrals and a council with
planning applications — and the checkpoint is a workspace that sells to private
people opening OneCRM and seeing nothing about companies.

Four claims.

**An overlay, not an edit.** The screens arrive from the control plane on every
sync and are rewritten wholesale, so a label typed into one would last fifteen
minutes.

**Applied in one place.** `sync.state()` builds the list the rail, the
switcher, the resolver, the breadcrumbs and the New button all read.

**The word is not the key.** `screen` stays what the address bar spells, so a
rename changes no url, no saved view and no declaration.

**And every space has a page for it**, appended by the engine rather than
declared in nine manifests and forgotten in the tenth.
"""

import pytest


@pytest.fixture
def words(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onespace.words"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onespace.words")


SPACES = [{
	"space_code": "onecrm",
	"screens": [
		{"screen": "deals", "label": "Deals", "singular": "Deal"},
		{"screen": "leads", "label": "Leads", "singular": "Lead"},
	],
}, {
	"space_code": "oneproject",
	"screens": [{"screen": "tasks", "label": "Tasks", "singular": "Task"}],
}]


def site(words, monkeypatch, rows=()):
	monkeypatch.setattr(words.frappe, "get_all", lambda *a, **k: [dict(one) for one in rows])
	words.frappe.cache().delete_value(words.CACHE_KEY)


def test_a_renamed_screen_reads_the_workspaces_word(words, monkeypatch):
	site(words, monkeypatch, [
		{"space_code": "onecrm", "screen": "deals", "label": "Donations",
		 "singular": "Donation"},
	])
	found = words.renamed(SPACES)
	deals = found[0]["screens"][0]
	assert deals["label"] == "Donations"
	assert deals["singular"] == "Donation"


def test_the_key_is_untouched(words, monkeypatch):
	"""A rename changes what a person reads and nothing a machine reads: no
	url, no saved view, no bookmark, no declaration."""
	site(words, monkeypatch, [
		{"space_code": "onecrm", "screen": "deals", "label": "Donations"},
	])
	assert words.renamed(SPACES)[0]["screens"][0]["screen"] == "deals"


def test_a_blank_singular_follows_the_label(words, monkeypatch):
	"""A workspace that renamed Deals to Donations and left this empty means
	Donation — not Deal, which is what falling back to the shipped word would
	have given them."""
	site(words, monkeypatch, [
		{"space_code": "onecrm", "screen": "deals", "label": "Donations",
		 "singular": ""},
	])
	assert words.renamed(SPACES)[0]["screens"][0]["singular"] == "Donations"


def test_a_screen_nobody_renamed_is_left_alone(words, monkeypatch):
	site(words, monkeypatch, [
		{"space_code": "onecrm", "screen": "deals", "label": "Donations"},
	])
	found = words.renamed(SPACES)
	assert found[0]["screens"][1]["label"] == "Leads"
	assert found[1]["screens"][0]["label"] == "Tasks"


def test_a_row_naming_another_space_does_not_reach_this_one(words, monkeypatch):
	"""Keyed `space_code/screen`, because `deals` is not a globally unique
	name and a rename that leaked across spaces would be one nobody could
	undo from the page they were on."""
	site(words, monkeypatch, [
		{"space_code": "oneproject", "screen": "deals", "label": "Donations"},
	])
	assert words.renamed(SPACES)[0]["screens"][0]["label"] == "Deals"


def test_a_row_with_no_label_is_not_a_rename(words, monkeypatch):
	site(words, monkeypatch, [
		{"space_code": "onecrm", "screen": "deals", "label": "   "},
	])
	assert words.renamed(SPACES)[0]["screens"][0]["label"] == "Deals"


def test_nothing_renamed_hands_the_list_straight_back(words, monkeypatch):
	"""The common case, and it must cost nothing: every request that draws a
	rail goes through here."""
	site(words, monkeypatch, [])
	assert words.renamed(SPACES) is SPACES


def test_the_spaces_are_copied_rather_than_rewritten(words, monkeypatch):
	"""`state()` caches what it builds, so a list rewritten in place is a list
	some other caller already holds a reference to."""
	site(words, monkeypatch, [
		{"space_code": "onecrm", "screen": "deals", "label": "Donations"},
	])
	words.renamed(SPACES)
	assert SPACES[0]["screens"][0]["label"] == "Deals"


def test_a_bench_that_has_not_migrated_it_draws_the_shipped_words(
		words, monkeypatch):
	"""A rail drawn in the shipped words is right; a rail that will not draw
	is not."""
	def raises(*a, **k):
		raise Exception("no such table")

	monkeypatch.setattr(words.frappe, "get_all", raises)
	words.frappe.cache().delete_value(words.CACHE_KEY)
	assert words.renamed(SPACES) is SPACES


# --------------------------------------------------------------------------- #
# The page every space gets
# --------------------------------------------------------------------------- #

def test_every_space_gets_a_page_for_its_words(words, monkeypatch):
	monkeypatch.setattr(words.frappe, "get_installed_apps", lambda: ["oneapp"])
	found = words.worded(SPACES)
	for space in found:
		assert [one["screen"] for one in space["screens"]][-1] == words.SCREEN


def test_the_page_is_narrowed_to_its_own_space(words, monkeypatch):
	"""And its New dialog starts with the space already in it: a page narrowed
	by a filter whose New made a row the page would not then show is what
	`view_settings.create` was added for."""
	monkeypatch.setattr(words.frappe, "get_installed_apps", lambda: ["oneapp"])
	page = words.worded(SPACES)[0]["screens"][-1]
	assert words.frappe.parse_json(page["filters"]) == {"space_code": "onecrm"}
	assert words.frappe.parse_json(page["view_settings"]) == {
		"create": {"values": {"space_code": "onecrm"}},
	}


def test_the_page_is_not_a_place_to_go(words, monkeypatch):
	"""`hide_in_nav`: it is a tab on the Configuration page, where the rest of
	a space's own tables are, and not a rail entry beside the work."""
	monkeypatch.setattr(words.frappe, "get_installed_apps", lambda: ["oneapp"])
	assert words.worded(SPACES)[0]["screens"][-1]["hide_in_nav"] == 1


def test_the_control_plane_gets_none(words, monkeypatch):
	"""An operator console rather than a workspace — the same line
	`sync.configured` draws."""
	from oneapp.onespace import one as ONE

	monkeypatch.setattr(words.frappe, "get_installed_apps",
	                    lambda: ["oneapp", ONE.CONTROL_APP])
	assert words.worded(SPACES) is SPACES


def test_a_space_that_already_has_one_is_left_alone(words, monkeypatch):
	monkeypatch.setattr(words.frappe, "get_installed_apps", lambda: ["oneapp"])
	once = words.worded(SPACES)
	assert [one["screen"] for one in words.worded(once)[0]["screens"]].count(
		words.SCREEN) == 1
