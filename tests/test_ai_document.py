"""The one thing a model may ask for that produces a file.

Everything else on the registry changes a field, adds a row to somebody's
diary or makes a task — all of them things whose whole content fits on the
card. A document does not: what is being agreed to is prose, and the three
claims worth holding are that the prose is written *before* the person is
asked, that applying goes through the same call the New menu posts to, and
that once it is applied there is a way to the thing rather than the word
"Applied" and a hunt through a folder.
"""

import sys
import types

import pytest


class Row(dict):
	def __getattr__(self, name):
		return self.get(name)

	def insert(self, **kw):
		self.setdefault("name", f"sug-{len(STORED) + 1}")
		STORED[self["name"]] = self
		return self

	def db_set(self, values, **kw):
		self.update(values)


STORED: dict[str, Row] = {}


@pytest.fixture
def doc(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace") or name.startswith("oneapp.onedoc"):
			del sys.modules[name]

	STORED.clear()
	made, stored = [], []

	stub_frappe.get_doc = lambda first, *a, **k: (
		Row(first) if isinstance(first, dict) else STORED.get(a[0])
	)
	stub_frappe.get_all = lambda *a, **k: []
	stub_frappe.db.exists = lambda *a, **k: True
	stub_frappe.db.savepoint = lambda *a, **k: None
	stub_frappe.db.release_savepoint = lambda *a, **k: None
	stub_frappe.db.rollback = lambda *a, **k: None
	stub_frappe.db.get_value = lambda *a, **k: "Ali Hassan"
	stub_frappe.has_permission = lambda *a, **k: True
	stub_frappe.utils.now = lambda: "2026-09-16 08:00:00"
	stub_frappe.get_meta = lambda dt: types.SimpleNamespace(
		get_title_field=lambda: "employee_name")

	from oneapp.onedoc import actions as module, body, writing
	from oneapp.oneai import actions

	# The real modules, with the two calls that touch a database replaced. A
	# stub in `sys.modules` would be a second `writing` for the package façade
	# to re-export, and the façade imports six names off it.
	monkeypatch.setattr(
		writing, "make",
		lambda title="", folder="", doctype="", docname="", template="": (
			made.append({"title": title, "doctype": doctype, "docname": docname})
			or {"name": "FILE-1", "title": title, "url": "/one/docs/FILE-1"}
		),
	)
	monkeypatch.setattr(body, "store",
	                    lambda name, content, html="", settings=None:
	                    stored.append({"name": name, "content": content}) or 1)

	return types.SimpleNamespace(
		module=module, actions=actions, body=body, frappe=stub_frappe,
		monkeypatch=monkeypatch, made=made, stored=stored, kept=STORED,
	)


LETTER = """To whom it may concern,

This is to certify that Ali Hassan has been employed since [date].

Yours faithfully,
The People team"""


def ask(doc, **kw):
	said = {"title": "To whom it may concern", "text": LETTER,
	        "doctype": "Employee", "docname": "HR-EMP-0001"}
	said.update(kw)
	return doc.actions.propose("document.write", said, session="s1",
	                           about=(said.get("doctype") or "", said.get("docname") or ""))


# --------------------------------------------------------------------------- #
# Proposing writes nothing
# --------------------------------------------------------------------------- #

def test_asking_makes_no_file(doc):
	answered = ask(doc)

	assert answered["proposed"] in doc.kept
	assert doc.made == [] and doc.stored == []
	assert "waiting" in answered["note"]


def test_the_prose_is_on_the_card_before_anybody_agrees(doc):
	"""What is being agreed to is the letter, so the letter is what is shown.

	A card that said "write a letter about this employee" and then produced
	four paragraphs nobody had seen would be `actions.py`'s own argument
	inverted: the person agreed to a summary, and the summary is not the diff.
	"""
	name = ask(doc)["proposed"]
	kind = doc.actions.get("document.write")
	said = kind.rows(doc.actions._read(doc.kept[name].payload), {})

	body = next(one for one in said if one["label"] == "Document")
	assert "To whom it may concern" in body["now"]
	assert "The People team" in body["now"]


def test_an_empty_document_is_refused(doc):
	assert "empty" in ask(doc, text="   ")["error"]
	assert "called" in ask(doc, title=" ")["error"]


def test_a_record_this_person_cannot_write_is_refused(doc):
	doc.frappe.has_permission = lambda *a, **k: False
	assert "not yours" in ask(doc)["error"]


def test_a_record_that_is_not_there_is_refused(doc):
	doc.frappe.db.exists = lambda *a, **k: False
	assert "no Employee" in ask(doc)["error"]


# --------------------------------------------------------------------------- #
# Applying goes the way a person would have gone
# --------------------------------------------------------------------------- #

def test_applying_makes_the_file_through_the_same_call_the_menu_posts_to(doc):
	name = ask(doc)["proposed"]
	done = doc.actions.apply(name)

	assert done["ok"] and done["name"] == "FILE-1"
	assert doc.made == [{"title": "To whom it may concern",
	                     "doctype": "Employee", "docname": "HR-EMP-0001"}]
	# And the prose landed, as a body rather than as a string.
	assert '"type": "doc"' in doc.stored[0]["content"]


def test_an_applied_card_says_where_the_document_went(doc):
	"""The half of this that is not about safety.

	A card that stopped at "Applied" was the one place in the product where
	somebody had to go and look for their own thing: you ask for a letter, you
	agree to it, and then you find it yourself in a folder.
	"""
	name = ask(doc)["proposed"]
	opens = doc.actions.apply(name)["opens"]

	assert opens["file"] == "FILE-1"
	assert opens["kind"] == "Doc"
	assert opens["title"] == "To whom it may concern"
	assert opens["label"]


def test_nothing_waiting_says_where_it_went(doc):
	"""A card nobody has answered has made nothing to open."""
	name = ask(doc)["proposed"]
	kind = doc.actions.get("document.write")
	assert kind.opened(doc.actions._read(doc.kept[name].payload), {"name": ""}) == {}


# --------------------------------------------------------------------------- #
# The prose, as a body
# --------------------------------------------------------------------------- #

def test_a_blank_line_is_a_paragraph_and_a_newline_is_a_break(doc):
	import json

	said = json.loads(doc.body.from_text(LETTER))

	assert said["type"] == "doc"
	assert len(said["content"]) == 3
	# The sign-off is one paragraph of two lines, not two paragraphs: an
	# address block carrying paragraph spacing between every line is not an
	# address block.
	kinds = [one["type"] for one in said["content"][2]["content"]]
	assert kinds == ["text", "hardBreak", "text"]


def test_nothing_written_is_still_a_document_the_editor_can_open(doc):
	assert doc.body.from_text("") == doc.body.blank()
	assert doc.body.from_text("\n\n  \n") == doc.body.blank()


# --------------------------------------------------------------------------- #
# The tool
# --------------------------------------------------------------------------- #

def test_the_tool_cannot_choose_whose_record_it_writes_about(doc):
	"""Bound out of the schema, like every other proposing tool.

	`about_name` is what the document is attached to. A model that could name
	one could attach a letter about this employee to a different employee's
	record, which is a permission check passed on the wrong subject.
	"""
	from oneapp.oneai import proposing

	[filled] = proposing.where(doc.module.tools(), session="s1",
	                           about_doctype="Employee", about_name="HR-EMP-0001")
	for gone in ("session", "about_doctype", "about_name"):
		assert gone not in filled.parameters["properties"]
	assert filled.bound["about_name"] == "HR-EMP-0001"


def test_the_tool_is_the_registry_and_adds_nothing(doc):
	"""A wrapper, like the four in `proposing.py`. A second implementation of
	the check is a second set of bugs and only one of them gets fixed."""
	consts = doc.module.propose_document.func.__code__.co_consts
	assert "document.write" in consts
