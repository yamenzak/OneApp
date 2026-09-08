"""Print formats, reached from a record.

The rendering is Frappe's and so is the PDF; what is here is the screen.
Frappe's own print endpoints take a doctype and a name, and ours take a space
and a screen — so a record this screen would not list is not one it prints,
and a doctype the space never granted has no route here at all.

See `onespace.printing` for what each piece of the stack actually is.
"""

import frappe
from frappe import _
from oneapp.onespace import collab, dashboard, docflow, fieldtypes, printing, showcase
from .guard import _reachable


@frappe.whitelist(methods=["GET"])
def print_options(space_code: str, screen: str, name: str) -> dict:
	"""What this record can be printed as: formats, letter heads, defaults."""
	doctype = _reachable(space_code, screen, name)
	return {
		"formats": printing.formats(doctype),
		"letter_heads": printing.letter_heads(),
		"settings": printing.settings(),
	}


@frappe.whitelist(methods=["GET"])
def print_preview(space_code: str, screen: str, name: str, format: str = "",
                  letterhead: str = "", language: str = "") -> dict:
	"""The rendered format, as HTML and its stylesheet.

	HTML back to a browser that will put it in an iframe, which is where the
	`style` half matters: a print format's CSS is written to win against a
	blank page, and dropping it into the app's own document would restyle the
	app. See `PrintDialog`.
	"""
	doctype = _reachable(space_code, screen, name)
	return printing.preview(doctype, name, format, letterhead, language)


@frappe.whitelist(methods=["GET"])
def print_pdf(space_code: str, screen: str, name: str, format: str = "",
              letterhead: str = "", language: str = ""):
	"""The same thing as a PDF, downloaded.

	Written into the response rather than returned: a PDF is bytes, and an
	endpoint that base64s them into JSON asks the browser to rebuild a file it
	could have been handed.
	"""
	doctype = _reachable(space_code, screen, name)
	content = printing.pdf(doctype, name, format, letterhead, language)

	frappe.local.response.filename = "{0}.pdf".format(
		str(name).replace(" ", "-").replace("/", "-")
	)
	frappe.local.response.filecontent = content
	frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["GET"])
def print_many(space_code: str, screen: str, names: str | list, format: str = "",
               letterhead: str = "", language: str = ""):
	"""A selection, as one PDF.

	The desk's bulk print, bounded the way everything here is: every record is
	re-read through `_reachable`, so a row this screen would not list is not one
	it prints — a selection is a list of ids from the browser, and ids are the
	one thing a browser can invent.

	`GET` because it reads: a print writes nothing, and a download is a
	navigation rather than a fetch.
	"""
	wanted = frappe.parse_json(names) if isinstance(names, str) else names
	wanted = [str(one) for one in (wanted or []) if str(one or "").strip()]
	if not wanted:
		frappe.throw(_("Nothing was selected to print."))

	doctype = ""
	for name in wanted[:printing.MAX_BUNDLE]:
		doctype = _reachable(space_code, screen, name)

	content = printing.bundle(
		doctype, wanted[:printing.MAX_BUNDLE], format, letterhead, language,
	)

	frappe.local.response.filename = "{0}.pdf".format(
		str(screen or doctype).replace(" ", "-").replace("/", "-")
	)
	frappe.local.response.filecontent = content
	frappe.local.response.type = "pdf"
