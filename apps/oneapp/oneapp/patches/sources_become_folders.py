"""A transit source stops being four kinds and two fields, and becomes a folder.

`sftp_sources_become_mounts` moved the credentials out; this moves the rest.
Before it there were four kinds — `Upload`, `Folder`, `HTTP`, `Socket` — a
`remote_folder` link, a `folder` path inside that mount, and a `format`
dropdown naming a specification. After it there are three kinds, one `folder`
holding a single address that works for both a Drive folder and a mounted one
(`onestorage/walk.py`), and no format at all except on a stream.

Three moves, and only the first can lose anything:

**`Upload` becomes `Folder` with nothing in it.** An upload source had no
folder because an upload had nowhere to land; there is no path to migrate and
no folder to guess. The row is kept, marked Paused, and told in
`last_message` what it needs — guessing a folder would be worse, because the
guess would silently start reading somebody's Drive.

**`Folder` keeps its mount and its path.** `remote_folder` becomes the
Dynamic Link's target with `folder_type` set to Remote Folder, and the old
`folder` — which was a path inside the mount, not a folder — becomes
`subfolder`. `sources.folder_key` composes the two back into the one address
`onestorage/walk.py` takes.

**`Socket` becomes `Stream`,** and is the one kind whose `format` survives —
a stream has to name its dialect, because the handshake differs per protocol.
Every other source's format is cleared, since the file now says what it is.
"""

import frappe


def execute():
	if not frappe.db.table_exists("Transit Source"):
		return

	rows = frappe.get_all(
		"Transit Source",
		fields=["name", "kind", "folder", "remote_folder", "format", "status"],
		limit_page_length=0,
	)

	for row in rows:
		fresh = {}

		if row.kind == "Socket":
			fresh["kind"] = "Stream"

		elif row.kind == "Folder":
			if row.remote_folder:
				fresh["folder_type"] = "Remote Folder"
				fresh["subfolder"] = row.folder or ""
				fresh["folder"] = row.remote_folder
			fresh["format"] = ""

		elif row.kind == "Upload":
			fresh["kind"] = "Folder"
			fresh["folder_type"] = "File"
			fresh["folder"] = ""
			fresh["format"] = ""
			fresh["status"] = "Paused"
			fresh["last_message"] = (
				"Uploads now land in a folder. Pick one in Files and unpause "
				"this source; every file under it will be read and identified."
			)

		elif row.kind == "HTTP":
			fresh["format"] = ""

		if fresh:
			frappe.db.set_value("Transit Source", row.name, fresh,
			                    update_modified=False)

	# The column stops being read the moment the doctype no longer declares it,
	# and the sync does not drop columns. Left in place on purpose: a workspace
	# that wants to know which mount a source used to name can still find out,
	# and dropping a column in a patch is the one migration that cannot be
	# undone by re-running it.
	frappe.db.commit()
