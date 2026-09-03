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
import types

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

	def __init__(self, values=None, name="NEW-1", doctype="Customer"):
		super().__init__(values or {})
		self.name = name
		self.doctype = doctype
		self.saved = 0
		self.inserted = 0
		self.validated = 0
		# What a rehearsal did to it, in order. Named rather than counted:
		# the property worth pinning is *which* of insert's checks ran, and
		# the one that matters is the link check.
		self.rehearsed = []
		self.flags = types.SimpleNamespace()

	def insert(self, **k):
		self.inserted += 1
		return self

	def save(self, **k):
		self.saved += 1
		return self

	def update(self, values):
		super().update(values)

	def run_method(self, method):
		self.rehearsed.append(method)
		self.validated += 1

	def set(self, key, value):
		self[key] = value

	def _set_defaults(self):
		self.rehearsed.append("defaults")

	def set_user_and_timestamp(self):
		self.rehearsed.append("stamped")

	def set_docstatus(self):
		self.rehearsed.append("docstatus")

	def check_permission(self, what):
		self.rehearsed.append(f"may {what}")

	def check_if_latest(self):
		self.rehearsed.append("latest")

	def validate_higher_perm_levels(self):
		self.rehearsed.append("perm levels")

	def _validate_links(self):
		self.rehearsed.append("links")

	def run_before_save_methods(self):
		self.rehearsed.append("before save")
		self.validated += 1

	def _validate(self):
		self.rehearsed.append("mandatory and selects")


class Plan:
	name = "P"


class Step:
	name = "STEP-1"
	source_doctype = "RUA Party"
	target_doctype = "Customer"
	field_map = '{"customer_name": "party"}'
	filters = None
	fan_out = None
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
	what = importer._write(Plan(), Step(), "Halloway & Co", {"name": "Halloway & Co"}, {"customer_name": "X"})
	assert what == "created"
	assert written[0].inserted == 1


def test_the_second_run_updates_rather_than_duplicating(importer, written, stub_frappe, monkeypatch):
	"""The property the whole identity table exists for."""
	monkeypatch.setattr(importer, "resolve", lambda *a: "CUST-0007")
	stub_frappe.db.records[("Customer", "CUST-0007")] = True

	what = importer._write(Plan(), Step(), "Halloway & Co", {"name": "Halloway & Co"}, {"customer_name": "X"})
	assert what == "updated"
	assert written[0].saved == 1
	assert written[0].inserted == 0


def test_a_target_deleted_since_is_made_again(importer, written, stub_frappe, monkeypatch):
	"""An identity pointing at a record somebody removed here. Making it again
	beats saving onto a name that is not there."""
	monkeypatch.setattr(importer, "resolve", lambda *a: "CUST-0007")
	stub_frappe.db.records[("Customer", "CUST-0007")] = None

	assert importer._write(Plan(), Step(), "H", {"name": "H"}, {"customer_name": "X"}) == "created"


def test_two_steps_off_one_source_doctype_both_run(importer, stub_frappe, monkeypatch):
	"""The run's rows pair with the plan's by position, not by name.

	Keyed by source doctype, a party table split into customers and suppliers —
	the ordinary reason to have two steps off one — collapses to whichever came
	last, and the other never runs at all. The run says Done, the counts look
	like numbers, and seventy-five customers were never looked at.
	"""
	ran = []
	monkeypatch.setattr(importer, "_step",
	                    lambda run, plan, source, step, row, held=None: ran.append(step.target_doctype))

	def plan_steps():
		return [
			types.SimpleNamespace(source_doctype="RUA Party", target_doctype="Customer",
			                      enabled=1),
			types.SimpleNamespace(source_doctype="RUA Party", target_doctype="Supplier",
			                      enabled=1),
		]

	run = types.SimpleNamespace(
		name="IMP-1", plan="P", dry_run=0, steps=[
			types.SimpleNamespace(name="RS-1", source_doctype="RUA Party",
			                      target_doctype="Customer",
			                      seen=0, created=0, updated=0, failed=0),
			types.SimpleNamespace(name="RS-2", source_doctype="RUA Party",
			                      target_doctype="Supplier",
			                      seen=0, created=0, updated=0, failed=0),
		],
		db_set=lambda *a, **k: None, reload=lambda: None,
	)
	docs = {
		"Import Run": run,
		"Import Plan": types.SimpleNamespace(name="P", source="S", steps=plan_steps()),
		"Import Source": types.SimpleNamespace(name="S"),
	}
	monkeypatch.setattr(stub_frappe, "get_doc", lambda what, name=None: docs[what])

	importer.execute("IMP-1")

	assert ran == ["Customer", "Supplier"]


