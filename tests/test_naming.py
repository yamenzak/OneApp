"""Naming: which doctypes a workspace may set a series for, and how far.

Frappe's `Document Naming Settings` does the writing — the Property Setter, the
duplicate check across every other doctype, the counter, the Version log — so
what is pinned here is the gate in front of it and the one distinction the
desk's own page never makes: a doctype named by a `naming_series` field, whose
prefixes are a business decision, against one named by its own `autoname`,
whose prefixes are part of what the app is. See `docs/PRINTING.md`, "Naming".
"""

import types

import pytest


@pytest.fixture
def naming(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import naming as module

	return module


def declare(frappe, doctype, *, series=False, autoname=""):
	field = types.SimpleNamespace(fieldname="naming_series", fieldtype="Select",
	                              label="Series", options="", default="")
	frappe._meta[doctype] = types.SimpleNamespace(
		name=doctype,
		autoname=autoname,
		fields=[field] if series else [],
		get_field=lambda name, field=field, series=series: (
			field if series and name == "naming_series" else None
		),
	)


def test_a_naming_series_field_is_the_editable_kind(naming, stub_frappe):
	"""The one Frappe's own settings page is about, and the only one a
	workspace may set: "our invoices start ACME-INV-" is a business decision,
	and Frappe stores it as a Property Setter rather than as an edit to the
	doctype, which is exactly what makes it safe to offer."""
	declare(stub_frappe, "Sales Invoice", series=True)
	assert naming._kind("Sales Invoice") == "series"


def test_a_doctype_named_by_its_own_scheme_is_the_other_kind(naming, stub_frappe):
	"""`EV.#####` is part of what Event *is*. The prefixes are not ours to
	change — but the counter under them is exactly as real, and a workspace
	that has just imported four years of history wants to move it."""
	declare(stub_frappe, "Event", autoname="EV.#####")
	assert naming._kind("Event") == "autoname"


def test_a_hash_or_a_field_has_no_counter_at_all(naming, stub_frappe):
	"""Nothing counts up, so there is nothing here to show."""
	declare(stub_frappe, "Note", autoname="hash")
	declare(stub_frappe, "Contact", autoname="field:first_name")
	declare(stub_frappe, "Todo", autoname="")

	assert naming._kind("Note") == ""
	assert naming._kind("Contact") == ""
	assert naming._kind("Todo") == ""
	assert not naming._named("Note")


def test_only_what_a_space_put_on_a_screen_is_reachable(naming, stub_frappe,
                                                        monkeypatch):
	"""The desk's own naming page offers every doctype on the site. A workspace
	that can renumber `Error Log` has been handed the platform's bookkeeping."""
	declare(stub_frappe, "Sales Invoice", series=True)
	monkeypatch.setattr(naming, "_granted", lambda: {"Sales Invoice"})

	with pytest.raises(stub_frappe.ValidationError) as raised:
		naming._reachable("Error Log")
	assert "Error Log" in str(raised.value)


def test_reaching_it_still_needs_write_on_the_doctype(naming, stub_frappe,
                                                      monkeypatch):
	"""The same rule as the rest of the product: what you may change is a
	subset of what you may read."""
	declare(stub_frappe, "Sales Invoice", series=True)
	monkeypatch.setattr(naming, "_granted", lambda: {"Sales Invoice"})
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: False,
	                    raising=False)

	with pytest.raises(stub_frappe.PermissionError):
		naming._reachable("Sales Invoice")


def test_prefixes_cannot_be_set_on_a_doctype_that_names_itself(naming, stub_frappe,
                                                               monkeypatch):
	"""Refused with the reason, because the counter beside it is not."""
	declare(stub_frappe, "Event", autoname="EV.#####")
	monkeypatch.setattr(naming, "_granted", lambda: {"Event"})
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True,
	                    raising=False)

	with pytest.raises(stub_frappe.ValidationError) as raised:
		naming.set_options("Event", ["EV-2-.#####"])
	assert "counter" in str(raised.value)


def test_a_doctype_offers_a_bounded_number_of_series(naming, stub_frappe,
                                                     monkeypatch):
	"""Frappe bounds none. A Select with forty options is a control nobody
	reads to the end of, and a workspace wanting forty wants a naming rule."""
	declare(stub_frappe, "Sales Invoice", series=True)
	monkeypatch.setattr(naming, "_granted", lambda: {"Sales Invoice"})
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True,
	                    raising=False)

	written = {}

	class Settings:
		transaction_type = None
		naming_series_options = None

		def update_series(self):
			written["options"] = self.naming_series_options

	monkeypatch.setattr(stub_frappe, "get_doc", lambda *a, **k: Settings())
	monkeypatch.setattr(naming, "options", lambda doctype: [])

	naming.set_options("Sales Invoice", [f"P{i}-.#####" for i in range(naming.SERIES + 6)])
	assert len(written["options"].split("\n")) == naming.SERIES


def test_a_series_with_no_prefixes_is_refused(naming, stub_frappe, monkeypatch):
	"""A record needs something to be named by, and an empty Select is a form
	nobody can submit."""
	declare(stub_frappe, "Sales Invoice", series=True)
	monkeypatch.setattr(naming, "_granted", lambda: {"Sales Invoice"})
	monkeypatch.setattr(stub_frappe, "has_permission", lambda *a, **k: True,
	                    raising=False)

	with pytest.raises(stub_frappe.ValidationError):
		naming.set_options("Sales Invoice", ["   ", ""])
