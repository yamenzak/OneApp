"""A deal's stage: what it means, and where the deal has been.

`docs/ONECRM.md` stages 1 and 2. Three claims.

**The stage decides the status.** `custom_stage` is a row a team named and
`status` is ERPNext's own Select, which their controller and every report over
the module read. One is written from the other's category, on one path.

**A probability is what the column assumes**, written when a deal arrives at a
stage and never again: the number on the deal is what the person selling it
says, and a rep who typed 80% keeps it until they move the card.

**And each arrival is logged.** A pipeline review is not held to ask what is in
Negotiation, it is held to ask what has been in Negotiation for forty days.
"""

import types

import pytest


@pytest.fixture
def stages(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onecrm"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onecrm.stages")


COLUMNS = {
	"New": {"category": "Open", "probability": 10},
	"Proposal": {"category": "Ongoing", "probability": 50},
	"Parked": {"category": "On hold", "probability": 0},
	"Signed": {"category": "Won", "probability": 100},
	"Gone": {"category": "Lost", "probability": 0},
}


def site(stages, monkeypatch, columns=None):
	rows = columns if columns is not None else COLUMNS

	def get_value(doctype, name, field):
		return (rows.get(name) or {}).get(field)

	monkeypatch.setattr(stages.frappe.db, "get_value", get_value)


def test_a_category_has_a_word_in_erpnexts_vocabulary(stages, monkeypatch):
	"""A workspace may call its last column Signed, Instructed or Booked; a
	forecast that had to know those three would break on the fourth."""
	site(stages, monkeypatch)
	assert stages.status_of("Signed") == "Converted"
	assert stages.status_of("Gone") == "Lost"


def test_a_deal_on_hold_is_not_a_loss(stages, monkeypatch):
	"""The reason On hold is a category of its own rather than folded into one
	of theirs: it is neither moving nor lost, and a report has to be able to
	leave it out of both."""
	site(stages, monkeypatch)
	assert stages.status_of("Parked") == "Open"


def test_a_column_nobody_declared_writes_no_status(stages, monkeypatch):
	"""A stage a workspace deleted, or one seeded before the categories were.
	Empty rather than a guess: a deal keeps the status it had."""
	site(stages, monkeypatch, columns={})
	assert stages.status_of("Whatever") == ""
	assert stages.status_of("") == ""


def test_the_two_statuses_we_never_write_are_theirs(stages):
	"""`Quotation` is set by their own controller when a quotation is raised,
	and `Replied` is mail's."""
	assert set(stages.STATUS_OF.values()) == {"Open", "Converted", "Lost"}


# --------------------------------------------------------------------------- #
# Where a deal has been
# --------------------------------------------------------------------------- #

class Deal:
	"""Just enough of an Opportunity for the log to be written onto it."""

	def __init__(self, stage, rows=(), new=False, was=None):
		self.custom_stage = stage
		self.custom_stage_log = [types.SimpleNamespace(**row) for row in rows]
		self.custom_stage_since = None
		self.probability = 0
		self.status = "Open"
		self._new = new
		self._was = was
		# The columns are a space manifest's, so `progress.log_the_move` asks
		# whether this doctype has the table before appending to it — a lead
		# saved between `bench migrate` and the first sync otherwise throws.
		self.meta = types.SimpleNamespace(has_field=lambda name: True)

	def get(self, field, default=None):
		return getattr(self, field, default)

	def set(self, field, value):
		setattr(self, field, value)

	def append(self, field, row):
		fresh = types.SimpleNamespace(
			stage=row.get("stage"), entered_on=row.get("entered_on"),
			left_on=None, days=0, moved_by=row.get("moved_by"),
		)
		getattr(self, field).append(fresh)
		return fresh

	def is_new(self):
		return self._new

	def get_doc_before_save(self):
		return {"custom_stage": self._was} if self._was else None


