"""Read state was a list of ids under each person. Now it is a column.

`oneapp_mail_seen` held, per person, the messages that person had opened —
the per-person unread model `mailbox/flags.py` used to describe. Read is the
mailbox's own state now (`Communication.seen`, kept the same as IMAP's
`\\Seen` in both directions), so those lists are folded in and removed.

**A union, not an intersection.** On a shared address two people had read
different things and there is no way to keep both; marking a message read
because *somebody* read it is the answer that loses the least, and it is what
the mailbox flag would have said anyway. The other direction — read only what
everybody had read — would hand people back mail they had already dealt with.

The rows are dropped afterwards so the defaults stop being loaded on every
request, and so a downgrade does not quietly resurrect a stale list.
"""

import frappe

KEY = "oneapp_mail_seen"
BATCH = 500


def execute():
	rows = frappe.get_all(
		"DefaultValue",
		filters={"defkey": KEY},
		fields=["name", "defvalue"],
		limit_page_length=0,
	)
	if not rows:
		return

	names = set()
	for row in rows:
		names.update(filter(None, (row.defvalue or "").split(",")))

	names = sorted(names)
	for at in range(0, len(names), BATCH):
		frappe.db.set_value(
			"Communication",
			{"name": ("in", names[at:at + BATCH])},
			"seen",
			1,
			update_modified=False,
		)

	frappe.db.delete("DefaultValue", {"defkey": KEY})
	frappe.clear_cache()
