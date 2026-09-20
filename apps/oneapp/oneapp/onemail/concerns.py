"""Who a conversation is about, from the addresses on it.

`docs/CLEANUP.md` §7 asks for OneAI in the middle: a message arrives and the
task, the person and the party it concerns are proposed, and OneTask, OneHR
and OneCRM receive them. `intelligence.py` does the task — `mail.notice` offers
a task and a diary entry off the proposing registry. This is the other two, and
**none of it is a model**, which is the point rather than a shortcut.

`linking.py` states the rule this follows: *a model is worth nothing until the
cases it is not needed for are already handled without it.* And the party and
the person a message concerns are, in the overwhelming case, not a judgement at
all. Somebody wrote from an address. Frappe already knows whose address it is —
`Contact`, plus `Contact Email` for the second one they write from — and
already knows what that contact belongs to, in the `Dynamic Link` rows every
party doctype hangs off. HRMS already knows which Employee an address belongs
to, in three fields.

Two joins, no prompt, no credits, and an answer that is either right or absent.

`intelligence.noticing()` says why the model is not asked this, and it is worth
repeating here because the temptation runs the other way: *"placing a message
against a quotation is linking, which is a retrieval problem rather than a
prompting one. Offering it here would be offering a guess."* A guessed customer
on a thread is a customer's correspondence filed under somebody else's account.

## What it writes, and what that is not

A `Communication Link` row per party and per person, with `custom_linked_by`
set to `address` — the fifth provenance value, beside `thread`, `text`,
`manual` and `model`. It is its own value rather than folded into `text`
because it answers a different question: `text` means somebody wrote an id we
issue, and this means somebody wrote *from a desk we know*. A reader deciding
whether to trust a link wants those apart.

**A link is not a grant**, and this changes nothing about that. `linking.py`
is emphatic and the same applies: nothing here calls `frappe.share`, and a
record's correspondence reader still filters by the reader's access to each
message rather than to the record. Filing a thread against a customer does not
publish it to everybody who can read that customer.

## Where the three spaces receive it

Nowhere new, and that is the design. A `Communication Link` row is what every
record's Correspondence tab already reads, so a thread linked to a Customer
appears on the customer in OneCRM, one linked to an Employee on the person in
OneHR, and the task `mail.notice` proposes lands in OneTask when somebody
presses Apply. There is no message, no queue and nothing to keep in step —
three spaces receive this because they were already reading the table it
writes.

## Not built

**The lead that does not exist yet.** A stranger writing in from a company
nobody has recorded is the case a party cannot be resolved for, and proposing
*a new Lead* out of it is a genuine OneCRM feature and a different one: it
creates a record rather than linking one, so it belongs in the proposing
registry beside a task, with a card somebody approves. `docs/ONECRM.md` is
where that argument goes.
"""

import frappe

from oneapp.onemail import linking

#: The fifth provenance. Beside `thread`, `text`, `manual` and `model` in
#: `linking.py`, which is where the other four are declared and where the
#: reader that shows them lives.
BY_ADDRESS = "address"

#: What OneCRM owns, in the order a link is preferred when an address belongs
#: to more than one. A contact is very often linked to both a Lead and the
#: Customer that lead became, and the customer is the live record — the lead is
#: history by then.
#:
#: `Supplier` is on the list and is OneBook's rather than OneCRM's
#: (`onebook/README.md` §3). It is here because the question this answers is
#: "which party", and a supplier is one; which space owns the doctype decides
#: who may edit it, not whether a message can be about it.
PARTIES = ("Customer", "Supplier", "Prospect", "Lead")

#: Where HRMS keeps an address. Three fields, and the order is by how much the
#: workspace controls it: the login is ours, the company address is the one HR
#: typed, and the personal one is whatever somebody wrote on a form.
EMPLOYEE_FIELDS = ("user_id", "company_email", "personal_email")

