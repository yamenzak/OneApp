"""Two sources claiming one key, and what happens to the one that loses.

README §6 is a claim about trust rather than about data: software that silently
drops one of two disagreeing numbers is software nobody trusts twice, and in
this market the disagreement is often the interesting part. So what is tested
here is not "the right value won" — it is that the other value is still there,
that it says what it disagrees about, and that a customer reordering their
sources changes the answer immediately rather than at the next delivery.

The fake below is four Frappe calls deep because the module is four Frappe calls
deep. A test that stubbed `settle` would assert that the code calls itself.
"""

import ast
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import where

ROOT = Path(where.__file__).resolve().parent.parent
GTFS = ROOT / "apps/oneapp/oneapp/onemobility/gtfs.py"


class Store:
	"""Enough of Frappe to settle a claim: rows, a key lookup, and a save."""

	def __init__(self, frappe):
		self.rows = {"Transit Claim": {}, "Transit Stop": {}, "Transit Source": {}}
		self.at = 0
		frappe.get_all = self.get_all
		frappe.get_doc = self.get_doc
		frappe.db.get_value = self.get_value
		frappe.db.set_value = self.set_value

	# -- writing ----------------------------------------------------------- #
	def put(self, doctype, name, **values):
		self.rows.setdefault(doctype, {}).setdefault(name, {"name": name})
		self.rows[doctype][name].update(values)
		return name

	def get_doc(self, first, second=None):
		if isinstance(first, dict):
			doctype = first["doctype"]
			self.at += 1
			name = f"{doctype[-4:].strip().lower()}-{self.at}"
			self.put(doctype, name, **{k: v for k, v in first.items() if k != "doctype"})
			return self._doc(doctype, name)
		return self._doc(first, second)

	def _doc(self, doctype, name):
		store = self

		class Doc(types.SimpleNamespace):
			def update(self, values):
				store.put(doctype, name, **values)

			def save(self, **kw):
				return self

			def insert(self, **kw):
				return self

		return Doc(doctype=doctype, **store.rows[doctype][name])

	def set_value(self, doctype, name, field=None, value=None, **kw):
		values = field if isinstance(field, dict) else {field: value}
		for one in self._matching(doctype, name):
			one.update(values)

	# -- reading ----------------------------------------------------------- #
	def _matching(self, doctype, name):
		rows = list(self.rows.get(doctype, {}).values())
		if isinstance(name, dict):
			return [one for one in rows if all(one.get(k) == v for k, v in name.items())]
		return [one for one in rows if one["name"] == name]

	def get_value(self, doctype, filters=None, fieldname=None, *a, **k):
		found = self._matching(doctype, filters)
		return found[0].get(fieldname) if found else None

	def get_all(self, doctype, filters=None, fields=None, order_by="", **k):
		rows = [
			dict(one) for one in self.rows.get(doctype, {}).values()
			if all(one.get(key) == value for key, value in (filters or {}).items())
		]
		for part in reversed([one.strip() for one in (order_by or "").split(",") if one.strip()]):
			field, _sep, direction = part.partition(" ")
			rows.sort(key=lambda one: (one.get(field) is None, one.get(field)),
			          reverse=direction.strip() == "desc")
		return rows