def test_an_identity_may_not_be_repointed_at_another_doctype(importer, stub_frappe):
	"""One source row claimed by two steps.

	Rewriting the identity would repoint every link that already resolved
	through it — the payments of a party that became a Customer would silently
	start naming the Supplier it became second. The row fails instead, and the
	plan's filters are what gets fixed.
	"""
	stub_frappe.db.values[("Import Identity", ("name", "target_doctype"))] = (
		"IMP-ID-1", "Supplier"
	)

	with pytest.raises(stub_frappe.ValidationError, match="two steps claim it"):
		importer._remember(Plan(), Step(), "Halloway & Co", "CUST-0007")


def test_a_rehearsal_is_the_real_run_thrown_away(importer, written, stub_frappe, monkeypatch):
	"""A dry run inserts exactly like a real one, and `execute` rolls it back.

	Validating a document in isolation was the old rehearsal and it could not
	answer the question that matters: a link to a record an earlier step would
	have made. Every step after the first reported failures that only the
	rehearsal had. So the rehearsal writes, resolves, and is thrown away.
	"""
	monkeypatch.setattr(importer, "resolve", lambda *a: None)

	assert importer._write(Plan(), Step(), "H", {"name": "H"}, {"customer_name": "X"}) == "created"
	assert written[0].inserted == 1


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
	                    lambda run, step, said, raised, held=None:
	                        seen["issues"].append(said["name"]))
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

	def write(plan, step, key, said, made, *a, **k):
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


def test_a_row_that_will_not_save_is_undone_to_its_own_savepoint(importer, stepped,
                                                                stub_frappe, monkeypatch):
	"""What a failing row costs: itself, and nothing else.

	`_issue` used to roll the connection back before writing, which threw away
	every row written since the last commit — up to a hundred and ninety-nine
	records already counted as created and then quietly gone. A savepoint per
	row undoes the one that failed.
	"""
	monkeypatch.setattr(importer, "fetch", lambda *a: [
		{"name": "good", "modified": "2026-01-01 00:00:00"},
		{"name": "bad", "modified": "2026-01-02 00:00:00"},
		{"name": "also good", "modified": "2026-01-03 00:00:00"},
	] if a[3] == 0 else [])

	def write(plan, step, key, said, made, *a, **k):
		if key == "bad":
			raise ValueError("no")
		return "created"

	monkeypatch.setattr(importer, "_write", write)
	row = RunStep()
	importer._step(Run(), Plan(), None, Step(), row)

	assert row.marks["created"] == 2
	assert row.marks["failed"] == 1
	# One mark per row, and the failing one is what was rolled back to.
	assert len(stub_frappe.db.savepoints) == 3
	assert len(stub_frappe.db.rollbacks) == 1
	assert stub_frappe.db.rollbacks[0] in stub_frappe.db.savepoints
	assert len(stub_frappe.db.released) == 2


def test_a_second_run_compares_the_watermark_with_what_arrives(importer, stepped,
                                                              monkeypatch):
	"""The run that matters, and the one that had never happened.

	A watermark comes back out of the database as a datetime and a row's
	`modified` arrives from the API as text. `max` over the two raises, so the
	first run worked every time and the second died before it read a row.
	"""
	import datetime

	monkeypatch.setattr(importer, "fetch", lambda *a: [
		{"name": "a", "modified": "2026-03-09 12:00:00"},
	] if a[3] == 0 else [])

	step = Step()
	step.watermark = datetime.datetime(2026, 1, 1)
	row = RunStep()

	importer._step(Run(), Plan(), None, step, row)

	assert row.marks["watermark_to"] == "2026-03-09 12:00:00"
	assert row.marks["created"] == 1


def test_a_rehearsal_moves_no_watermark(importer, stepped, stub_frappe, monkeypatch):
	"""Otherwise a dry run would make the real one skip everything it read."""
	monkeypatch.setattr(importer, "fetch", lambda *a: [
		{"name": "a", "modified": "2026-01-01 00:00:00"}] if a[3] == 0 else [])

	run = Run()
	run.dry_run = 1
	importer._step(run, Plan(), None, Step(), RunStep())

	assert not [w for w in stub_frappe.db.writes if w[2] == "watermark"]


# --------------------------------------------------------------------------- #
# Checking a plan before running it
#
# A fourteen-step field map is a document nobody can read for correctness, and
# every mistake in one is quiet: a renamed source field drops a column, a link
# resolved too early files an issue per row. These are the ones worth refusing
# before a run rather than reporting after one.
# --------------------------------------------------------------------------- #


class Row:
	def __init__(self, **kw):
		self.__dict__.update(kw)


