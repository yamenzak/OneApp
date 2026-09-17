"""The columns a pipeline is made of.

`docs/ONECRM.md`. ERPNext's `Sales Stage` is a row with a name and nothing
else: no order, so a board drawn from it comes out Negotiation, Prospecting,
Proposal; no colour; and no way for the engine to ask which column means *won*.
Its `status` is a fixed Select of six words, three of which are about a
quotation rather than about a deal.

So a stage is `One Deal Stage` — a row a workspace renames, recolours, reorders
and adds to — and what the engine needs from each is a **category**, which is
how "did we win it" has an answer without reading the word somebody chose.

The same shape as `onetask/states.py`, deliberately: a board of work and a board
of deals are the same problem, and the second one arriving with a different
vocabulary would be the thing `docs/UNIFICATION.md` exists to complain about.
"""

import frappe

STAGE = "One Deal Stage"


def ensure(stages) -> int:
	"""Write the default columns, once.

	Idempotent by name, and it never edits one that is already there: a
	workspace that renamed a stage or moved it should not find it back the way
	it shipped after the next migration. Which also means a stage *added* to
	the shipped set lands beside whatever was at its number — the boards break
	the tie on the name, so the order is at least stable, and renumbering
	somebody's pipeline to make room is not ours to do.
	"""
	written = 0
	for name, category, probability, colour, position in stages:
		if frappe.db.exists(STAGE, name):
			continue
		frappe.get_doc({
			"doctype": STAGE, "stage_name": name, "category": category,
			"probability": probability, "colour": colour, "position": position,
		}).insert(ignore_permissions=True)
		written += 1
	return written


def category_of(stage: str) -> str:
	"""What a column means, for the code that has to ask."""
	if not stage:
		return ""
	return frappe.db.get_value(STAGE, stage, "category") or ""


#: What a category is, in ERPNext's own words.
#:
#: Four of their six. The two left out are theirs to write rather than ours:
#: `Quotation` is set by their own controller when a quotation is raised
#: against the deal, and `Replied` is mail's. A workspace that wants a column
#: called Quoted has one, and it is Ongoing until somebody moves it on — which
#: is the same answer `onetask/states.py` gives about Pending Review.
STATUS_OF = {
	"Open": "Open",
	"Ongoing": "Open",
	"On hold": "Open",
	"Won": "Converted",
	"Lost": "Lost",
}


def status_of(stage: str) -> str:
	"""ERPNext's status for the column a deal is in."""
	return STATUS_OF.get(category_of(stage), "")


def probability_of(stage: str):
	"""What a deal at this stage is assumed to be worth, as a percentage."""
	if not stage:
		return None
	return frappe.db.get_value(STAGE, stage, "probability")
