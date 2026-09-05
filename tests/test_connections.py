"""What else in this space is about one record.

Frappe's Connections, derived from the schema rather than declared. The whole
value is in the deriving: a screen *could* name its related screens and one
already can — `view_settings.showcase.tabs` — but a declaration only exists
where somebody wrote one, and until this every record in the product except
RUA's project page had no answer at all to "what has been filed against this".

Three things have to hold, and each fails quietly:

  * the field it filters on has to be the right one, or the tab is a list of
    somebody else's records;
  * a Dynamic Link needs its doctype as well as its id, or a letter about a
    licence turns up on a project that shares its name;
  * the tabs have to be bounded by the space, because a connection that opens
    a screen this workspace has not got is worse than no connection.
"""

import types

import pytest


@pytest.fixture
def connections(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	# By path rather than `from ... import connections`: the package re-exports
	# the *function* under that name, so the plain import hands back a function
	# and every `module.frappe` below fails somewhere unhelpful.
	import importlib

	return importlib.import_module("oneapp.oneapp_core.spaceview.connections")


def field(fieldname, fieldtype="Data", options=None):
	return types.SimpleNamespace(fieldname=fieldname, fieldtype=fieldtype, options=options)


def meta(fields):
	found = {f.fieldname: f for f in fields}
	return types.SimpleNamespace(fields=fields, get_field=found.get)


def schema(connections, monkeypatch, doctypes: dict):
	"""`get_meta` over a handful of made-up doctypes."""
	def get_meta(name):
		if name not in doctypes:
			raise KeyError(name)
		return meta(doctypes[name])

	monkeypatch.setattr(connections.frappe, "get_meta", get_meta)
	monkeypatch.setattr(connections.frappe, "scrub",
	                    lambda name: name.lower().replace(" ", "_"), raising=False)


SPACE = {
	"screens": [
		{"screen": "projects", "label": "Projects", "document_type": "Project",
		 "icon": "lucide-briefcase"},
		{"screen": "invoices", "label": "Invoices", "document_type": "Sales Invoice",
		 "icon": "lucide-receipt"},
		{"screen": "letters", "label": "Letters", "document_type": "Correspondence",
		 "icon": "lucide-mail"},
	],
}

GRANTED = {"Project", "Sales Invoice", "Correspondence"}


# --------------------------------------------------------------------------- #
# Which field points back
# --------------------------------------------------------------------------- #

def test_a_link_field_is_the_connection(connections, monkeypatch):
	schema(connections, monkeypatch, {
		"Sales Invoice": [field("customer", "Link", "Customer"),
		                  field("project", "Link", "Project")],
	})
	assert connections.points_back("Sales Invoice", "Project") == {
		"field": "project", "where": [],
	}


def test_the_field_named_after_the_doctype_wins(connections, monkeypatch):
	"""A Sales Invoice carries `project` and `cost_center`, both Links, and only
	one of them is what somebody means by this project's invoices."""
	schema(connections, monkeypatch, {
		"Sales Invoice": [field("parent_project", "Link", "Project"),
		                  field("project", "Link", "Project")],
	})
	assert connections.points_back("Sales Invoice", "Project")["field"] == "project"


def test_a_dynamic_link_carries_its_doctype_too(connections, monkeypatch):
	"""Half of Frappe's own linking is this shape — a field holding a doctype
	beside a field holding an id. Filtering on the id alone would put a
	licence's letters on a project that happens to share its name."""
	schema(connections, monkeypatch, {
		"Correspondence": [field("about_doctype", "Link", "DocType"),
		                   field("about", "Dynamic Link", "about_doctype")],
	})
	assert connections.points_back("Correspondence", "Compliance Document") == {
		"field": "about",
		"where": [["about_doctype", "=", "Compliance Document"]],
	}


def test_a_link_beats_a_dynamic_link(connections, monkeypatch):
	"""The narrower statement: this field is always a project, and a screen
	that carries one meant it."""
	schema(connections, monkeypatch, {
		"Correspondence": [field("about_doctype", "Link", "DocType"),
		                   field("about", "Dynamic Link", "about_doctype"),
		                   field("project", "Link", "Project")],
	})
	assert connections.points_back("Correspondence", "Project")["field"] == "project"


def test_a_dynamic_link_naming_no_field_is_a_broken_field(connections, monkeypatch):
	schema(connections, monkeypatch, {
		"Correspondence": [field("about", "Dynamic Link", "not_a_field")],
	})
	assert connections.points_back("Correspondence", "Project") is None


def test_a_doctype_this_site_has_not_got_is_not_a_connection(connections, monkeypatch):
	"""A space may name more than the tenant installed. Ordinary, and not worth
	a traceback in the middle of resolving a screen."""
	schema(connections, monkeypatch, {})
	assert connections.points_back("Sales Invoice", "Project") is None


# --------------------------------------------------------------------------- #
# Which screens become tabs
# --------------------------------------------------------------------------- #

def test_the_screens_that_point_back_become_tabs(connections, monkeypatch):
	schema(connections, monkeypatch, {
		"Project": [field("customer", "Link", "Customer")],
		"Sales Invoice": [field("project", "Link", "Project")],
		"Correspondence": [field("about_doctype", "Link", "DocType"),
		                   field("about", "Dynamic Link", "about_doctype")],
	})
	found = connections.connections(SPACE, "projects", "Project", GRANTED)

	assert [one["screen"] for one in found] == ["invoices", "letters"]
	assert found[0]["field"] == "project"
	assert found[0]["label"] == "Invoices"
	assert found[1]["where"] == [["about_doctype", "=", "Project"]]


def test_a_screen_the_space_did_not_grant_is_not_offered(connections, monkeypatch):
	"""A connection that opens a screen this workspace has no permission on is
	worse than no connection: it is a tab that always comes back empty."""
	schema(connections, monkeypatch, {
		"Sales Invoice": [field("project", "Link", "Project")],
		"Correspondence": [field("about_doctype", "Link", "DocType"),
		                   field("about", "Dynamic Link", "about_doctype")],
	})
	found = connections.connections(SPACE, "projects", "Project", {"Project"})
	assert found == []


def test_a_screen_is_never_its_own_connection(connections, monkeypatch):
	"""A doctype that links to itself — a project's variations, a licence's
	renewal — would otherwise draw a tab of the same screen you are on."""
	schema(connections, monkeypatch, {
		"Project": [field("parent_project", "Link", "Project")],
		"Sales Invoice": [],
		"Correspondence": [],
	})
	assert connections.connections(SPACE, "projects", "Project", GRANTED) == []


def test_a_screen_the_showcase_already_declares_is_not_repeated(connections, monkeypatch):
	"""The manifest said it first, said it in its own words, and put it in its
	own order."""
	schema(connections, monkeypatch, {
		"Project": [],
		"Sales Invoice": [field("project", "Link", "Project")],
		"Correspondence": [],
	})
	found = connections.connections(
		SPACE, "projects", "Project", GRANTED,
		declared=[{"screen": "invoices", "field": "project", "label": "Money in"}],
	)
	assert found == []


def test_there_is_a_ceiling(connections, monkeypatch):
	"""Past six the strip is a menu, and the rail already is one."""
	many = {"screens": [
		{"screen": f"s{n}", "label": f"S{n}", "document_type": f"D{n}"}
		for n in range(12)
	]}
	schema(connections, monkeypatch, {
		f"D{n}": [field("project", "Link", "Project")] for n in range(12)
	})
	found = connections.connections(many, "projects", "Project",
	                                {f"D{n}" for n in range(12)})
	assert len(found) == connections.CONNECTIONS


def test_a_screen_over_nothing_is_skipped(connections, monkeypatch):
	"""A screen naming a component rather than a doctype — the mail screen, the
	drive — has no rows to filter and no field to filter them on."""
	schema(connections, monkeypatch, {"Sales Invoice": [field("project", "Link", "Project")]})
	space = {"screens": [
		{"screen": "mail", "label": "Mail", "document_type": ""},
		{"screen": "invoices", "label": "Invoices", "document_type": "Sales Invoice"},
	]}
	found = connections.connections(space, "projects", "Project", GRANTED)
	assert [one["screen"] for one in found] == ["invoices"]


def test_a_named_link_is_offered_before_one_that_could_be_about_anything(connections, monkeypatch):
	"""A Link is a screen saying "this is always about a project". A Dynamic
	Link is a screen saying it could be about anything, and those turn up on
	every record in the space — so where the ceiling bites, the vaguer half is
	what loses its place."""
	space = {"screens": [
		{"screen": "letters", "label": "Letters", "document_type": "Correspondence"},
		{"screen": "invoices", "label": "Invoices", "document_type": "Sales Invoice"},
	]}
	schema(connections, monkeypatch, {
		"Correspondence": [field("about_doctype", "Link", "DocType"),
		                   field("about", "Dynamic Link", "about_doctype")],
		"Sales Invoice": [field("project", "Link", "Project")],
	})
	found = connections.connections(space, "projects", "Project",
	                                {"Correspondence", "Sales Invoice"})
	assert [one["screen"] for one in found] == ["invoices", "letters"]
