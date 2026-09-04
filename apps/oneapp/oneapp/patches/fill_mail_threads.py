"""Give the mail already on this site its conversation keys.

New messages get one on insert. These are the ones that arrived before the
column existed, and without this every conversation older than the upgrade
would read as one message per row — which is worse than the subject grouping it
replaces, not better.

In batches, ordered oldest first, so a parent is keyed before its replies and
each one can inherit rather than fall back.
"""

import frappe

from oneapp.oneapp_core.email.threading import THREAD_FIELD, key_for

BATCH = 500


def execute():
	if not frappe.db.has_column("Communication", THREAD_FIELD):
		return

	while True:
		rows = frappe.get_all(
			"Communication",
			filters={
				"communication_medium": "Email",
				THREAD_FIELD: ("in", ["", None]),
			},
			fields=["name", "subject", "in_reply_to"],
			order_by="creation asc",
			limit_page_length=BATCH,
		)
		if not rows:
			return

		for row in rows:
			frappe.db.set_value(
				"Communication", row.name, THREAD_FIELD, key_for(row),
				update_modified=False,
			)
		frappe.db.commit()
