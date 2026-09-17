"""Who a conversation is about, from the addresses on it.

`docs/CLEANUP.md` §7 and stage 11: a message arrives and the task, the person
and the party it concerns are proposed. The task is `mail.notice` and is a
model; these two are not, and that is the whole argument of
`onemail/concerns.py` — `linking.py`'s rule is that a model is worth nothing
until the cases it is not needed for are handled without it, and a party and a
person behind an address are two joins.

So these check the joins, the order, and the three ways to get it wrong that
are silent: resolving an address Frappe stores in `Name <addr>` form, linking a
contact to something that is not a party, and letting the address link take the
primary reference away from an id somebody wrote.
"""

import types

import pytest


@pytest.fixture
def concerns(monkeypatch):
	"""The module, with the database answering from tables in the test.

	Imported inside the fixture for the same reason `test_mail_linking` does
	it: `frappe` is stubbed by an autouse fixture and a module-level import
	would run first.
	"""
	from oneapp.onemail import concerns as module

	return module


def message(**values):
	"""A Communication as the hook sees it: a bag with `append`."""
	doc = types.SimpleNamespace(links=[], **values)
	doc.get = lambda key, default=None: (
		doc.links if key == "timeline_links" else getattr(doc, key, default)
	)
	doc.set = lambda key, value: setattr(doc, key, value)
	doc.append = lambda key, row: doc.links.append(types.SimpleNamespace(
		link_doctype=row["link_doctype"], link_name=row["link_name"],
		get=lambda k, d=None: row.get(k, d),
	))
	doc.reference_doctype = values.get("reference_doctype")
	doc.reference_name = values.get("reference_name")
	return doc


def answering(monkeypatch, concerns, *, contacts=(), emails=(), links=(),
              employees=(), has_employee=True):
	"""Point `frappe.get_all` at rows written here.

	One stub for four queries, keyed by doctype, because the alternative is
	four monkeypatched helpers and a test that passes when the module stops
	calling one of them.
	"""
	def get_all(doctype, filters=None, fields=None, pluck=None, **kwargs):
		filters = filters or {}
		if doctype == "Contact":
			wanted = set(filters.get("email_id", ("in", []))[1])
			return [row["name"] for row in contacts
			        if row["email_id"] in wanted]
		if doctype == "Contact Email":
			wanted = set(filters.get("email_id", ("in", []))[1])
			return [row["parent"] for row in emails if row["email_id"] in wanted]
		if doctype == "Dynamic Link":
			parents = set(filters.get("parent", ("in", []))[1])
			kinds = set(filters.get("link_doctype", ("in", []))[1])
			return [
				types.SimpleNamespace(**row) for row in links
				if row["parent"] in parents and row["link_doctype"] in kinds
			]
		if doctype == "Employee":
			field = next(k for k in concerns.EMPLOYEE_FIELDS if k in filters)
			wanted = set(filters[field][1])
			return [row["name"] for row in employees
			        if row.get(field) in wanted]
		raise AssertionError(f"unexpected query on {doctype}")

	monkeypatch.setattr(concerns.frappe, "get_all", get_all)
	monkeypatch.setattr(concerns.frappe.db, "exists",
	                    lambda *a, **k: has_employee)


# --------------------------------------------------------------------------- #
# A. The addresses on a message
# --------------------------------------------------------------------------- #

def test_the_sender_comes_first(concerns):
	"""`linking.add` makes the first link the primary reference, so the order
	here decides which record a thread is filed under."""
	doc = message(sender="h@alreem.ae", recipients="ops@ours.test, a@b.ae")
	assert concerns.addresses_on(doc)[0] == "h@alreem.ae"


def test_a_display_name_is_not_an_address(concerns):
	"""Frappe stores both shapes and the child table only ever holds the bare
	one, so a query against `Hala Nasser <h@x.ae>` matches nothing and says
	nothing."""
	doc = message(sender="Hala Nasser <h@alreem.ae>", recipients="")
	assert concerns.addresses_on(doc) == ["h@alreem.ae"]


def test_every_field_is_read_and_nothing_is_repeated(concerns):
	doc = message(sender="a@x.ae", recipients="b@x.ae; a@x.ae",
	              cc="c@x.ae", bcc="d@x.ae")
	assert concerns.addresses_on(doc) == ["a@x.ae", "b@x.ae", "c@x.ae", "d@x.ae"]


