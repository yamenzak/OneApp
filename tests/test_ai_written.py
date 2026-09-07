"""Which values on a record a model wrote.

The mark itself is one row and needs no test. What needs one is the three
things around it, because each is a way the icon becomes a lie:

* it must **not** be dropped by the save that writes it, or the mark and the
  value can never be written together;
* it must be dropped when a person rewrites *that* field, and kept when they
  rewrite a different one;
* the hook is on `*`, so it must cost nothing on the doctypes — every save on
  the site, forever — that no model has ever written to.
"""

import types

import pytest


class Store:
	"""The rows, as `frappe.get_all`/`db.exists`/`delete_doc` see them."""

	def __init__(self, rows=()):
		self.rows = [dict(r) for r in rows]
		self.queries = 0

	def get_all(self, doctype, filters=None, fields=None, pluck=None,
	            distinct=False, **kwargs):
		self.queries += 1
		found = [
			r for r in self.rows
			if all(r.get(k) == v for k, v in (filters or {}).items())
		]
		if pluck:
			values = [r.get(pluck) for r in found]
			return list(dict.fromkeys(values)) if distinct else values
		return [types.SimpleNamespace(**r) for r in found]

	def exists(self, doctype, filters):
		found = [
			r for r in self.rows
			if all(r.get(k) == v for k, v in filters.items())
		]
		return found[0]["name"] if found else None

	def delete(self, doctype, name, **kwargs):
		self.rows = [r for r in self.rows if r.get("name") != name]


def row(doctype="ToDo", name="TASK-1", fieldname="description", **extra):
	return {
		"name": f"mark-{fieldname}",
		"reference_doctype": doctype,
		"reference_name": name,
		"fieldname": fieldname,
		"feature_key": "oneapp.chat.workspace",
		"model_key": "google-ai-studio:flash",
		"asked_by": "ada@example.com",
		"creation": "2026-01-01 00:00:00",
		**extra,
	}


@pytest.fixture
def written(monkeypatch):
	from oneapp.oneapp_core.ai import written as module

	monkeypatch.setattr(module.frappe, "session", types.SimpleNamespace(user="ada@example.com"))
	monkeypatch.setattr(module.frappe, "flags", {})
	module.frappe.cache.delete_value(module.MARKED_DOCTYPES)
	return module


def wire(written, monkeypatch, store):
	monkeypatch.setattr(written.frappe, "get_all", store.get_all)
	monkeypatch.setattr(written.frappe.db, "exists", store.exists)
	monkeypatch.setattr(written.frappe, "delete_doc", store.delete, raising=False)
	written.frappe.cache.delete_value(written.MARKED_DOCTYPES)
	return store


def saved(doctype="ToDo", name="TASK-1", before=None, **now):
	"""A document mid-save, as `on_update` receives it."""
	was = types.SimpleNamespace(get=lambda field: (before or {}).get(field))
	return types.SimpleNamespace(
		doctype=doctype, name=name,
		get=lambda field: now.get(field),
		get_doc_before_save=lambda: was,
	)


# --------------------------------------------------------------------------- #
# Reading a mark back
# --------------------------------------------------------------------------- #

def test_a_mark_names_the_model_the_way_the_workspace_sees_it(written, monkeypatch):
	"""The stored key is not what a reader is owed.

	`google-ai-studio:flash` is how the catalogue is keyed. "Flash" is what the
	model picker calls it, so it is what the tooltip has to say.
	"""
	wire(written, monkeypatch, Store([row()]))
	monkeypatch.setattr(
		"oneapp.oneapp_core.ai.settings.catalogue",
		lambda: [{"model_key": "google-ai-studio:flash", "display_name": "Flash"}],
	)

	marks = written.written("ToDo", "TASK-1")

	assert marks["description"]["model"] == "Flash"
	assert marks["description"]["by"] == "ada@example.com"


def test_a_document_with_no_marks_asks_the_catalogue_nothing(written, monkeypatch):
	wire(written, monkeypatch, Store())
	monkeypatch.setattr(
		"oneapp.oneapp_core.ai.settings.catalogue",
		lambda: pytest.fail("the catalogue was read for a document with no marks"),
	)

	assert written.written("ToDo", "TASK-1") == {}


# --------------------------------------------------------------------------- #
# When a mark goes
# --------------------------------------------------------------------------- #

def test_the_field_a_person_rewrote_stops_being_the_models(written, monkeypatch):
	store = wire(written, monkeypatch, Store([row()]))

	written.forget_changed(saved(
		before={"description": "What the model wrote"},
		description="What Ada wrote instead",
	))

	assert store.rows == []


def test_a_save_that_touched_another_field_leaves_the_mark_alone(written, monkeypatch):
	store = wire(written, monkeypatch, Store([row()]))

	written.forget_changed(saved(
		before={"description": "What the model wrote", "status": "Open"},
		description="What the model wrote", status="Closed",
	))

	assert len(store.rows) == 1


def test_the_save_that_writes_the_mark_does_not_clear_it(written, monkeypatch):
	"""Otherwise a mark could never be written at all.

	The value did change and the document was saved, which is exactly what a
	person rewriting it looks like. The flag is the only thing that tells them
	apart.
	"""
	store = wire(written, monkeypatch, Store([row()]))
	written.frappe.flags[written.WRITING] = True

	written.forget_changed(saved(
		before={"description": "the old text"}, description="what the model wrote",
	))

	assert len(store.rows) == 1


def test_the_marks_go_when_the_document_goes(written, monkeypatch):
	store = wire(written, monkeypatch, Store([row(), row(fieldname="reference_name")]))

	written.forget_deleted(saved())

	assert store.rows == []


# --------------------------------------------------------------------------- #
# What the hook on `*` costs
# --------------------------------------------------------------------------- #

def test_a_doctype_nothing_has_ever_marked_costs_no_query_at_all(written, monkeypatch):
	"""The hook is on `*`. Every save on the site pays whatever this costs.

	One query answers it for the whole site and is cached, so the second save
	of an unmarked doctype — and the millionth — asks nothing.
	"""
	store = wire(written, monkeypatch, Store([row()]))

	written.forget_changed(saved(doctype="Email Queue Recipient"))
	written.forget_changed(saved(doctype="Sales Invoice", name="SINV-1"))
	written.forget_changed(saved(doctype="Sales Invoice", name="SINV-2"))

	assert store.queries == 1
	assert len(store.rows) == 1


def test_writing_a_mark_makes_its_doctype_known_again(written, monkeypatch):
	"""The cache is only safe if writing a mark invalidates it.

	Without this the first save after a workspace's first mark would still see
	the doctype as unmarked, and the mark would outlive the value.
	"""
	store = wire(written, monkeypatch, Store())
	monkeypatch.setattr(
		written.frappe, "get_doc",
		lambda values: types.SimpleNamespace(
			insert=lambda **kw: store.rows.append(row(**{
				k: v for k, v in values.items() if k != "doctype"
			})),
		),
	)

	assert written._marked_doctypes() == set()
	written.mark("ToDo", "TASK-1", "description")
	assert written._marked_doctypes() == {"ToDo"}