@pytest.fixture
def conflicts(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import conflicts as module

	return module


@pytest.fixture
def store(stub_frappe, conflicts, monkeypatch):
	shop = Store(stub_frappe)
	clock = {"at": datetime(2026, 9, 9, 10, 0, 0)}

	def tick():
		clock["at"] += timedelta(seconds=1)
		return clock["at"]

	monkeypatch.setattr(conflicts, "now_datetime", tick)
	shop.put("Transit Source", "planning", precedence=10)
	shop.put("Transit Source", "vehicles", precedence=50)
	shop.put("Transit Source", "unranked")
	return shop


def stop(conflicts, key="zz-1", name="Alexanderplatz", lat=52.52, source="planning"):
	return conflicts.record(
		"Transit Stop", key,
		{"stop_name": name, "stop_code": "1", "latitude": lat, "longitude": 13.4,
		 "zone": "A"},
		source=source, feed="feed-1",
	)


def claims(store, key="zz-1"):
	return {
		one["source"]: one
		for one in store.get_all("Transit Claim", filters={"natural_key": key})
	}


# --------------------------------------------------------------------------- #
# The ordinary case, which is nearly every key
# --------------------------------------------------------------------------- #

def test_one_source_saying_something_is_not_a_conflict(conflicts, store):
	"""Nearly every key on nearly every workspace. One row, drawn, and no badge
	anywhere — a conflict surface that flags the normal case is noise."""
	name = stop(conflicts)
	only = claims(store)["planning"]
	assert only["verdict"] == "Drawn"
	assert not only["contested"]
	assert store.rows["Transit Stop"][name]["stop_name"] == "Alexanderplatz"


def test_a_row_with_no_source_behind_it_writes_no_claim(conflicts, store):
	"""A fixture, a hand-made row, a migration. A claim nobody can attribute
	answers no question, so it is not written."""
	conflicts.record("Transit Stop", "zz-9", {"stop_name": "Depot"})
	assert not store.rows["Transit Claim"]


# --------------------------------------------------------------------------- #
# Two sources
# --------------------------------------------------------------------------- #

def test_the_loser_is_kept_and_says_what_it_disagrees_about(conflicts, store):
	"""The whole of §6. Dropping the second answer is the cheap version and is
	the one that makes a data product untrustworthy — here the planning office
	says Alexanderplatz and the vehicles say something else, and both are on
	the screen."""
	stop(conflicts, name="Alexanderplatz", source="planning")
	stop(conflicts, name="Alexanderpl.", lat=52.6, source="vehicles")

	settled = claims(store)
	assert settled["planning"]["verdict"] == "Drawn"
	assert settled["vehicles"]["verdict"] == "Overruled"
	assert settled["vehicles"]["differs"] == "latitude, stop_name"
	assert all(one["contested"] for one in settled.values())


def test_two_sources_agreeing_is_not_a_disagreement(conflicts, store):
	"""Worth showing — three sources agreeing and one not is a much stronger
	finding than two disagreeing — and not worth flagging."""
	stop(conflicts, source="planning")
	stop(conflicts, source="vehicles")
	settled = claims(store)
	assert settled["vehicles"]["verdict"] == "Agrees"
	assert not any(one["contested"] for one in settled.values())


def test_the_record_carries_one_source_answer_entire(conflicts, store):
	"""Not the best field from each. Taking the name from whoever ranks highest
	for names and the position from whoever ranks highest for positions is how
	a stop ends up named Alexanderplatz with Spandau's coordinates, and neither
	source ever said that."""
	name = stop(conflicts, name="Alexanderplatz", lat=52.52, source="planning")
	stop(conflicts, name="Alexanderpl.", lat=52.6, source="vehicles")
	drawn = store.rows["Transit Stop"][name]
	assert (drawn["stop_name"], drawn["latitude"]) == ("Alexanderplatz", 52.52)


def test_a_tie_goes_to_whatever_was_seen_last(conflicts, store):
	"""Two sources a customer ranked the same. Falling back to row order would
	make the answer depend on which delivery happened to be read first, which
	is a coin toss that looks like a decision."""
	store.put("Transit Source", "other", precedence=50)
	stop(conflicts, name="Old", source="other")
	stop(conflicts, name="New", source="vehicles")

	settled = claims(store)
	assert settled["other"]["precedence"] == settled["vehicles"]["precedence"] == 50
	assert settled["vehicles"]["verdict"] == "Drawn"
	assert settled["other"]["verdict"] == "Overruled"


def test_a_source_nobody_ranked_does_not_quietly_win(conflicts, store):
	"""An empty precedence read as nought would beat every source the customer
	actually thought about."""
	assert conflicts._precedence("unranked") == conflicts.DEFAULT_PRECEDENCE
	stop(conflicts, name="Guess", source="unranked")
	stop(conflicts, name="Planned", source="planning")
	assert claims(store)["planning"]["verdict"] == "Drawn"


def test_reordering_the_sources_changes_the_map_now(conflicts, store):
	"""Not at the next delivery, which for an SFTP drop folder is tomorrow.
	This is what makes precedence a setting rather than an import-time
	snapshot."""
	name = stop(conflicts, name="Alexanderplatz", source="planning")
	stop(conflicts, name="Alexanderpl.", source="vehicles")

	store.put("Transit Source", "vehicles", precedence=1)
	conflicts.resettle("vehicles")

	assert claims(store)["vehicles"]["verdict"] == "Drawn"
	assert claims(store)["planning"]["verdict"] == "Overruled"
	assert store.rows["Transit Stop"][name]["stop_name"] == "Alexanderpl."


def test_a_precedence_that_did_not_change_settles_nothing(conflicts, store, monkeypatch):
	"""`on_update` fires on every save of a source — a renamed endpoint, a new
	password, a run that marked it Failing. Re-settling every key it claims on
	each of those is a table scan for nothing."""
	settled = []
	monkeypatch.setattr(conflicts, "resettle", lambda source: settled.append(source))
	doc = types.SimpleNamespace(
		name="planning", precedence=10, has_value_changed=lambda field: False
	)
	conflicts.on_source_change(doc)
	assert not settled


# --------------------------------------------------------------------------- #
# What counts as disagreeing
# --------------------------------------------------------------------------- #

def test_the_same_number_written_differently_is_not_a_disagreement(conflicts):
	"""`52.5` and `52.50000`, or a trailing space. A badge on every one of
	those makes the real ones impossible to find."""
	assert not conflicts._differs(52.5, 52.50000)
	assert not conflicts._differs("Alexanderplatz ", "Alexanderplatz")
	assert not conflicts._differs("", None)
	assert conflicts._differs(52.5, 52.6)


def test_a_feed_never_claims_what_the_workspace_chose(conflicts, store):
	"""A colour somebody picked in our UI, an emoji, a marker shape, a status.
	No feed has an opinion about those, and a source that overwrote them on
	every delivery would make the record uneditable with nobody able to say
	why."""
	claimed = conflicts.CLAIMED["Transit Line"][3]
	assert "colour" not in claimed and "emoji" not in claimed
	assert "marker_shape" not in claimed and "status" not in claimed


# --------------------------------------------------------------------------- #
# The surfaces
# --------------------------------------------------------------------------- #

def test_the_screen_shows_both_answers_side_by_side(conflicts, store):
	"""The honest version of "select all sources": it is not merging, it is
	choosing whose answer to draw, and it can always show you the others."""
	stop(conflicts, name="Alexanderplatz", source="planning")
	stop(conflicts, name="Alexanderpl.", source="vehicles")

	out = conflicts.disagreements()
	assert out["total"] == 1
	found = out["disagreements"][0]
	assert found["key"] == "zz-1"
	assert {one["source"] for one in found["claims"]} == {"planning", "vehicles"}
	assert [one["values"]["stop_name"] for one in found["claims"]] == [
		"Alexanderplatz", "Alexanderpl."
	]


def test_a_workspace_whose_sources_agree_has_an_empty_screen(conflicts, store):
	stop(conflicts, source="planning")
	assert conflicts.disagreements() == {"disagreements": [], "total": 0}


def test_an_inferred_stop_is_promoted_by_a_person_and_nothing_else(conflicts, store):
	"""A vehicle stopping where no feed declares a stop is a finding, drawn
	differently. Promoting it automatically would be the system quietly adding
	things to the network it was asked to describe."""
	store.put("Transit Stop", "guessed", status="Inferred")
	store.put("Transit Stop", "real", status="Served")

	assert conflicts.accept_stop("guessed") == {"accepted": True, "status": "Served"}
	assert store.rows["Transit Stop"]["guessed"]["status"] == "Served"
	assert conflicts.accept_stop("real") == {"accepted": False, "status": "Served"}


def test_neither_surface_answers_a_reader_who_may_not_see_a_line(conflicts, store, stub_frappe):
	stub_frappe.has_permission = lambda *a, **k: False
	with pytest.raises(stub_frappe.PermissionError):
		conflicts.disagreements()
	with pytest.raises(stub_frappe.PermissionError):
		conflicts.accept_stop("guessed")


# --------------------------------------------------------------------------- #
# And the importer actually goes through it
# --------------------------------------------------------------------------- #

def test_the_importer_writes_claims_rather_than_overwriting(conflicts):
	"""The one that keeps this from being a module nothing calls. A GTFS load
	that saved the record directly would leave the claim table empty and every
	screen above it honest about nothing."""
	tree = ast.parse(GTFS.read_text())
	body = next(
		node for node in ast.walk(tree)
		if isinstance(node, ast.FunctionDef) and node.name == "_upsert"
	)
	called = {ast.unparse(node.func) for node in ast.walk(body) if isinstance(node, ast.Call)}
	assert called == {"conflicts.record"}, called