def check_step(importer, monkeypatch, field_map, *, rows=None, ours=None, made=(),
               filters=None, seen=None):
	monkeypatch.setattr(importer, "_their_fields",
	                    lambda source, dt, filters, problems: (
	                        set(rows[0]) if rows else set(), rows))
	monkeypatch.setattr(importer, "_our_fields", lambda dt, problems: ours)
	step = Row(source_doctype="RUA Party", target_doctype="Customer",
	           field_map=__import__("json").dumps(field_map), fan_out=None, enabled=1,
	           filters=__import__("json").dumps(filters or []))
	return importer._check_step(None, Row(name="P"), step, set(made), seen)


def test_a_source_field_that_is_gone_is_a_problem(importer, monkeypatch):
	found = check_step(importer, monkeypatch, {"customer_name": {"from": "partyy"}},
	                   rows=[{"party": "X"}], ours={"customer_name"})
	assert any("no field `partyy`" in p for p in found["problems"])


def test_a_target_field_that_does_not_exist_is_a_problem(importer, monkeypatch):
	found = check_step(importer, monkeypatch, {"custmer_name": {"from": "party"}},
	                   rows=[{"party": "X"}], ours={"customer_name"})
	assert any("no field `custmer_name`" in p for p in found["problems"])


def test_a_link_to_a_later_step_is_a_problem_not_a_warning(importer, monkeypatch):
	"""It finds nothing on every row, and the run files one issue per record
	rather than saying the plan is in the wrong order."""
	found = check_step(importer, monkeypatch,
	                   {"customer": {"from": "party", "link": "RUA Project"}},
	                   rows=[{"party": "X"}], ours={"customer"}, made=())
	assert any("runs later" in p for p in found["problems"])


def test_a_link_to_an_earlier_step_is_fine(importer, monkeypatch):
	found = check_step(importer, monkeypatch,
	                   {"customer": {"from": "party", "link": "RUA Project"}},
	                   rows=[{"party": "X"}], ours={"customer"}, made=("RUA Project",))
	assert found["problems"] == []


def test_a_value_map_that_misses_what_is_in_the_column_warns(importer, monkeypatch):
	"""The quiet one: somebody maps the values they remember rather than the
	values that are there, and the rest cross over as-is."""
	found = check_step(
		importer, monkeypatch,
		{"customer_group": {"from": "type", "values": {"Client": "Commercial"}}},
		rows=[{"type": "Client"}, {"type": "Consultant"}, {"type": "Supplier"}],
		ours={"customer_group"},
	)
	assert found["problems"] == []
	assert any("Consultant" in w and "Supplier" in w for w in found["warnings"])


def test_a_default_makes_the_unmapped_values_a_decision(importer, monkeypatch):
	found = check_step(
		importer, monkeypatch,
		{"customer_group": {"from": "type", "values": {"Client": "Commercial"},
		                    "default": "All Customer Groups"}},
		rows=[{"type": "Client"}, {"type": "Consultant"}],
		ours={"customer_group"},
	)
	assert found["warnings"] == []


def test_a_field_map_that_is_not_json_says_so_rather_than_raising(importer, monkeypatch):
	step = Row(source_doctype="RUA Party", target_doctype="Customer",
	           field_map="{not json", fan_out=None, enabled=1, filters="[]")
	found = importer._check_step(None, Row(name="P"), step, set())
	assert found["problems"] and "not JSON" in found["problems"][0]


def test_the_sample_is_taken_through_the_step_own_filters(importer, monkeypatch):
	"""A step that excludes a value is not a step that has to map it.

	The check reads what a column holds by reading rows, so which rows it reads
	decides what it complains about. Sampling unfiltered means a step whose
	filters already answer a value gets told to answer it again — and a check
	that reports things that are not wrong is one people stop reading.
	"""
	asked = {}

	def fetch(source, doctype, filters, start, length):
		asked["filters"] = filters
		return [{"type": "Client"}]

	monkeypatch.setattr(importer, "fetch", fetch)
	monkeypatch.setattr(importer, "_our_fields", lambda dt, problems: {"customer_group"})
	step = Row(source_doctype="RUA Party", target_doctype="Customer",
	           field_map='{"customer_group": {"from": "type", '
	                     '"values": {"Client": "Commercial"}}}',
	           fan_out=None, enabled=1,
	           filters='[["RUA Party", "type", "in", ["Client"]]]')

	found = importer._check_step(None, Row(name="P"), step, set())

	assert asked["filters"] == [["RUA Party", "type", "in", ["Client"]]]
	assert found["warnings"] == []


