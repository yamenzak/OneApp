"""Give every file that arrived before the Drive existed a kind.

`custom_kind` is what the filter chips read and what the icon comes from, and it
is derived on insert — so on a site with two hundred existing attachments,
everything uploaded before this shipped would sit under Other for ever and the
"show me the drawings" chip would find nothing.

Unlike `custom_status`, whose absence honestly means Active, an absent kind
means nothing at all: it is not a state, it is an unanswered question. So this
one is worth a backfill and that one is not.

The kind comes from the name, exactly as it does on insert — the same function,
so a file backfilled here and a file uploaded tomorrow cannot disagree.
"""

import frappe

from oneapp.oneapp_core.drive import KIND_FIELD, kind_of


def execute():
	from oneapp.install import create_custom_fields

	# Patches run before `after_migrate`, which is where the custom fields are
	# made — so on a site seeing this for the first time the column does not
	# exist yet and every write below would be silently dropped. The same trap
	# `fill_mail_threads` documents, and the same way out.
	create_custom_fields()

	rows = frappe.get_all(
		"File",
		filters={KIND_FIELD: ["in", ["", None]]},
		fields=["name", "file_name", "is_folder"],
		limit_page_length=0,
	)

	for row in rows:
		frappe.db.set_value(
			"File",
			row.name,
			KIND_FIELD,
			kind_of(row.file_name, row.is_folder),
			update_modified=False,
		)

	frappe.db.commit()
	return len(rows)
