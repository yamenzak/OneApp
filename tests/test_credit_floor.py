"""A credit that sells for less than it costs to honour.

Three numbers decide whether AI makes money and no two of them are typed on the
same screen: `CREDITS_PER_USD`, which is code; the markup, which is a control
setting and a per-model override; and a pack's credits and price, which an
operator types into a catalogue. Nothing compared them, so the catalogue could
sell a thousand credits for a dollar and every screen would look correct while
the inference bill went up.

The direction that breaks it is the counter-intuitive one, which is why it is
worth a test rather than a comment: *raising* a markup charges more credits for
the same provider spend, so each credit buys less of it and a pack gets more
profitable. *Lowering* one is what puts a pack under water — including a
per-model override, because a customer chooses which model to spend a credit on
and will not choose the one that is dearest for us.
"""

import sys

import pytest


@pytest.fixture
def pricing(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp_control"):
			del sys.modules[name]
	from oneapp_control.ai import pricing as module

	return module


@pytest.fixture
def packs(stub_frappe, pricing):
	from oneapp_control.billing import packs as module

	return module


def catalogue(stub_frappe, models=(), rows=(), markup=None):
	"""The AI models a credit can be spent on, and the packs on sale.

	Rows as Frappe's own `_dict` rather than a namespace, because `underwater`
	spreads one — and a stub that only answered to attribute access would pass
	on code that cannot work against the real thing.
	"""
	def get_all(doctype, **kw):
		if doctype == "AI Model":
			return [stub_frappe._dict(markup_override=one) for one in models]
		return [stub_frappe._dict(**one) for one in rows]

	stub_frappe.get_all = get_all
	stub_frappe.db.get_single_value = lambda *a: markup


# --------------------------------------------------------------------------- #
# What a credit costs
# --------------------------------------------------------------------------- #

def test_the_fallback_markup_carries_more_than_the_provider_bill(pricing):
	"""Three, not the one and a half it was. Stripe takes about 2.9% and thirty
	cents of every payment — on a small pack that alone is a tenth of the sale —
	and the metering, the reconciliation and the ledger sit under that. A markup
	of 1.5 is a 33% gross margin of revenue before any of it."""
	assert pricing.FALLBACK_MARKUP == 3.0


def test_a_credit_costs_a_cent_divided_by_the_markup(pricing, stub_frappe):
	"""The inverse of `to_credits`, and the number the catalogue has to clear."""
	catalogue(stub_frappe, markup=3.0)
	assert pricing.cost_per_credit() == pytest.approx(1 / 300)
	# Which is exactly what a call costing that much is charged.
	assert pricing.to_credits(1 / 300, 3.0) == pytest.approx(1.0, abs=0.01)


def test_the_cheapest_model_prices_every_pack(pricing, stub_frappe):
	"""A customer chooses which model to spend a credit on and will not choose
	the one that is dearest for us. One override at 1.0 reprices the whole
	catalogue against it."""
	catalogue(stub_frappe, models=[0, 1.0, 5.0], markup=3.0)
	assert pricing.lowest_markup() == 1.0
	catalogue(stub_frappe, models=[0, 5.0], markup=3.0)
	assert pricing.lowest_markup() == 3.0


def test_a_model_nobody_can_call_does_not_price_anything(pricing, stub_frappe):
	"""Retired and Needs Review models are filtered in the query, so a stale
	override on something unreachable cannot drag the floor down."""
	import inspect

	source = inspect.getsource(pricing.lowest_markup)
	assert '"status": ("in", ("Available", "Preview"))' in source


# --------------------------------------------------------------------------- #
# The floor
# --------------------------------------------------------------------------- #

def test_a_pack_priced_under_cost_is_refused(packs, stub_frappe):
	catalogue(stub_frappe, markup=3.0)
	# A thousand credits cost us $3.33 to honour at 3×.
	assert packs.floor_price(1000) == pytest.approx(3.33, abs=0.01)

	packs.check_price(1000, 10.0)  # fine
	with pytest.raises(stub_frappe.ValidationError):
		packs.check_price(1000, 2.0)


def test_the_refusal_says_what_to_do_about_it(packs, stub_frappe):
	"""Three numbers on two screens made this, so the message has to name all
	three ways out or somebody edits the wrong one."""
	catalogue(stub_frappe, markup=3.0)
	with pytest.raises(stub_frappe.ValidationError) as raised:
		packs.check_price(1000, 1.0, "Small")
	said = str(raised.value)
	assert "Small" in said
	assert "Raise the price" in said and "markup" in said


def test_an_empty_pack_is_somebody_elses_error(packs, stub_frappe):
	"""Zero credits and zero price are refused by the controller with better
	sentences. This one only has an opinion about a ratio."""
	catalogue(stub_frappe, markup=3.0)
	packs.check_price(0, 0)
	packs.check_price(1000, 0)


def test_lowering_a_markup_is_what_puts_a_pack_under_water(packs, stub_frappe):
	"""Not raising it. More markup means more credits charged for the same
	provider spend, so each credit buys less and the pack gets safer."""
	sold = [{"name": "p", "pack_name": "Small", "credits": 1000, "amount": 5.0}]
	catalogue(stub_frappe, rows=sold, markup=3.0)

	assert packs.underwater(3.0) == []
	assert packs.underwater(5.0) == []
	# At 1.5×, a thousand credits cost $6.67 and this pack sells them for five.
	broken = packs.underwater(1.5)
	assert [one["pack_name"] for one in broken] == ["Small"]
	assert broken[0]["floor"] == pytest.approx(6.67, abs=0.01)


# --------------------------------------------------------------------------- #
# The two screens that can cause it
# --------------------------------------------------------------------------- #

def test_the_markup_setting_refuses_to_strand_a_pack():
	"""Saved through an endpoint rather than a form, so the check lives there."""
	import ast
	from pathlib import Path

	import where

	source = (Path(where.__file__).resolve().parent.parent
	          / "apps/oneapp_control/oneapp_control/api/admin/ai.py").read_text()
	body = next(
		node for node in ast.walk(ast.parse(source))
		if isinstance(node, ast.FunctionDef) and node.name == "set_ai_markup"
	)
	called = {ast.unparse(node.func) for node in ast.walk(body) if isinstance(node, ast.Call)}
	assert "packs.underwater" in called
	# And before the write, not after it.
	written = ast.unparse(body).index("set_single_value")
	assert ast.unparse(body).index("packs.underwater") < written


def test_a_model_override_is_checked_the_same_way():
	"""It reprices the whole catalogue, so it is the same decision made from a
	different form."""
	import ast
	from pathlib import Path

	import where

	source = (Path(where.__file__).resolve().parent.parent
	          / "apps/oneapp_control/oneapp_control/control_plane/doctype"
	          / "ai_model/ai_model.py").read_text()
	assert "packs.underwater" in source
	assert "def validate" in source
