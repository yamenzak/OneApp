"""Give every text file that shares an object one of its own.

`File.validate_duplicate_entry` points a new row at an existing object when the
bytes match, which is right for an upload and wrong for a file created empty to
be typed into: every `.txt`, `.md` and `.csv` `make_text` ever created started
as the same single newline, so they were all handed the same `file_url`. Editing
one rewrote all of them, because `save_text` writes back through that URL.

The creation paths no longer do this — see the flag in `docs/writing.make_text`
— but rows made before that fix still point at each other, and the damage is
silent and lands on the *next* edit rather than now. So each of them gets its
own object, holding whatever the shared one currently holds.

Only the local path can be affected. An R2 object's key is
`tenants/…/<File.name>/<file_name>` — see `storage/r2.object_key` — so two rows
cannot share one there however identical their bytes.

The oldest row in each group keeps the object it has. That is not arbitrary: it
is the one a genuine duplicate upload would also be pointing at, where sharing
is correct and re-splitting would double what the workspace is billed for.

The work itself is `docs.text.own_object`, which is also what the two creation
paths call. One function, so a row split here and a row created tomorrow cannot
disagree about what owning your own object means.
"""

import frappe

from oneapp.onedoc.text import is_text, own_object

#: What a local object's URL looks like. An R2-backed row's does not, and the
#: R2 ones cannot be shared in the first place.
LOCAL = ("/files/", "/private/files/")


def execute():
	shared = frappe.db.sql("""
		SELECT file_url
		FROM `tabFile`
		WHERE is_folder = 0 AND IFNULL(file_url, '') != ''
		GROUP BY file_url
		HAVING COUNT(*) > 1
	""", as_dict=True)

	split = 0
	for group in shared:
		if not group.file_url.startswith(LOCAL):
			continue

		rows = frappe.get_all(
			"File",
			filters={"file_url": group.file_url, "is_folder": 0},
			fields=["name", "file_name", "is_private"],
			order_by="creation asc",
		)
		# The first keeps the object. Only the text files behind it are the ones
		# that would overwrite it, so only they are moved.
		for row in rows[1:]:
			if not is_text(row.file_name):
				continue
			try:
				if own_object(frappe.get_doc("File", row.name)):
					split += 1
			except Exception:
				# The object is gone. Nothing to split, and nothing this can
				# fix — the row was broken before it was also shared.
				continue

	frappe.db.commit()
	return split
