"""One price history for everything we sell.

Stripe Prices are immutable in amount and currency, so changing what something
costs means minting a new Price and archiving the old one. Everyone already
subscribed keeps billing on the Price they bought — that is grandfathering, and
it only works while the old ids survive.

Plans needed that first. Add-ons need exactly the same thing, and credit packs
need the archive-on-reprice half of it. So the table and the machinery are
shared rather than copied twice under different names, which is what these pin.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps/oneapp_control/oneapp_control"
CATALOGUE = APP / "billing/catalogue.py"
PRICE_JSON = APP / "control_plane/doctype/catalogue_price/catalogue_price.json"
PATCH = APP / "patches/rename_plan_price.py"


def function(path: Path, name: str) -> str:
	source = path.read_text()
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.FunctionDef) and node.name == name:
			return ast.get_source_segment(source, node)
	raise AssertionError(f"{name} is missing from {path.name}")


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #

def test_the_table_is_a_child_of_whatever_sells():
	import json

	spec = json.loads(PRICE_JSON.read_text())
	assert spec["name"] == "Catalogue Price"
	assert spec.get("istable") == 1


def test_a_one_off_is_a_cadence_the_table_can_express():
	"""A credit pack is bought once. Said rather than left blank, because a price
	with no interval and a price whose interval nobody filled in are different
	problems."""
	import json

	spec = json.loads(PRICE_JSON.read_text())
	interval = next(f for f in spec["fields"] if f["fieldname"] == "interval")
	assert set(interval["options"].split("\n")) == {"Monthly", "Yearly", "One-off"}
	assert interval.get("reqd") == 1


@pytest.mark.parametrize("parent", ["plan"])
def test_every_parent_points_at_the_shared_table(parent):
	import json

	spec = json.loads((APP / f"control_plane/doctype/{parent}/{parent}.json").read_text())
	prices = next(f for f in spec["fields"] if f["fieldname"] == "prices")
	assert prices["options"] == "Catalogue Price"


# --------------------------------------------------------------------------- #
# The sync
# --------------------------------------------------------------------------- #

def test_a_reprice_mints_and_archives_rather_than_edits():
	body = function(CATALOGUE, "ensure_price")
	assert "create_price" in body
	assert "archive_price" in body
	assert "retire_row" in body


def test_the_sync_never_raises():
	"""A record an operator cannot save is worse than a Stripe outage."""
	body = function(CATALOGUE, "sync")
	assert "except Exception" in body
	assert "sync_error" in body
	tree = ast.parse(body.replace("\t", "    ", 1) if body.startswith("\t") else body)
	assert not [n for n in ast.walk(tree) if isinstance(n, ast.Raise)]


def test_a_one_off_price_carries_no_recurring_block():
	"""Stripe reads the presence of `recurring` as 'this is a subscription
	price', so passing it empty is not the same as leaving it out — a credit pack
	would become a subscription nobody asked for."""
	body = function(CATALOGUE, "ensure_price")
	assert 'interval == ONE_OFF' in body
	assert '{}' in body


def test_an_interval_priced_at_nothing_is_not_sold():
	"""A plan can be monthly-only. The existing price stays listed, because
	somebody may be on it."""
	body = function(CATALOGUE, "ensure_price")
	assert "amount <= 0" in body
	assert "retire_row(current)" in body


def test_the_idempotency_key_carries_the_amount():
	"""Minting the same price twice is a duplicate; minting a different one is a
	deliberate change, and Stripe cannot tell them apart on its own."""
	body = function(CATALOGUE, "ensure_price")
	assert "idempotency_key" in body
	assert "cents" in body


def test_a_lookup_must_say_which_catalogue_it_means():
	"""One table holds every catalogue's history. Without the parenttype an
	add-on's price would resolve to 'a plan' and reprice the workspace onto it,
	which is the whole reason this is not optional."""
	for name in ("owner_of_price", "interval_of_price"):
		body = function(CATALOGUE, name)
		assert "parenttype" in body, name

	tree = ast.parse(CATALOGUE.read_text())
	for name in ("owner_of_price", "interval_of_price"):
		fn = next(
			n for n in ast.walk(tree)
			if isinstance(n, ast.FunctionDef) and n.name == name
		)
		required = [a.arg for a in fn.args.args[len(fn.args.args) - len(fn.args.defaults):]] \
			if fn.args.defaults else []
		assert "parenttype" not in required, f"{name} lets parenttype default"


# --------------------------------------------------------------------------- #
# The rename
# --------------------------------------------------------------------------- #

def test_the_rename_runs_before_the_model_sync():
	"""After the sync Frappe has already created Catalogue Price from its JSON,
	and a rename then would leave the old table behind holding every price we
	have minted — the one thing here that cannot be regenerated, because Stripe
	is still billing on those ids."""
	text = (APP / "patches.txt").read_text()
	pre = text[text.index("[pre_model_sync]"):text.index("[post_model_sync]")]
	assert "rename_plan_price" in pre


def test_the_rename_moves_the_table_rather_than_making_a_new_one():
	body = PATCH.read_text()
	assert "rename_doc" in body
	assert '"Plan Price", "Catalogue Price"' in body
	assert "parenttype" in body, "child rows would point at a doctype that is gone"


def test_the_rename_is_safe_to_run_twice():
	"""Every patch runs once, but a half-finished migration is re-run by hand."""
	# Wrapping is not the subject, so it is normalised away rather than matched.
	body = " ".join(PATCH.read_text().split())
	assert 'exists("DocType", "Plan Price")' in body
	assert 'not frappe.db.exists( "DocType", "Catalogue Price" )' in body, (
		"the rename would run again over a table it has already renamed"
	)