#: How many addresses one thread is resolved for. A message with forty
#: recipients is a circular, and resolving all of them is forty rows on a
#: record that is about none of them in particular.
MAX_ADDRESSES = 12


def addresses_on(doc) -> list[str]:
	"""Every address on one message, sender first, lowercased and deduplicated.

	Sender first because a message is more about who wrote it than about who
	was copied, and `add` makes the first link the primary reference.
	"""
	raw = [doc.get("sender") or ""]
	for field in ("recipients", "cc", "bcc"):
		raw += str(doc.get(field) or "").replace(";", ",").split(",")

	found, seen = [], set()
	for one in raw:
		email = _bare(one)
		if not email or email in seen:
			continue
		seen.add(email)
		found.append(email)
	return found[:MAX_ADDRESSES]


def _bare(address: str) -> str:
	"""`Hala Nasser <h@x.ae>` as `h@x.ae`. Frappe stores both shapes."""
	one = (address or "").strip()
	if "<" in one and ">" in one:
		one = one[one.index("<") + 1:one.index(">")]
	one = one.strip().strip("'\"").lower()
	return one if "@" in one else ""


def contacts_for(addresses: list[str]) -> list[str]:
	"""The Contacts these addresses belong to.

	`people._contacts` is the same join and answers with a profile per address;
	this wants the names, so it asks for them directly rather than mapping a
	richer answer down to one column.
	"""
	if not addresses:
		return []

	names = set(frappe.get_all(
		"Contact", filters={"email_id": ("in", addresses)}, pluck="name"))
	names |= set(frappe.get_all(
		"Contact Email",
		filters={"email_id": ("in", addresses), "parenttype": "Contact"},
		pluck="parent"))
	return sorted(names)


def parties_for(contacts: list[str]) -> list[tuple[str, str]]:
	"""What those contacts belong to, as `(doctype, name)`.

	`Dynamic Link` is where every party doctype hangs its contacts, which is
	why one query answers for all four rather than four queries answering for
	one each.

	Narrowed to `PARTIES` in the query and not afterwards: a contact is also
	linked to a User, a Warehouse and anything else that ever attached one,
	and a message is not about a warehouse.
	"""
	if not contacts:
		return []

	rows = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "parent": ("in", contacts),
		         "link_doctype": ("in", list(PARTIES))},
		fields=["link_doctype", "link_name"],
	)
	found = {(row.link_doctype, row.link_name) for row in rows if row.link_name}
	# In `PARTIES` order, so a contact linked to both a Lead and the Customer
	# it became links to the customer first.
	return sorted(found, key=lambda one: (PARTIES.index(one[0]), one[1]))


def people_for(addresses: list[str]) -> list[str]:
	"""The Employees these addresses belong to.

	Skipped whole on a site without HRMS rather than guarded per field: OneHR
	is the only space that has this doctype, and a workspace without it should
	not pay three queries per message to find that out.
	"""
	if not addresses or not frappe.db.exists("DocType", "Employee"):
		return []

	found = set()
	for field in EMPLOYEE_FIELDS:
		found |= set(frappe.get_all(
			"Employee", filters={field: ("in", addresses)}, pluck="name"))
	return sorted(found)


def place(doc) -> bool:
	"""Link this message to the parties and people its addresses name.

	In memory, on a document not yet saved — the same contract `linking.place`
	keeps, and for the same reason: `before_insert` is where this runs, so the
	rows are part of the write rather than a second one.

	Returns whether anything was added, which is what `linking.on_insert` needs
	to know to record provenance afterwards.
	"""
	addresses = addresses_on(doc)
	if not addresses:
		return False

	added = False
	for doctype, name in parties_for(contacts_for(addresses)):
		added = linking.add(doc, doctype, name, BY_ADDRESS) or added
	for name in people_for(addresses):
		added = linking.add(doc, "Employee", name, BY_ADDRESS) or added
	return added