def test_a_circular_is_cut_off(concerns):
	"""Forty recipients is a circular, and forty rows on a record it is about
	none of in particular."""
	doc = message(sender="a@x.ae",
	              recipients=",".join(f"p{n}@x.ae" for n in range(40)))
	assert len(concerns.addresses_on(doc)) == concerns.MAX_ADDRESSES


def test_something_that_is_not_an_address_is_dropped(concerns):
	doc = message(sender="undisclosed-recipients", recipients="a@x.ae")
	assert concerns.addresses_on(doc) == ["a@x.ae"]


# --------------------------------------------------------------------------- #
# B. The two joins
# --------------------------------------------------------------------------- #

def test_a_contact_is_found_by_either_address(monkeypatch, concerns):
	"""`Contact.email_id` is the primary one and `Contact Email` holds the
	rest. Somebody writing from their second address is the same person."""
	answering(monkeypatch, concerns,
	          contacts=[{"name": "Hala", "email_id": "h@alreem.ae"}],
	          emails=[{"parent": "Sami", "email_id": "s2@alreem.ae"}])
	assert concerns.contacts_for(["h@alreem.ae", "s2@alreem.ae"]) == ["Hala", "Sami"]


def test_a_party_is_read_off_the_dynamic_links(monkeypatch, concerns):
	answering(monkeypatch, concerns, links=[
		{"parent": "Hala", "link_doctype": "Customer", "link_name": "Al Reem"},
	])
	assert concerns.parties_for(["Hala"]) == [("Customer", "Al Reem")]


def test_the_live_party_wins_over_the_one_it_became(monkeypatch, concerns):
	"""A contact is very often linked to both a Lead and the Customer that
	lead became. The customer is the record somebody is working; the lead is
	history by then, and `PARTIES` order is what says so."""
	answering(monkeypatch, concerns, links=[
		{"parent": "Hala", "link_doctype": "Lead", "link_name": "LEAD-9"},
		{"parent": "Hala", "link_doctype": "Customer", "link_name": "Al Reem"},
	])
	assert concerns.parties_for(["Hala"])[0] == ("Customer", "Al Reem")


def test_a_contact_linked_to_something_that_is_not_a_party_is_ignored(
		monkeypatch, concerns):
	"""A contact is also linked to a User, a Warehouse and anything else that
	ever attached one. A message is not about a warehouse — and the narrowing
	is in the query rather than after it, so the rows never arrive."""
	answering(monkeypatch, concerns, links=[
		{"parent": "Hala", "link_doctype": "Warehouse", "link_name": "Stores"},
	])
	assert concerns.parties_for(["Hala"]) == []


def test_a_person_is_found_by_any_of_three_fields(monkeypatch, concerns):
	answering(monkeypatch, concerns, employees=[
		{"name": "HR-EMP-1", "user_id": "omar@ours.test"},
		{"name": "HR-EMP-2", "company_email": "sami@ours.test"},
		{"name": "HR-EMP-3", "personal_email": "leila@gmail.test"},
	])
	assert concerns.people_for(
		["omar@ours.test", "sami@ours.test", "leila@gmail.test"]
	) == ["HR-EMP-1", "HR-EMP-2", "HR-EMP-3"]


def test_a_site_without_hrms_asks_nothing(monkeypatch, concerns):
	"""Three queries per message to find out a doctype is not installed is
	three queries a workspace that never bought OnePeople pays forever."""
	answering(monkeypatch, concerns, has_employee=False)
	assert concerns.people_for(["omar@ours.test"]) == []


# --------------------------------------------------------------------------- #
# C. What lands on the message
# --------------------------------------------------------------------------- #

