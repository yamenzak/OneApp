"""The file somebody attached to a form, written.

`docs/ONEFORMS.md` §14, stage 11. This is the one write in OneForms that is not
`frappe…accept`, and it exists because `accept`'s own attachment path does not
work for the reader this module was built for.

**Measured, in the browser.** `accept` writes the `File` as the current user,
and on a public form that user is Guest. `File` grants create to `All`, and
Guest is not in `All`, so a keyed applicant attaching a CV got *"User Guest does
not have doctype access via role permission for document File"* — after their
submission had already been saved. Frappe's own guest web form has the same
hole; ours cannot.

So the attach fields are taken out of the payload before `accept` sees them, and
written here afterwards. Three things follow, and the second is the one worth
the module:

* **It only ever attaches to the document `accept` just made.** Not a name from
  the payload — the one that came back. So the authorisation is the one that
  already happened: the key, the published check, the login rule, all of it.
* **The cap is enforced here, not in the browser.** Until this, nothing on the
  server looked at the size at all: `FileField.vue` checked before reading, and
  anybody posting straight to `send` could put half a gigabyte of base64 in a
  string. A rule that only ever ran in a renderer is not a rule, which is the
  same sentence `showing.py` opens with.
* **The file is private.** `accept` does not set it and a CV at a guessable URL
  is a data leak. Whoever may read the record may read what is attached to it;
  nobody else gets a URL.
"""

import base64
import re

import frappe
from frappe import _

#: The two fieldtypes that are a file rather than a value.
ATTACHES = ("Attach", "Attach Image")

#: What a form allows when it names no cap of its own, in MB. Frappe's own
#: default for a site, restated because this check runs before the framework's.
DEFAULT_MB = 10

#: `filename,data:<mime>;base64,<payload>` — the shape `accept` splits on and
#: therefore the shape the page sends. Parsed rather than trusted: the filename
#: reaches a `File` document and the mime reaches a `Content-Type`.
CARRIED = re.compile(
	r"^(?P<name>[^,]*),data:(?P<mime>[a-z0-9.+/-]*);base64,(?P<payload>.*)$",
	re.I | re.S,
)


def taken(doc, values: dict) -> dict:
	"""The attach fields, lifted out of the payload. Mutates `values`.

	Out before `accept` rather than after, because `accept` would otherwise
	write the same file itself and fail — see the module docstring.
	"""
	out = {}
	for row in doc.web_form_fields or []:
		if row.fieldtype not in ATTACHES:
			continue
		said = values.pop(row.fieldname, "")
		if said and str(said).startswith(("data:", "")) and "base64," in str(said):
			out[row.fieldname] = str(said)
	return out


def onto(doc, made, files: dict) -> list:
	"""Write each file and put its url on the document that was just created.

	`made` is what `accept` returned, which is the whole of the authorisation:
	this never looks up a document by a name somebody sent.
	"""
	if not made or not files:
		return []

	cap = (int(doc.max_attachment_size or 0) or DEFAULT_MB) * 1024 * 1024
	written = []
	for fieldname, said in files.items():
		content = _decoded(said, cap)
		if not content:
			continue
		name, raw = content
		record = frappe.get_doc({
			"doctype": "File",
			"file_name": name,
			"attached_to_doctype": made.doctype,
			"attached_to_name": made.name,
			# A CV at a guessable URL is a data leak, and `accept` does not set
			# this. Whoever may read the record may read what is on it.
			"is_private": 1,
			"content": raw,
		})
		# The one `ignore_permissions` on the public side, and it is against a
		# document this request just created through the key. Guest cannot
		# create a `File` — `File` grants create to `All` and Guest is not in
		# `All` — which is the whole reason this module exists.
		record.insert(ignore_permissions=True)
		frappe.db.set_value(made.doctype, made.name, fieldname, record.file_url,
		                    update_modified=False)
		written.append(record.file_url)
	return written


def _decoded(said: str, cap: int):
	"""`(filename, bytes)`, or nothing, refusing anything over the cap.

	The size is checked on the *decoded* length and before the decode, from the
	base64 length — a payload is a third larger than the file it carries, so
	decoding half a gigabyte in order to then refuse it is the failure this
	check exists to avoid, not a step on the way to it.
	"""
	found = CARRIED.match(said or "")
	if not found:
		return None

	payload = found["payload"]
	# Four base64 characters carry three bytes. Close enough to refuse on, and
	# it costs nothing.
	if (len(payload) * 3) // 4 > cap:
		frappe.throw(_("That file is larger than this form accepts."))

	try:
		raw = base64.b64decode(payload, validate=False)
	except Exception:
		frappe.throw(_("That file could not be read."))

	if len(raw) > cap:
		frappe.throw(_("That file is larger than this form accepts."))

	# Scrubbed, because it becomes a filename on disk and a header. Frappe
	# scrubs again on save; this is so the refusal is ours and readable.
	name = (found["name"] or "").strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
	name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.") or "attachment"
	return name[:140], raw