def test_two_steps_claiming_one_row_of_a_shared_source_warn(importer, monkeypatch):
	"""`resolve` is keyed on the source doctype, not the target.

	A row caught by both steps resolves to whichever ran last, so every link
	through it silently names the wrong record. The check asks the rows rather
	than the schema, because the schema cannot answer it.
	"""
	found = check_step(importer, monkeypatch, {"customer_name": {"from": "party"}},
	                   rows=[{"name": "P-1", "party": "X"}], ours={"customer_name"},
	                   made=["RUA Party"], seen={("RUA Party", "Customer"): {"P-1"}})
	assert any("claimed by an earlier step" in w for w in found["warnings"])
	assert found["problems"] == []


def test_a_shared_source_with_disjoint_filters_is_silent(importer, monkeypatch):
	"""The ordinary case, and the reason the warning is not about the schema.

	A party table split into customers and suppliers is two steps off one
	doctype and entirely correct. Warning about it every run is how a check
	teaches people to skim its output.
	"""
	found = check_step(importer, monkeypatch, {"customer_name": {"from": "party"}},
	                   rows=[{"name": "P-2", "party": "X"}], ours={"customer_name"},
	                   made=["RUA Party"], seen={("RUA Party", "Customer"): {"P-2 elsewhere"}})
	assert found["warnings"] == []


# --------------------------------------------------------------------------- #
# The plan this app ships
# --------------------------------------------------------------------------- #


def test_a_shipped_plan_is_offered_only_where_its_space_is(importer, stub_frappe, monkeypatch):
	"""A shipped plan is one customer's own migration.

	Offering it to every workspace would be offering to fill their books with a
	stranger's — and the button that does it writes custom fields and seed
	records before it reads a row.
	"""
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True)
	monkeypatch.setattr(stub_frappe, "get_all", lambda *a, **k: [])

	import sys
	import types

	sync = types.ModuleType("oneapp.oneapp_core.sync")
	sync.state = lambda: {"spaces": [{"space_code": "zzmock"}]}
	monkeypatch.setitem(sys.modules, "oneapp.oneapp_core.sync", sync)

	assert importer.console()["shipped"] == []

	sync.state = lambda: {"spaces": [{"space_code": "rua"}, {"space_code": "zzmock"}]}
	offered = importer.console()["shipped"]

	assert [one["key"] for one in offered] == ["rua"]
	# What the card says before anybody presses it: how much it will bring and
	# how much it will add to this site's own schema to hold it.
	assert offered[0]["steps"] == 12
	assert offered[0]["fields"] > 0


def test_the_rua_plan_resolves_every_link_backwards(stub_frappe):
	"""Checked without a network and without a bench, because the ordering is a
	property of the declaration rather than of either site."""
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core.plans import rua

	made = set()
	for step in rua.STEPS:
		for target, rule in step["map"].items():
			if isinstance(rule, dict) and rule.get("link"):
				assert rule["link"] in made, (
					f"{step['source']}.{target} resolves against {rule['link']}, "
					"which the plan runs later"
				)
		made.add(step["source"])


def test_every_rua_step_says_what_it_is_for(stub_frappe):
	"""A field map is unreadable without one. The `why` is what somebody looking
	at a fourteen-step plan a year from now has."""
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core.plans import rua

	for step in rua.STEPS:
		assert len(step.get("why", "")) > 20, f"{step['source']} says nothing"
		assert step["map"], f"{step['source']} maps nothing"


# --------------------------------------------------------------------------- #
# One row over there, many rows here
#
# RUA keeps a month of attendance as one row a day holding an object keyed by
# employee: 307 rows that have to become about twenty thousand. What is checked
# here is that the pieces keep every promise the engine makes about whole rows.
# --------------------------------------------------------------------------- #


DAY = {
	"name": "RC-ATN-2026-09-01",
	"date": "2026-09-01",
	"modified": "2026-09-01 18:00:00",
	"attendance_log": '{"RC-EMP-00001": {"present": true, "late": false, '
	                  '"absent": false, "overtime": 0}, '
	                  '"RC-EMP-00002": {"present": false, "late": false, '
	                  '"absent": true, "overtime": 0}}',
}

FAN = {"from": "attendance_log", "shape": "map"}


def test_no_fan_out_is_one_piece_keyed_by_the_row(importer):
	"""So the caller has one loop and not two, and a plain step's identity is
	exactly what it was before any of this existed."""
	assert importer.explode({"name": "X"}, None) == [("X", {"name": "X"})]


def test_a_map_fans_out_one_piece_per_key(importer):
	"""And the key is the row's name *and* the piece's.

	Keyed on the piece alone, a month of attendance keyed by employee is one
	record per employee overwritten once a day — 20,229 rows read and 71 kept,
	which is what the first full rehearsal actually reported.
	"""
	pieces = importer.explode(DAY, FAN)
	assert [key for key, _ in pieces] == [
		"RC-ATN-2026-09-01:RC-EMP-00001", "RC-ATN-2026-09-01:RC-EMP-00002",
	]


