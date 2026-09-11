"""The half of linking that is arithmetic.

What is worth pinning here is not "does it find the right record" — that is a
model's job and a model is not in this test run. It is the four properties the
ranking rests on, each of which fails silently if it breaks: a vector survives
the round trip and comes back normalised, the same text is never embedded
twice, two models' vectors are never compared, and what goes into a vector is
only what a reader could have read anyway.
"""

import base64
import math
import sys
import types

import pytest


class Doc(dict):
	def __getattr__(self, name):
		return self.get(name)

	def get(self, name, default=None):
		return dict.get(self, name, default)


class Field(dict):
	def __getattr__(self, name):
		return self.get(name)


class Meta:
	def __init__(self, fields, title="title"):
		self.fields = [Field(one) for one in fields]
		self._title = title

	def get_title_field(self):
		return self._title


@pytest.fixture
def index(stub_frappe, monkeypatch):
	for name in list(sys.modules):
		if name.startswith("oneapp.onespace"):
			del sys.modules[name]

	features = types.ModuleType("oneapp.onespace.ai.features")

	def ai_feature(*a, **kw):
		def decorate(fn):
			def wrapper(*args, **kwargs):
				return fn(wrapper.ai, *args, **kwargs)
			wrapper.ai = lambda *a, **k: {"embedding": [], "credits": 0}
			wrapper.feature = types.SimpleNamespace(key="oneapp.index.embed",
			                                        label="Search index")
			return wrapper
		return decorate

	features.ai_feature = ai_feature
	monkeypatch.setitem(sys.modules, "oneapp.onespace.ai.features", features)

	from oneapp.onespace.ai import index as module

	monkeypatch.setattr(module, "model_in_use", lambda: "gemini-embed")
	return module


# --------------------------------------------------------------------------- #
# A vector survives the round trip, normalised
# --------------------------------------------------------------------------- #

def test_a_vector_comes_back_the_direction_it_went_in(index):
	packed = index.pack([3.0, 4.0])
	found = list(index.unpack(packed))

	assert len(found) == 2
	assert math.isclose(found[0], 0.6, abs_tol=1e-6)
	assert math.isclose(found[1], 0.8, abs_tol=1e-6)


def test_it_is_normalised_at_write_so_the_read_is_one_multiply(index):
	"""Length one at rest is what makes cosine a dot product. Without it every
	row in a two-thousand-row scan pays for two square roots."""
	found = index.unpack(index.pack([7.0, -2.0, 0.5]))
	assert math.isclose(math.sqrt(sum(one * one for one in found)), 1.0, abs_tol=1e-6)


def test_a_zero_vector_does_not_divide_by_zero(index):
	assert list(index.unpack(index.pack([0.0, 0.0]))) == [0.0, 0.0]


def test_it_is_base64_of_float32_and_not_json(index):
	"""Four bytes a dimension rather than eighteen characters. A 768-dimension
	vector as JSON is about 14 kB of Long Text per record."""
	packed = index.pack([1.0, 0.0, 0.0, 0.0])
	assert len(base64.b64decode(packed)) == 16


# --------------------------------------------------------------------------- #
# Nothing is embedded twice for nothing
# --------------------------------------------------------------------------- #

def test_the_same_text_is_not_embedded_again(index, monkeypatch, stub_frappe):
	"""A save that moved a date must not be a metered call. Without this, every
	save on the site is one."""
	calls = []
	monkeypatch.setattr(index, "describe", lambda d, n: ("Project: Marina", "Marina"))
	monkeypatch.setattr(index, "embed", lambda text: calls.append(text) or
	                    {"vector": [1.0], "model": "gemini-embed"})
	stub_frappe.db.get_value = lambda *a, **k: Doc({
		"name": "e1", "digest": index.digest_of("Project: Marina"),
		"model_key": "gemini-embed",
	})

	assert index.remember("Project", "PROJ-1") is False
	assert calls == []


