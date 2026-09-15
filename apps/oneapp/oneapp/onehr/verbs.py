"""What a verb over somebody else's app has to do with what it gets back.

`hiring.py` was three verbs and could say this in its own docstring. There are
now thirty across six modules, and two sentences are repeated in all of them, so
they live here.

## HRMS answers with an unsaved document

Almost every `frm.add_custom_button` in HRMS ends the same way: a whitelisted
method returns `frappe.new_doc(...)` or `get_mapped_doc(...)`, the desk syncs it
into an unsaved form, and a person looks at it before pressing Save. Frappe's
own `get_mapped_doc` is built for exactly that — it *returns* a document and
never inserts one.

This product has no unsaved form to sync into, so there are two honest answers
and which one applies is decided by the document, not by taste:

**`filled`** — for a document whose interesting fields are scalars. The verb
answers `{"create": {"screen": …, "values": …}}` and the engine opens that
screen's own New dialog with them in it. Same as the desk: nothing is written
until somebody presses Save, and the validation, the required-ness and the
permission are the target screen's rather than the verb's.

**`drafted`** — for a document whose point is its child rows. A New dialog
carries a flat dict, so a journal entry with two account lines or a claim
carrying the advance it is against cannot go through one — the rows would be
silently dropped and the reader would press Save on a document missing the
thing it was made for. So the verb inserts it as a **draft** and answers
`{"open": …}`. A draft is still a document nobody has committed to: it is
reviewed and submitted on its own screen, which is the same two steps in the
same order.

## And a refusal says which state it wanted

Every verb in OnePeople is offered on every row — `hiring.py` states the rule
and the reason: a button that vanishes at some statuses is a button nobody
learns is there. That only works if the refusal names the state it wanted and
the state it found, so `refuse` is the one sentence shape all of them use.
"""

import frappe
from frappe import _

#: Frappe's own bookkeeping, which is never a value a New dialog should carry.
#: `name` is on the list because a mapped document has none — it is unsaved —
#: and sending the empty string would fill the dialog's id field with nothing
#: and mark it touched.
NOT_VALUES = {
	"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
	"doctype", "parent", "parentfield", "parenttype", "amended_from",
	"naming_series",
}


def refuse(doc, wanted: str) -> None:
	"""Say which state this is in, and which one the verb wanted."""
	state = doc.get("status") or doc.get("workflow_state")
	if not state:
		state = {0: _("a draft"), 1: _("submitted"), 2: _("cancelled")}.get(
			int(doc.get("docstatus") or 0), _("a draft")
		)
	frappe.throw(_("{0} is {1}. {2}").format(doc.name, _(str(state)), wanted))


def filled(doc, screen: str, keep=()) -> dict:
	"""An unsaved document, as a New dialog on one of this space's screens.

	Scalars only. A child table is a list and a dialog carries a dict, so a
	`Table` field would arrive as something the form cannot render — and
	dropping it in silence is what `drafted` exists to avoid. `keep` names
	fields to send anyway, for the two cases where an empty value is the point.
	"""
	values = {}
	for field in doc.meta.fields:
		if field.fieldname in NOT_VALUES:
			continue
		if field.fieldtype in ("Table", "Table MultiSelect"):
			continue
		held = doc.get(field.fieldname)
		if held in (None, "", 0) and field.fieldname not in keep:
			continue
		values[field.fieldname] = held
	return {"create": {"screen": screen, "values": values}}


def drafted(doc, screen: str) -> dict:
	"""The same document, inserted as a draft and opened where it lives.

	For anything whose child rows are the point. `ignore_permissions` is not
	passed: the verb has already checked that this reader may write the record
	it came *from*, and whether they may create the thing it becomes is a
	second question Frappe is the right one to answer.
	"""
	doc.insert()
	return {"open": {"screen": screen, "name": doc.name}}