def test_a_piece_carries_the_parent_and_its_own_key(importer):
	"""The day is on the parent and the attendance is on the piece, and the
	field map reads both without knowing which is which."""
	_, piece = importer.explode(DAY, FAN)[0]
	assert piece["date"] == "2026-09-01"
	assert piece["__key"] == "RC-EMP-00001"
	assert piece["present"] is True


def test_the_piece_wins_where_both_name_something(importer):
	"""The inner value is the more specific one."""
	row = {"name": "P", "status": "parent", "rows": '{"a": {"status": "piece"}}'}
	_, piece = importer.explode(row, {"from": "rows", "shape": "map"})[0]
	assert piece["status"] == "piece"


def test_a_list_fans_out_by_position(importer):
	"""A list has no other stable name, and a stable name is what makes a second
	run an update rather than a duplicate."""
	row = {"name": "P", "items": '[{"item": "a"}, {"item": "b"}]'}
	pieces = importer.explode(row, {"from": "items", "shape": "list"})
	assert [key for key, _ in pieces] == ["P:0", "P:1"]
	assert pieces[1][1]["item"] == "b"


def test_an_empty_column_fans_out_to_nothing(importer):
	"""A day nobody logged is not a failure."""
	assert importer.explode({"name": "P", "attendance_log": ""}, FAN) == []


def test_a_shape_that_does_not_fit_the_data_says_so(importer):
	"""And it says so per row, as an issue, rather than ending the run."""
	row = {"name": "P", "attendance_log": '["not", "an", "object"]'}
	with pytest.raises(ValueError):
		importer.explode(row, FAN)


def test_every_piece_gets_its_own_identity(importer, stepped, monkeypatch):
	"""The one that matters. Every piece of one row shares the parent's name, so
	an identity keyed on that would have twenty thousand rows overwrite each
	other and leave one."""
	keys = []
	monkeypatch.setattr(importer, "fetch", lambda *a: [DAY] if a[3] == 0 else [])
	monkeypatch.setattr(importer, "_write",
	                    lambda plan, step, key, said, made, *a, **k: keys.append(key) or "created")

	step = Step()
	step.fan_out = __import__("json").dumps(FAN)
	row = RunStep()
	importer._step(Run(), Plan(), None, step, row)

	assert keys == ["RC-ATN-2026-09-01:RC-EMP-00001", "RC-ATN-2026-09-01:RC-EMP-00002"]
	# And `seen` counts what the source has, not what was written — a number
	# growing twenty times faster than the thing being read is unreadable as
	# progress.
	assert row.marks["seen"] == 1
	assert row.marks["created"] == 2


def test_one_bad_piece_does_not_lose_the_others(importer, stepped, monkeypatch):
	monkeypatch.setattr(importer, "fetch", lambda *a: [DAY] if a[3] == 0 else [])

	def write(plan, step, key, said, made, *a, **k):
		if key.endswith("2"):
			raise ValueError("Employee RC-EMP-00002 does not exist")
		return "created"

	monkeypatch.setattr(importer, "_write", write)
	step = Step()
	step.fan_out = __import__("json").dumps(FAN)
	row = RunStep()
	importer._step(Run(), Plan(), None, step, row)

	assert row.marks["created"] == 1
	assert row.marks["failed"] == 1
	assert row.marks["status"] == "Done"


# --- the `when` rule --------------------------------------------------------


def test_the_first_true_field_gives_its_value(importer):
	rule = {"status": {"when": [["absent", "Absent"]], "default": "Present"}}
	assert importer.build({"absent": True}, rule, "P") == {"status": "Absent"}
	assert importer.build({"absent": False}, rule, "P") == {"status": "Present"}


def test_when_reads_in_order(importer):
	"""Three booleans where a real system keeps one status: the answer is in
	none of them individually, and which wins is the declaration's to say."""
	rule = {"status": {"when": [["absent", "Absent"], ["half", "Half Day"]],
	                   "default": "Present"}}
	assert importer.build({"absent": True, "half": True}, rule, "P") == {"status": "Absent"}
	assert importer.build({"absent": False, "half": True}, rule, "P") == {"status": "Half Day"}


# --------------------------------------------------------------------------- #
# Child rows
#
# The other half of "one row over there, many rows here", and the commoner
# half: a quotation without its lines is not a quotation. Distinct from a
# fan-out, which makes several *records* — these are rows inside one.
# --------------------------------------------------------------------------- #


