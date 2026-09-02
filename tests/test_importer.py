"""Bringing a customer's data with them.

What is checked here is the part that makes this an engine rather than a
script: that a second run updates rather than duplicates, that a link resolves
to what an earlier step made, that a watermark makes the second run a delta,
that a row which will not save is kept rather than losing the run, and that a
rehearsal writes nothing.

The network is not here. `fetch` is one function and its job is one GET; what
is worth pinning is everything the rows are put through after it.
"""

import json

import pytest


@pytest.fixture
def importer(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import importer as module

	return module


# --------------------------------------------------------------------------- #
# The field map
# --------------------------------------------------------------------------- #


def test_a_field_is_copied_across(importer):
	made = importer.build({"party": "Halloway & Co"}, {"customer_name": {"from": "party"}}, "P")
	assert made == {"customer_name": "Halloway & Co"}


def test_the_short_form_means_the_same(importer):
	"""`{"customer_name": "party"}` is what somebody writes first."""
	assert importer.build({"party": "X"}, {"customer_name": "party"}, "P") == {"customer_name": "X"}


def test_a_value_can_be_mapped_on_the_way(importer):
	rule = {"customer_group": {"from": "type", "values": {"Client": "Commercial"}}}
	assert importer.build({"type": "Client"}, rule, "P") == {"customer_group": "Commercial"}


def test_an_unmapped_value_falls_to_the_default(importer):
	rule = {"customer_group": {"from": "type", "values": {"Client": "Commercial"},
	                           "default": "All Customer Groups"}}
	made = importer.build({"type": "Consultant"}, rule, "P")
	assert made == {"customer_group": "All Customer Groups"}


def test_a_constant_needs_no_source_field(importer):
	assert importer.build({}, {"company": {"const": "RUA"}}, "P") == {"company": "RUA"}


def test_a_link_resolves_to_what_an_earlier_step_made(importer, stub_frappe):
	stub_frappe.db.values[("Import Identity", "target_name")] = "CUST-0007"
	made = importer.build({"party": "Halloway & Co"},
	                      {"customer": {"from": "party", "link": "RUA Party"}}, "P")
	assert made == {"customer": "CUST-0007"}


def test_a_link_that_resolves_to_nothing_is_an_error_not_a_blank(importer):
	"""The failure this refuses is the one nobody finds: a third of a report's
	rows missing, months later, because a link quietly did not arrive."""
	with pytest.raises(importer.Unresolved) as raised:
		importer.build({"party": "Halloway & Co"},
		               {"customer": {"from": "party", "link": "RUA Party"}}, "P")
	# And it says which step to move, because that is the whole diagnosis.
	assert "RUA Party" in str(raised.value)


def test_an_empty_link_is_left_alone(importer):
	"""A source row with no party is a source row with no party."""
	made = importer.build({"party": ""}, {"customer": {"from": "party", "link": "RUA Party"}}, "P")
	assert made == {}


# --------------------------------------------------------------------------- #
# Where a source may be
# --------------------------------------------------------------------------- #


class Source:
	def __init__(self, url):
		self.base_url = url


@pytest.mark.parametrize("url", [
	"http://old.example.com",       # credentials in the clear
	"https://localhost",            # this machine
	"https://site.localhost",
	"https://169.254.169.254",      # a metadata service
	"https://10.0.0.4",             # the network next door
	"https://old.example.com/app",  # a path, which is not a site
])
def test_a_source_has_to_be_somewhere_sensible(importer, stub_frappe, url):
	with pytest.raises(stub_frappe.ValidationError):
		importer._endpoint(Source(url))


def test_an_ordinary_site_is_fine(importer):
	assert importer._endpoint(Source("https://old.example.com/")) == "https://old.example.com"


# --------------------------------------------------------------------------- #
# Writing one row
#
# The stub has no ORM, so what these inject is the document layer and what they
# check is the decision made around it: whether this row is a record that
# exists, and whether a rehearsal is allowed to keep anything.
# --------------------------------------------------------------------------- #


class Doc(dict):
	"""Just enough of a Frappe document to be inserted or saved."""

	def __init__(self, values=None, name="NEW-1"):
		super().__init__(values or {})
		self.name = name
		self.saved = 0
		self.inserted = 0
		self.validated = 0

	def insert(self, **k):
		self.inserted += 1
		return self

	def save(self, **k):
		self.saved += 1
		return self

	def update(self, values):
		super().update(values)

	def run_method(self, method):
		self.validated += 1


class Plan:
	name = "P"


class Step:
	name = "STEP-1"
	source_doctype = "RUA Party"
	target_doctype = "Customer"
	field_map = '{"customer_name": "party"}'
	filters = None
	watermark = None
	enabled = 1


@pytest.fixture
def written(importer, stub_frappe, monkeypatch):
	"""Records `_write` made, with identity writing stubbed out."""
	made = []

	def get_doc(what, name=None):
		if isinstance(what, dict):
			doc = Doc(what)
			made.append(doc)
			return doc
		doc = Doc({}, name=name)
		made.append(doc)
		return doc

	monkeypatch.setattr(stub_frappe, "get_doc", get_doc)
	monkeypatch.setattr(importer, "_remember", lambda *a: None)
	return made


def test_a_row_nobody_has_seen_is_inserted(importer, written, monkeypatch):
	monkeypatch.setattr(importer, "resolve", lambda *a: None)
	what = importer._write(Plan(), Step(), {"name": "Halloway & Co"}, {"customer_name": "X"}, 0)
	assert what == "created"
	assert written[0].inserted == 1


def test_the_second_run_updates_rather_than_duplicating(importer, written, stub_frappe, monkeypatch):
	"""The property the whole identity table exists for."""
	monkeypatch.setattr(importer, "resolve", lambda *a: "CUST-0007")
	stub_frappe.db.records[("Customer", "CUST-0007")] = True

	what = importer._write(Plan(), Step(), {"name": "Halloway & Co"}, {"customer_name": "X"}, 0)
	assert what == "updated"
	assert written[0].saved == 1
	assert written[0].inserted == 0


def test_a_target_deleted_since_is_made_again(importer, written, stub_frappe, monkeypatch):
	"""An identity pointing at a record somebody removed here. Making it again
	beats saving onto a name that is not there."""
	monkeypatch.setattr(importer, "resolve", lambda *a: "CUST-0007")
	stub_frappe.db.records[("Customer", "CUST-0007")] = None

	assert importer._write(Plan(), Step(), {"name": "H"}, {"customer_name": "X"}, 0) == "created"


def test_a_rehearsal_validates_and_keeps_nothing(importer, written, monkeypatch):
	"""The counts a dry run reports are real; the records are not."""
	monkeypatch.setattr(importer, "resolve", lambda *a: None)
	what = importer._write(Plan(), Step(), {"name": "H"}, {"customer_name": "X"}, 1)

	assert what == "created"
	assert written[0].validated == 1
	assert written[0].inserted == 0
	assert written[0].saved == 0


# --------------------------------------------------------------------------- #
# One step, page by page
# --------------------------------------------------------------------------- #


class Run:
	name = "IMP-1"
	dry_run = 0


class RunStep:
	name = "RS-1"

	def __init__(self):
		self.marks = {}

	def set(self, key, value):
		self.marks[key] = value


@pytest.fixture
def stepped(importer, stub_frappe, monkeypatch):
	"""`_step` with the network and the writes replaced, so what is left to
	watch is the paging, the counting and the watermark."""
	seen = {"fetched": [], "wrote": [], "issues": []}

	monkeypatch.setattr(importer, "_write", lambda *a: "created")
	monkeypatch.setattr(importer, "_issue",
	                    lambda run, step, said, raised: seen["issues"].append(said["name"]))
	monkeypatch.setattr(importer, "_mark", lambda row, values: row.marks.update(values))
	return seen


def test_a_step_walks_every_page(importer, stepped, monkeypatch):
	"""Two full pages and a short one. The short page is what ends it — asking
	again after it is a request for nothing."""
	pages = [[{"name": f"r{i}", "modified": "2026-01-01 00:00:00"} for i in range(importer.BATCH)],
	         [{"name": f"s{i}", "modified": "2026-01-02 00:00:00"} for i in range(importer.BATCH)],
	         [{"name": "last", "modified": "2026-01-03 00:00:00"}]]
	calls = []

	def fetch(source, doctype, filters, start, length):
		calls.append(start)
		return pages.pop(0) if pages else []

	monkeypatch.setattr(importer, "fetch", fetch)
	row = RunStep()
	importer._step(Run(), Plan(), None, Step(), row)

	assert calls == [0, importer.BATCH, importer.BATCH * 2]
	assert row.marks["seen"] == importer.BATCH * 2 + 1
	assert row.marks["created"] == importer.BATCH * 2 + 1
	assert row.marks["status"] == "Done"


def test_the_watermark_ends_at_the_newest_row_seen(importer, stepped, stub_frappe, monkeypatch):
	monkeypatch.setattr(importer, "fetch", lambda *a: [
		{"name": "a", "modified": "2026-01-01 00:00:00"},
		{"name": "b", "modified": "2026-03-09 12:00:00"},
	] if a[3] == 0 else [])

	row = RunStep()
	importer._step(Run(), Plan(), None, Step(), row)

	assert row.marks["watermark_to"] == "2026-03-09 12:00:00"
	# And it is written back to the plan's step, which is what makes the *next*
	# run a delta rather than the whole thing again.
	assert ("Import Step", "STEP-1", "watermark", "2026-03-09 12:00:00") in stub_frappe.db.writes


def test_a_second_run_asks_only_for_what_changed(importer, stepped, monkeypatch):
	"""And asks with `>=`, not `>`. Rows sharing the boundary's exact `modified`
	would otherwise be dropped — a second of records lost at a page edge, with
	nothing to say so. Re-reading them costs an update apiece."""
	asked = {}

	def fetch(source, doctype, filters, start, length):
		asked["filters"] = filters
		return []

	monkeypatch.setattr(importer, "fetch", fetch)
	step = Step()
	step.watermark = "2026-03-09 12:00:00"
	importer._step(Run(), Plan(), None, step, RunStep())

	assert asked["filters"] == [["RUA Party", "modified", ">=", "2026-03-09 12:00:00"]]


def test_a_row_that_will_not_save_is_kept_and_the_rest_go_on(importer, stepped, monkeypatch):
	"""One bad row is a row to work through later, not the end of the run."""
	monkeypatch.setattr(importer, "fetch", lambda *a: [
		{"name": "good", "modified": "2026-01-01 00:00:00"},
		{"name": "bad", "modified": "2026-01-02 00:00:00"},
	] if a[3] == 0 else [])

	def write(plan, step, said, made, dry_run):
		if said["name"] == "bad":
			raise ValueError("Customer Group is required")
		return "created"

	monkeypatch.setattr(importer, "_write", write)
	row = RunStep()
	importer._step(Run(), Plan(), None, Step(), row)

	assert stepped["issues"] == ["bad"]
	assert row.marks["created"] == 1
	assert row.marks["failed"] == 1
	assert row.marks["status"] == "Done"


def test_a_rehearsal_moves_no_watermark(importer, stepped, stub_frappe, monkeypatch):
	"""Otherwise a dry run would make the real one skip everything it read."""
	monkeypatch.setattr(importer, "fetch", lambda *a: [
		{"name": "a", "modified": "2026-01-01 00:00:00"}] if a[3] == 0 else [])

	run = Run()
	run.dry_run = 1
	importer._step(run, Plan(), None, Step(), RunStep())

	assert not [w for w in stub_frappe.db.writes if w[2] == "watermark"]