def test_the_links_carry_their_own_provenance(monkeypatch, concerns):
	"""`address` is its own value beside `thread`, `text`, `manual` and
	`model`: `text` means somebody wrote an id we issue, and this means
	somebody wrote from a desk we know. A reader deciding whether to trust a
	link wants those apart."""
	answering(monkeypatch, concerns,
	          contacts=[{"name": "Hala", "email_id": "h@alreem.ae"}],
	          links=[{"parent": "Hala", "link_doctype": "Customer",
	                  "link_name": "Al Reem"}],
	          employees=[{"name": "HR-EMP-1", "user_id": "ops@ours.test"}])

	doc = message(sender="h@alreem.ae", recipients="ops@ours.test")
	assert concerns.place(doc) is True

	rows = [(row.link_doctype, row.link_name, row.get("custom_linked_by"))
	        for row in doc.links]
	assert rows == [
		("Customer", "Al Reem", "address"),
		("Employee", "HR-EMP-1", "address"),
	]


def test_a_message_about_nobody_adds_nothing(monkeypatch, concerns):
	answering(monkeypatch, concerns)
	doc = message(sender="stranger@nowhere.test", recipients="")
	assert concerns.place(doc) is False
	assert doc.links == []


def test_an_id_somebody_wrote_keeps_the_primary_reference(monkeypatch, concerns):
	"""A message naming an invoice is about the invoice. The customer it is
	also about is a second row — which is why `linking.place` runs this last,
	and it is the one ordering decision in that function that a reader would
	otherwise have to infer."""
	answering(monkeypatch, concerns,
	          contacts=[{"name": "Hala", "email_id": "h@alreem.ae"}],
	          links=[{"parent": "Hala", "link_doctype": "Customer",
	                  "link_name": "Al Reem"}])

	doc = message(sender="h@alreem.ae", recipients="")
	# As `from_text` would have left it.
	doc.reference_doctype = "Purchase Invoice"
	doc.reference_name = "PINV-0001"
	doc.append("timeline_links", {"link_doctype": "Purchase Invoice",
	                              "link_name": "PINV-0001",
	                              "custom_linked_by": "text"})

	concerns.place(doc)
	assert (doc.reference_doctype, doc.reference_name) == \
		("Purchase Invoice", "PINV-0001")
	assert len(doc.links) == 2


def test_the_same_party_is_not_linked_twice(monkeypatch, concerns):
	"""Two people from one firm on one message is one customer."""
	answering(monkeypatch, concerns,
	          contacts=[{"name": "Hala", "email_id": "h@alreem.ae"},
	                    {"name": "Sami", "email_id": "s@alreem.ae"}],
	          links=[{"parent": "Hala", "link_doctype": "Customer",
	                  "link_name": "Al Reem"},
	                 {"parent": "Sami", "link_doctype": "Customer",
	                  "link_name": "Al Reem"}])

	doc = message(sender="h@alreem.ae", recipients="s@alreem.ae")
	concerns.place(doc)
	assert len(doc.links) == 1


# --------------------------------------------------------------------------- #
# D. And the rule this must not break
# --------------------------------------------------------------------------- #

def test_a_link_is_still_not_a_grant():
	"""`linking.py` is emphatic and this changes nothing about it: filing a
	thread against a customer must not publish it to everybody who can read
	that customer.

	Read from the *parse tree* rather than from the text, and that is not
	fastidiousness: the first version of this grepped the source, and the
	module's own docstring says "nothing here calls `frappe.share`" — so the
	guard failed on the sentence promising the thing it was checking. A rule
	about what code does has to read code.
	"""
	import ast
	import pathlib

	tree = ast.parse((pathlib.Path(__file__).resolve().parent.parent
	                  / "apps/oneapp/oneapp/onemail/concerns.py").read_text())
	for node in ast.walk(tree):
		if isinstance(node, ast.Call):
			assert ast.unparse(node.func) != "frappe.share", (
				"a link is being turned into a grant"
			)
			for keyword in node.keywords:
				assert keyword.arg != "ignore_permissions", (
					f"{ast.unparse(node.func)} reads past the caller's own "
					f"permissions"
				)


def test_the_places_it_is_wired_are_the_two_it_should_be():
	"""`linking.place` calls it and nothing else does. A second caller would
	be a second set of rows with the same provenance and a different order."""
	import pathlib

	root = pathlib.Path(__file__).resolve().parent.parent / "apps/oneapp/oneapp"
	callers = [
		path.name for path in root.rglob("*.py")
		if "concerns.place(" in path.read_text() and path.name != "concerns.py"
	]
	assert callers == ["linking.py"], callers
