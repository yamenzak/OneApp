"""The word "Assistant" stops being a stored value and goes back to a default.

`assistant_name` was declared with `default="Assistant"`, so every site that
ever created the single wrote that word into the column. When the assistant
got a name of its own, `identity()`'s fallback never ran anywhere: a stored
value beats a default, and the stored value was the old name.

So the column loses the default (`scripts/doctypes/ai.py`) and this clears
what the default put there. Only the exact word, and only where the workspace
has not renamed it — a workspace that typed "Assistant" on purpose is
indistinguishable from this, and the cost of being wrong in that direction is
that they type it again, against a field whose placeholder now says what
leaving it empty means.
"""

import frappe

#: What the column used to be filled with.
WAS = "Assistant"


def execute():
	# A Single has no table of its own, so there is nothing to guard on but
	# whether the doctype is there at all — and on a site where it is not,
	# there is no row in `tabSingles` either and the update matches nothing.

	# A Single, so the value is a row in `tabSingles` rather than a column.
	# `set_single_value` would run the doctype's own validation and rewrite
	# every other field with it; this changes one row and nothing else.
	frappe.db.sql(
		"""update `tabSingles` set value = ''
		   where doctype = 'OneAI Settings'
		     and field = 'assistant_name' and value = %s""",
		WAS,
	)
	frappe.clear_document_cache("OneAI Settings", "OneAI Settings")
	frappe.db.commit()