def test_a_vector_from_another_model_is_replaced_rather_than_kept(index, monkeypatch, stub_frappe):
	"""Two models' vectors are not comparable at all, so a workspace that
	changed model has an index that rebuilds rather than one that ranks noise."""
	written = []
	monkeypatch.setattr(index, "describe", lambda d, n: ("Project: Marina", "Marina"))
	monkeypatch.setattr(index, "embed", lambda text: {"vector": [1.0, 0.0],
	                                                  "model": "gemini-embed"})
	stub_frappe.db.get_value = lambda *a, **k: Doc({
		"name": "e1", "digest": index.digest_of("Project: Marina"),
		"model_key": "an-older-model",
	})
	stub_frappe.db.set_value = lambda dt, name, row, **k: written.append(row)

	assert index.remember("Project", "PROJ-1") is True
	assert written and written[0]["model_key"] == "gemini-embed"


def test_a_record_with_nothing_to_say_is_not_embedded(index, monkeypatch):
	monkeypatch.setattr(index, "describe", lambda d, n: ("", ""))
	monkeypatch.setattr(index, "embed", lambda text: pytest.fail("should not be called"))

	assert index.remember("Project", "PROJ-1") is False


# --------------------------------------------------------------------------- #
# What goes into a vector
# --------------------------------------------------------------------------- #

def _described(index, stub_frappe, monkeypatch, fields, values):
	stub_frappe.get_doc = lambda *a, **k: Doc(values)
	stub_frappe.get_meta = lambda *a, **k: Meta(fields)
	stub_frappe.utils.strip_html = lambda v: v
	return index.describe("Project", "PROJ-1")


def test_a_record_is_labelled_lines_rather_than_a_bag_of_values(index, stub_frappe, monkeypatch):
	""""Customer: Al Reem" and "Al Reem" mean different things to an embedding,
	and the first is the one that matches an email naming a customer."""
	text, title = _described(
		index, stub_frappe, monkeypatch,
		[{"fieldname": "title", "fieldtype": "Data", "label": "Name"},
		 {"fieldname": "customer", "fieldtype": "Link", "label": "Customer"}],
		{"title": "Marina tower", "customer": "Al Reem Consultants"},
	)

	assert "Customer: Al Reem Consultants" in text
	assert "Reference: PROJ-1" in text
	assert title == "Marina tower"


def test_a_field_nobody_may_read_is_not_in_the_vector(index, stub_frappe, monkeypatch):
	"""What is searchable is what is readable. A permlevel field in a vector is
	a permlevel field in a ranking."""
	text, _title = _described(
		index, stub_frappe, monkeypatch,
		[{"fieldname": "title", "fieldtype": "Data", "label": "Name"},
		 {"fieldname": "margin_note", "fieldtype": "Small Text",
		  "label": "Margin", "permlevel": 1}],
		{"title": "Marina tower", "margin_note": "we are 40% on this"},
	)

	assert "40%" not in text


def test_amounts_and_dates_are_left_out(index, stub_frappe, monkeypatch):
	"""They are what a filter is for, and put nothing into the meaning of "the
	Al Reem cladding quote"."""
	text, _title = _described(
		index, stub_frappe, monkeypatch,
		[{"fieldname": "title", "fieldtype": "Data", "label": "Name"},
		 {"fieldname": "grand_total", "fieldtype": "Currency", "label": "Total"}],
		{"title": "Marina tower", "grand_total": 412000},
	)

	assert "412000" not in text


def test_a_record_that_cannot_be_read_describes_as_nothing(index, stub_frappe):
	def boom(*a, **k):
		raise Exception("gone")

	stub_frappe.get_doc = boom
	assert index.describe("Project", "PROJ-1") == ("", "")


# --------------------------------------------------------------------------- #
# The scan
# --------------------------------------------------------------------------- #

def _rows(index, stub_frappe, rows):
	stub_frappe.get_all = lambda *a, **k: [Doc(one) for one in rows]


def test_the_nearest_row_comes_back_first(index, stub_frappe):
	_rows(index, stub_frappe, [
		{"reference_doctype": "Project", "reference_name": "PROJ-2",
		 "title": "Al Reem", "vector": index.pack([0.0, 1.0])},
		{"reference_doctype": "Project", "reference_name": "PROJ-1",
		 "title": "Marina", "vector": index.pack([1.0, 0.0])},
	])

	found = index.among(index.pack([1.0, 0.1]))

	assert [one["name"] for one in found] == ["PROJ-1", "PROJ-2"]
	assert found[0]["score"] > found[1]["score"]