LINES = {
	"items": {
		"rows": "items",
		"map": {
			"item_code": {"const": "RUA-FAB"},
			"description": {"from": "description"},
			"qty": {"from": "qty"},
			"rate": {"from": "amount"},
			"custom_width_cm": {"from": "width", "number": True},
		},
	},
}


def test_a_child_table_is_built_out_of_a_list_on_the_source(importer):
	said = {
		"name": "RC-QTN-2500005",
		"items": [
			{"description": "Curtain wall", "qty": 2, "amount": 20160.0, "width": "200.0 cm"},
			{"description": "Sliding door", "qty": 1, "amount": 4200.0, "width": "90 cm"},
		],
	}

	made = importer.build(said, LINES, "P")

	assert made["items"] == [
		{"item_code": "RUA-FAB", "description": "Curtain wall", "qty": 2,
		 "rate": 20160.0, "custom_width_cm": 200.0},
		{"item_code": "RUA-FAB", "description": "Sliding door", "qty": 1,
		 "rate": 4200.0, "custom_width_cm": 90.0},
	]


def test_a_document_with_no_lines_makes_an_empty_table_not_a_missing_one(importer):
	"""An empty list and no key at all are the same answer.

	Frappe reads a Table field's value as the rows; leaving it out of the
	values would keep whatever the record already had, which on a second run
	is the previous import's lines beside this one's.
	"""
	assert importer.build({"name": "Q-1"}, LINES, "P") == {"items": []}
	assert importer.build({"name": "Q-1", "items": []}, LINES, "P") == {"items": []}


def test_a_measurement_somebody_typed_becomes_a_number(importer):
	"""Their widths are prose: `"200.0 cm"`, because the old form had one box
	and no unit. A system that keeps a measurement as a string cannot add two
	of them."""
	rule = {"w": {"from": "width", "number": True}}

	assert importer.build({"width": "200.0 cm"}, rule, "P") == {"w": 200.0}
	assert importer.build({"width": "90"}, rule, "P") == {"w": 90.0}
	assert importer.build({"width": 3.5}, rule, "P") == {"w": 3.5}
	# Nothing rather than a guess: a width of zero is a real width and would
	# be believed by everything downstream.
	assert importer.build({"width": "as drawn"}, rule, "P") == {"w": None}
	assert importer.build({"width": ""}, rule, "P") == {"w": None}


def test_one_line_can_be_built_out_of_the_header(importer):
	"""A progress invoice is one number against a contract, so their invoice
	has no lines at all — and ERPNext will not post one without them."""
	rule = {"items": {"rows": "__self", "map": {
		"item_code": {"const": "RUA-FAB"},
		"qty": {"const": 1},
		"rate": {"from": "amount"},
	}}}

	made = importer.build({"name": "INV-1", "amount": 899233.33}, rule, "P")

	assert made == {"items": [{"item_code": "RUA-FAB", "qty": 1, "rate": 899233.33}]}
	# And it needs no second read: the header is what the list endpoint already
	# answered, so a step that only does this must not fetch a document a row.
	assert importer.maps_children(rule) is False


def test_a_constant_list_is_not_shared_between_records(importer):
	"""A tax row is a constant and a child row is mutable.

	Handed out by reference, whatever the first invoice's controller wrote into
	its tax row would be what the second one started from — and a rate or an
	amount computed once and reused is a set of books that does not add up.
	"""
	rule = {"taxes": {"const": [{"rate": 5}]}}

	first = importer.build({}, rule, "P")
	second = importer.build({}, rule, "P")
	first["taxes"][0]["tax_amount"] = 44961.67

	assert second["taxes"] == [{"rate": 5}]


PARTIES = json.dumps([
	{"name": "Alumil Middle East", "type": "Supplier: Aluminum"},
	{"name": "MSJ General Contracting", "type": "Client"},
	{"name": "Bayaty Architects", "type": "Consultant"},
])


def test_one_entry_is_picked_out_of_a_denormalised_list(importer):
	"""Their project carries every party on it as JSON — client, consultant,
	four suppliers — and the customer is whichever one says Client. It is not a
	column over there and it is not a child table, so without this the field is
	unreachable."""
	rule = {"customer": {"from": "parties", "pick": {"type": "Client"},
	                     "take": "name"}}

	assert importer.build({"parties": PARTIES}, rule, "P") == {
		"customer": "MSJ General Contracting"}


def test_a_list_with_nothing_matching_gives_nothing(importer):
	"""Nothing, and not the first item. A project with no consultant on it has
	no consultant, and handing back whoever was listed first is how a migration
	invents relationships."""
	rule = {"x": {"from": "parties", "pick": {"type": "Architect"}, "take": "name"}}

	assert importer.build({"parties": PARTIES}, rule, "P") == {"x": None}
	assert importer.build({"parties": None}, rule, "P") == {"x": None}


