"""Print formats, reached from a record."""

import frappe
from oneapp.oneapp_core import collab, dashboard, docflow, fieldtypes, printing, showcase
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