def test_a_vector_of_another_length_is_skipped_rather_than_scored(index, stub_frappe):
	"""`zip` over mismatched lengths produces a number, and a number with no
	meaning outranking a real one is the worst kind of wrong here."""
	_rows(index, stub_frappe, [
		{"reference_doctype": "Project", "reference_name": "OLD",
		 "title": "Old", "vector": index.pack([1.0])},
		{"reference_doctype": "Project", "reference_name": "PROJ-1",
		 "title": "Marina", "vector": index.pack([1.0, 0.0])},
	])

	assert [one["name"] for one in index.among(index.pack([1.0, 0.0]))] == ["PROJ-1"]


def test_the_scan_is_filtered_to_the_model_in_use(index, stub_frappe):
	seen = {}
	stub_frappe.get_all = lambda *a, **k: seen.update(k) or []

	index.among(index.pack([1.0, 0.0]))

	assert seen["filters"]["model_key"] == "gemini-embed"
	assert seen["limit_page_length"] == index.MAX_SCAN


def test_asking_for_fewer_gets_fewer(index, stub_frappe):
	_rows(index, stub_frappe, [
		{"reference_doctype": "Project", "reference_name": f"P{n}",
		 "title": f"P{n}", "vector": index.pack([1.0, n / 10])}
		for n in range(6)
	])

	assert len(index.among(index.pack([1.0, 0.0]), limit=2)) == 2


# --------------------------------------------------------------------------- #
# Keeping it up to date
# --------------------------------------------------------------------------- #

def test_a_doctype_no_space_exposes_is_skipped_before_any_query(index, monkeypatch, stub_frappe):
	"""This hook runs on every save on the site. A query per save to learn that
	this one is a Version row is a query per save."""
	monkeypatch.setattr(index, "indexable", lambda: {"Project"})
	monkeypatch.setattr(index, "enabled", lambda: pytest.fail("asked too late"))

	index.on_save(Doc({"doctype": "Version", "name": "v1"}))
	assert not stub_frappe.enqueued


def test_one_job_per_record_in_flight(index, monkeypatch, stub_frappe):
	"""Ten saves in a minute is one embedding."""
	monkeypatch.setattr(index, "indexable", lambda: {"Project"})
	monkeypatch.setattr(index, "enabled", lambda: True)

	index.on_save(Doc({"doctype": "Project", "name": "PROJ-1"}))

	_method, job = stub_frappe.enqueued[-1]
	assert job["job_id"] == "ai-index::Project::PROJ-1"
	assert job["deduplicate"] is True
	assert job["enqueue_after_commit"] is True


def test_indexing_a_record_never_raises_into_the_save(index, monkeypatch, stub_frappe):
	"""An index is not the record."""
	monkeypatch.setattr(index, "remember", lambda d, n: (_ for _ in ()).throw(Exception("nope")))
	index.refresh("Project", "PROJ-1")


def test_a_build_chains_rather_than_walking_a_whole_site(index, monkeypatch, stub_frappe):
	"""A pass that tried to do forty thousand records is one job holding a
	worker for an hour."""
	monkeypatch.setattr(index, "enabled", lambda: True)
	monkeypatch.setattr(index, "indexable", lambda: {"Project"})
	monkeypatch.setattr(index, "refresh", lambda d, n: None)
	stub_frappe.get_all = lambda *a, **k: [f"PROJ-{n}" for n in range(index.BATCH)]

	answer = index.build()

	assert answer["done"] is False
	assert answer["after"] == f"Project::PROJ-{index.BATCH - 1}"
	assert stub_frappe.enqueued[-1][1]["after"] == answer["after"]


def test_a_build_that_caught_up_stops(index, monkeypatch, stub_frappe):
	"""Nothing wakes this again. A build starts because somebody switched the
	feature on or pressed Rebuild."""
	monkeypatch.setattr(index, "enabled", lambda: True)
	monkeypatch.setattr(index, "indexable", lambda: {"Project"})
	monkeypatch.setattr(index, "refresh", lambda d, n: None)
	stub_frappe.get_all = lambda *a, **k: ["PROJ-1"]

	answer = index.build()

	assert answer["done"] is True
	assert not stub_frappe.enqueued


def test_a_build_does_nothing_where_the_feature_is_off(index, monkeypatch):
	monkeypatch.setattr(index, "enabled", lambda: False)
	assert index.build() == {"ok": False, "reason": "disabled"}