def test_picking_out_of_something_that_is_not_a_list_says_so(importer):
	rule = {"x": {"from": "parties", "pick": {"type": "Client"}}}

	with pytest.raises(ValueError, match="needs a list"):
		importer.build({"parties": '{"type": "Client"}'}, rule, "P")


def test_a_step_only_carries_files_where_it_says_to(importer, stub_frappe, monkeypatch):
	"""One request per row and one download per file, so it is opt-in.

	Twenty thousand attendance records asking their source what is attached to
	them is twenty thousand round trips for nothing.
	"""
	asked = []
	monkeypatch.setattr(importer, "attachments",
	                    lambda source, dt, name: asked.append(name) or [])

	quiet = Step()
	assert importer.carry(object(), quiet, {"name": "P-1"}, Doc(), {}) == {}
	assert asked == []


def test_a_named_file_field_is_repointed_at_our_copy(importer, stub_frappe, monkeypatch):
	"""A logo whose URL is on the site the customer is switching off is a
	broken image the week after the migration, and nobody looks at a logo until
	then."""
	monkeypatch.setattr(importer, "attachments", lambda source, dt, name: [
		{"file_name": "logo.png", "file_url": "/files/logo.png", "is_private": 0},
	])
	monkeypatch.setattr(importer, "download", lambda source, url: b"...")
	monkeypatch.setattr(stub_frappe, "get_all", lambda *a, **k: [])
	monkeypatch.setattr(stub_frappe, "get_doc", lambda values: types.SimpleNamespace(
		insert=lambda **k: None, file_url="/files/logo-ours.png"))

	step = Step()
	rule = {"image": {"from": "image", "file": True}}
	said = {"name": "P-1", "image": "/files/logo.png"}

	found = importer.carry(object(), step, said, Doc(), rule)
	assert found == {"/files/logo.png": "/files/logo-ours.png"}

	doc = Doc()
	written = []
	doc.db_set = lambda field, value, **k: written.append((field, value))
	importer._point_at_ours(doc, said, rule, found)
	assert written == [("image", "/files/logo-ours.png")]


def test_a_file_already_here_is_not_downloaded_twice(importer, stub_frappe, monkeypatch):
	"""Matched on the name it had over there, which is what makes a second run
	a no-op rather than a second copy of every photograph in the company."""
	downloads = []
	monkeypatch.setattr(importer, "attachments", lambda source, dt, name: [
		{"file_name": "perspective.jpg", "file_url": "/files/p.jpg", "is_private": 0},
	])
	monkeypatch.setattr(importer, "download",
	                    lambda source, url: downloads.append(url) or b"")
	monkeypatch.setattr(stub_frappe, "get_all",
	                    lambda *a, **k: [types.SimpleNamespace(file_name="perspective.jpg")])
	stub_frappe.db.values[("File", "file_url")] = "/files/perspective-ours.jpg"

	step = Step()
	step.carry_files = 1
	found = importer.carry(object(), step, {"name": "P-1"}, Doc(), {})

	assert downloads == []
	assert found == {"/files/p.jpg": "/files/perspective-ours.jpg"}


def test_a_second_field_is_tried_before_giving_up(importer):
	"""Two of their seventy-one employees have no joining date and ERPNext
	requires one. The creation date is wrong by however long the old system
	lagged, and is the only date there is."""
	rule = {"date_of_joining": {"from": "joining_date", "default_from": "creation"}}

	assert importer.build({"joining_date": "2024-03-01", "creation": "2025-01-01"},
	                      rule, "P") == {"date_of_joining": "2024-03-01"}
	assert importer.build({"joining_date": None, "creation": "2025-01-01"},
	                      rule, "P") == {"date_of_joining": "2025-01-01"}


def test_a_vocabulary_value_is_made_where_it_is_missing(importer, stub_frappe, monkeypatch):
	"""Fourteen job titles kept as free text over there and as records here.

	Named by the field the doctype names itself after, which is the whole test
	for whether something is a vocabulary at all.
	"""
	made = []
	monkeypatch.setattr(stub_frappe.db, "exists", lambda dt, name=None: False)
	monkeypatch.setattr(stub_frappe, "get_meta",
	                    lambda dt: types.SimpleNamespace(autoname="field:designation_name"))
	monkeypatch.setattr(stub_frappe, "get_doc",
	                    lambda values: made.append(values) or Doc(values, name=values.get(
	                        "designation_name")))

	assert importer.build({"position": "Cutting Specialist"},
	                      {"designation": {"from": "position", "into": "Designation"}},
	                      "P") == {"designation": "Cutting Specialist"}
	assert made == [{"doctype": "Designation", "designation_name": "Cutting Specialist"}]