@pytest.fixture
def deal(stub_frappe, monkeypatch):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onecrm"):
			del sys.modules[name]
	# ERPNext is not on the bench the unit tests run against, so the base class
	# is stubbed the way every other override in this repository is.
	erpnext = types.ModuleType("erpnext.crm.doctype.opportunity.opportunity")
	erpnext.Opportunity = type("Opportunity", (), {"validate": lambda self: None})
	for part in ("erpnext", "erpnext.crm", "erpnext.crm.doctype",
	             "erpnext.crm.doctype.opportunity"):
		sys.modules.setdefault(part, types.ModuleType(part))
	monkeypatch.setitem(sys.modules,
	                    "erpnext.crm.doctype.opportunity.opportunity", erpnext)
	module = importlib.import_module("oneapp.onecrm.deal")
	monkeypatch.setattr(module.stages, "status_of", lambda one: "Open")
	monkeypatch.setattr(module.stages, "probability_of", lambda one: 50)
	return module


def test_the_stage_writes_their_status_and_the_columns_number(deal):
	"""The two halves of `_from_stage`, on the arrival that triggers them."""
	one = Deal("Proposal", new=True)
	deal.Deal._from_stage(one)
	assert one.status == "Open"
	assert one.probability == 50


def test_a_deal_that_did_not_move_keeps_the_number_somebody_typed(deal):
	"""The stage is what the desk assumes and the number on the deal is what
	the person selling it says."""
	one = Deal("Proposal", was="Proposal", rows=[{
		"stage": "Proposal", "entered_on": "2025-12-25 00:00:00", "left_on": None,
		"days": 0, "moved_by": "somebody@example.com",
	}])
	one.probability = 80
	deal.Deal._from_stage(one)
	assert one.probability == 80


def test_an_arrival_opens_a_row(deal):
	one = Deal("Proposal", new=True)
	deal.Deal._log_the_move(one)
	assert [row.stage for row in one.custom_stage_log] == ["Proposal"]
	assert one.custom_stage_log[0].left_on is None
	assert one.custom_stage_since == one.custom_stage_log[0].entered_on


def test_a_move_closes_the_row_before_it(deal):
	"""How long it sat there, filled on the way out — which is the number a
	pipeline review reads."""
	one = Deal("Proposal", rows=[{
		"stage": "New", "entered_on": "2025-12-25 00:00:00", "left_on": None,
		"days": 0, "moved_by": "somebody@example.com",
	}])
	deal.Deal._log_the_move(one)

	assert [row.stage for row in one.custom_stage_log] == ["New", "Proposal"]
	assert one.custom_stage_log[0].left_on
	assert one.custom_stage_log[0].days > 0


def test_a_save_that_moves_nothing_writes_nothing(deal):
	"""This runs on every save of every deal on the site, so the common case is
	the one that has to cost nothing."""
	one = Deal("Proposal", rows=[{
		"stage": "Proposal", "entered_on": "2026-01-01 00:00:00", "left_on": None,
		"days": 0, "moved_by": "somebody@example.com",
	}])
	deal.Deal._log_the_move(one)
	assert len(one.custom_stage_log) == 1
	assert one.custom_stage_since is None


def test_a_deal_with_no_stage_logs_nothing(deal):
	"""A workspace that has not opened the pipeline should not have its deals
	rewritten by a field it has not used."""
	one = Deal("", new=True)
	deal.Deal._log_the_move(one)
	assert one.custom_stage_log == []


def test_the_log_is_bounded(deal):
	"""A deal dragged around a board two hundred times is still a record
	somebody has to be able to open, and the oldest rows are the least
	interesting."""
	rows = [{"stage": f"S{at}", "entered_on": "2026-01-01 00:00:00",
	         "left_on": "2026-01-02 00:00:00", "days": 1, "moved_by": "x"}
	        for at in range(deal.progress.MOST + 5)]
	rows[-1]["left_on"] = None
	one = Deal("Proposal", rows=rows)
	deal.Deal._log_the_move(one)
	assert len(one.custom_stage_log) == deal.progress.MOST
	assert one.custom_stage_log[-1].stage == "Proposal"
