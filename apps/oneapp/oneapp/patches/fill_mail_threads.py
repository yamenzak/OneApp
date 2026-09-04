"""Give the mail already on this site its conversation keys.

New messages get one on insert. These are the ones that arrived before the
column existed, and without this every conversation older than the upgrade
would read as one message per row — which is worse than the subject grouping it
replaces, not better.

In batches, ordered oldest first, so a parent is keyed before its replies and
each one can inherit rather than fall back.

It makes its own column first, and that is the whole reason this note exists.
Patches run *before* `after_migrate`, which is where `create_custom_fields`
lives — so on the one site this patch is for, the site upgrading into the
column, `has_column` was False, the patch returned, and Frappe wrote it into
`Patch Log` as done. It could never run again. Every message older than the
upgrade kept a null key for good, and nothing looked wrong: the readers fall
back to the subject, so the mail still grouped and the specs still passed.
Creating the field here is idempotent and costs nothing on a site that has it.
"""

import frappe

from oneapp.install import create_custom_fields
from oneapp.oneapp_core.email.threading import THREAD_FIELD, key_for

BATCH = 500


def execute():
	if not frappe.db.has_column("Communication", THREAD_FIELD):
		create_custom_fields()
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