def test_a_doctype_not_named_after_a_field_is_not_a_vocabulary(importer, stub_frappe,
                                                              monkeypatch):
	"""The guard that keeps this from becoming "create anything I point at".

	An Item is named by a series or a rule, not by a value, and filling one in
	from a line's description would invent a catalogue nobody agreed to keep.
	"""
	monkeypatch.setattr(stub_frappe.db, "exists", lambda dt, name=None: False)
	monkeypatch.setattr(stub_frappe, "get_meta",
	                    lambda dt: types.SimpleNamespace(autoname="hash"))

	with pytest.raises(stub_frappe.ValidationError, match="not named after a field"):
		importer.vocabulary("Item", "CW01")


def test_a_step_that_maps_child_rows_reads_whole_documents(importer, monkeypatch):
	"""The list endpoint answers columns, and a child table is not a column.

	Without the second read every quotation would import with no lines on it
	and nothing would say so — the field map would be satisfied, the record
	would insert, and the numbers would be wrong.
	"""
	assert importer.maps_children(LINES) is True
	assert importer.maps_children({"customer_name": {"from": "party"}}) is False


def test_a_field_map_naming_a_column_the_lines_do_not_have_is_a_problem(
	importer, monkeypatch,
):
	"""The mistake this catches is silent: a line map naming `unit_price` on a
	table whose column is `rate` builds a row of blanks, inserts it, and leaves
	an invoice for nothing."""
	monkeypatch.setattr(importer, "_their_fields",
	                    lambda source, dt, filters, problems: ({"name", "items"},
	                                                           [{"name": "Q-1"}]))
	monkeypatch.setattr(importer, "whole", lambda source, dt, name: {
		"name": "Q-1", "items": [{"description": "Curtain wall", "qty": 2, "amount": 1.0}],
	})
	monkeypatch.setattr(importer, "_our_fields", lambda dt, problems: {"items"})
	step = Row(source_doctype="RUA Quotation", target_doctype="Quotation",
	           field_map=__import__("json").dumps({
	               "items": {"rows": "items", "map": {"rate": {"from": "unit_price"}}},
	           }),
	           fan_out=None, enabled=1, filters="[]")

	found = importer._check_step(None, Row(name="P"), step, set())

	assert any("`items.rate` reads `unit_price`" in p for p in found["problems"])


def test_the_check_looks_past_a_row_with_no_lines_on_it(importer, monkeypatch):
	"""Their oldest purchase order has no items at all.

	Checking a line map against that one says nothing about the map and warns
	about the data — so the check reads a few and takes the first with lines,
	which is what somebody looking by hand would do.
	"""
	docs = {
		"PO-1": {"name": "PO-1", "items": []},
		"PO-2": {"name": "PO-2", "items": [{"item": "M70032-G3", "qty": 58}]},
	}
	monkeypatch.setattr(importer, "_their_fields",
	                    lambda source, dt, filters, problems: (
	                        {"name", "items"}, [{"name": "PO-1"}, {"name": "PO-2"}]))
	monkeypatch.setattr(importer, "whole", lambda source, dt, name: docs[name])
	monkeypatch.setattr(importer, "_our_fields", lambda dt, problems: {"items"})
	step = Row(source_doctype="RUA LPO", target_doctype="Purchase Order",
	           field_map=__import__("json").dumps({
	               "items": {"rows": "items", "map": {"qty": {"from": "qty"}}},
	           }),
	           fan_out=None, enabled=1, filters="[]")

	found = importer._check_step(None, Row(name="P"), step, set())

	assert found["problems"] == []
	assert found["warnings"] == []


def test_a_fan_out_that_does_not_fit_is_a_problem_the_check_finds(importer, monkeypatch):
	"""Whether a column holds the shape a rule claims cannot be known from a
	schema, so the check explodes a real row to find out."""
	monkeypatch.setattr(importer, "_their_fields",
	                    lambda source, dt, filters, problems: ({"attendance_log"},
	                                                           [{"attendance_log": '["a"]'}]))
	monkeypatch.setattr(importer, "_our_fields", lambda dt, problems: {"employee"})
	step = Row(source_doctype="RUA Attendance", target_doctype="Attendance",
	           field_map='{"employee": "__key"}',
	           fan_out=__import__("json").dumps(FAN), enabled=1, filters="[]")

	found = importer._check_step(None, Row(name="P"), step, set())
	assert any("does not fit the data" in p for p in found["problems"])
