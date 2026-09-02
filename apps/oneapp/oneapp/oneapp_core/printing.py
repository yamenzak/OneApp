"""Printing: formats, letter heads, settings, and the PDF at the end of them.

The whole stack is Frappe's and every piece of it is worth using rather than
rebuilding, for a reason that is easy to miss until you try: **a print format
is not a template we render, it is a document the framework renders.**
`frappe.get_print` walks the format, resolves the letter head, applies the
print style, honours the page size and the margins, runs the field renderers,
and hands the result to whichever PDF engine the site is configured for. Every
one of those is a decision somebody already made carefully, and a second
renderer of ours would be a second set of them, drifting.

So this module is a *gate* and a *shape*, and neither is small:

**The gate.** Frappe's own print endpoints take a doctype and a name and check
`read` or `print` on the document. Ours take a space and a screen, resolve the
doctype from the manifest, and re-read the record through `record()` — which
applies the screen's own filters and this person's User Permissions. So a
record this screen would not list is not one it will print, and a doctype the
space never granted has no route here at all.

**The shape.** The desk offers a print dialog with eleven controls, several of
which are about wkhtmltopdf. A workspace member wants a format, a letter head
and a PDF; the rest belongs in settings, once, for everybody. What is offered
here is that short list, and the long one lives in `workspace.py` under
Printing.

What is deliberately *not* here: rendering. There is no HTML in this file.
"""

import frappe
from frappe import _

# How many formats one picker offers. A doctype with more than this has a
# naming problem rather than a printing one.
FORMATS = 50

# The page sizes Frappe's own Print Settings offers, and the only ones a
# workspace may pick. `Custom` is Frappe's escape hatch for a size in
# millimetres; it is offered, and the two boxes it needs come with it.
PAGE_SIZES = ("A4", "Letter", "Legal", "A3", "A5", "Custom")

# Which engine turns the HTML into a PDF. Frappe ships both and they are not
# interchangeable: wkhtmltopdf is old WebKit and gets modern CSS wrong;
# headless Chrome renders what a browser renders and is slower to start.
PDF_ENGINES = ("chrome", "wkhtmltopdf")


def formats(doctype: str) -> list[dict]:
	"""The formats this doctype can be printed with, and which is standard.

	Frappe's own `Standard` is always available and always last: it is the
	fallback the framework renders when a doctype has no format of its own, and
	putting it first would make it the thing people pick by accident.
	"""
	rows = frappe.get_all(
		"Print Format",
		filters={"doc_type": doctype, "disabled": 0},
		fields=["name", "print_format_type", "standard", "format_data",
		        "print_format_builder_beta", "custom_format", "raw_printing"],
		order_by="standard asc, name asc",
		limit_page_length=FORMATS,
	)

	default = frappe.db.get_value("Property Setter", {
		"doc_type": doctype, "property": "default_print_format",
	}, "value")

	found = [
		{
			"name": row["name"],
			# Whether it came out of the builder, which is the only kind we can
			# open in ours. A format written as HTML or as raw printer commands
			# is still printable and simply is not editable here — and a
			# standard one ships in an app's source tree, so it is drawn here
			# and saved nowhere.
			"built": bool(row.get("print_format_builder_beta"))
			         and not row.get("custom_format")
			         and not row.get("raw_printing"),
			"standard": row.get("standard") == "Yes",
			"default": row["name"] == default,
		}
		for row in rows
	]

	found.append({
		"name": "Standard", "built": False, "standard": True,
		"default": not default,
	})
	return found


def letter_heads() -> list[dict]:
	"""Every letter head on the workspace, and which one is the default."""
	return [
		{"name": row["name"], "default": bool(row["is_default"])}
		for row in frappe.get_all(
			"Letter Head",
			filters={"disabled": 0},
			fields=["name", "is_default"],
			order_by="is_default desc, name asc",
		)
	]


def settings() -> dict:
	"""What the workspace has decided about printing, as the dialog reads it."""
	found = frappe.get_cached_doc("Print Settings")
	return {
		"page_size": found.pdf_page_size or "A4",
		"page_width": found.pdf_page_width,
		"page_height": found.pdf_page_height,
		"font": found.font or "",
		"font_size": found.font_size or 0,
		"engine": found.pdf_generator or "chrome",
		"with_letterhead": bool(found.with_letterhead),
		"repeat_header_footer": bool(found.repeat_header_footer),
		"drafts": bool(found.allow_print_for_draft),
		"cancelled": bool(found.allow_print_for_cancelled),
		"style": found.print_style or "",
	}


def preview(doctype: str, name: str, format: str = "", letterhead: str = "",
            language: str = "") -> dict:
	"""The rendered format, as HTML and its stylesheet.

	Frappe's own `get_html_and_style`, called rather than copied — it is what
	knows about the beta generator, the classic renderer, the letter head and
	the print style, and it checks the document's own print permission on the
	way through.
	"""
	from frappe.www.printview import get_html_and_style

	with _language(language):
		return get_html_and_style(
			doc=doctype,
			name=name,
			print_format=format or None,
			letterhead=letterhead or None,
			no_letterhead=0 if letterhead else None,
		)


def pdf(doctype: str, name: str, format: str = "", letterhead: str = "",
        language: str = "") -> bytes:
	"""The same thing as a PDF, through whichever engine the site runs.

	`frappe.get_print(as_pdf=True)` rather than `download_pdf`: the latter
	writes into `frappe.local.response` and takes the request over, which is
	the desk's own download flow and not something an API can hand back.
	"""
	from frappe.www.printview import validate_print_permission

	document = frappe.get_doc(doctype, name)
	validate_print_permission(document)

	with _language(language):
		return frappe.get_print(
			doctype, name, format or None, doc=document,
			as_pdf=True,
			letterhead=letterhead or None,
			no_letterhead=0 if letterhead else None,
		)


def _language(language: str):
	"""Frappe's own print-language context, or nothing.

	A format carries a `default_print_language` and a person may ask for
	another; both go through the same context manager the desk uses, so a
	translated format prints the same way here as there.
	"""
	from contextlib import nullcontext

	if not language:
		return nullcontext()

	from frappe.translate import print_language

	return print_language(language)


# --------------------------------------------------------------------------- #
# What a workspace decides once, for everybody
# --------------------------------------------------------------------------- #

# The Print Settings fields a workspace may change, and what each is called
# here. Frappe's own names are on the singles doctype and half of them say
# `pdf_` for things that are about paper rather than about PDFs.
SETTINGS = {
	"page_size": "pdf_page_size",
	"page_width": "pdf_page_width",
	"page_height": "pdf_page_height",
	"font": "font",
	"font_size": "font_size",
	"engine": "pdf_generator",
	"with_letterhead": "with_letterhead",
	"repeat_header_footer": "repeat_header_footer",
	"drafts": "allow_print_for_draft",
	"cancelled": "allow_print_for_cancelled",
	"style": "print_style",
}


def save_settings(values: dict) -> dict:
	"""Change them, through the document so the framework's own cache clears.

	Bounded rather than trusted: `pdf_generator` names a binary to run and
	`pdf_page_size` reaches wkhtmltopdf's command line, so both are checked
	against the list this module offers rather than written through.
	"""
	if not isinstance(values, dict):
		frappe.throw(_("Those settings could not be read."))

	doc = frappe.get_doc("Print Settings")

	if "page_size" in values and values["page_size"] not in PAGE_SIZES:
		frappe.throw(_("{0} is not a page size.").format(values["page_size"]))
	if "engine" in values and values["engine"] not in PDF_ENGINES:
		frappe.throw(_("{0} is not a PDF engine.").format(values["engine"]))
	if "style" in values and values["style"]:
		if not frappe.db.exists("Print Style", values["style"]):
			frappe.throw(_("{0} is not a print style.").format(values["style"]))

	for key, value in values.items():
		field = SETTINGS.get(key)
		if not field:
			continue
		doc.set(field, int(value) if isinstance(value, bool) else value)

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return settings()


def styles() -> list[str]:
	"""The print styles on the site: the typography a format is drawn in."""
	return frappe.get_all(
		"Print Style", filters={"disabled": 0}, pluck="name", order_by="name asc",
	)


# --------------------------------------------------------------------------- #
# The builder
#
# A format built here is a Frappe *beta* print format: `print_format_builder_beta
# = 1` and a `format_data` layout, which `PrintFormatGenerator` renders. That
# choice is the whole point of this section. The alternative — our own layout
# JSON and our own renderer — would print differently from the same format
# opened anywhere else, and "differently" for a printed invoice means a
# customer's letter head in the wrong place.
#
# So the contract below is Frappe's, verbatim:
#
#     {"sections": [{"columns": [{"fields": [...], "width": 1}],
#                    "justify": "space-between", "gap": 20}],
#      "header": {"columns": [...]},
#      "footer": {"columns": [...]}}
#
# and a field is a docfield-shaped dict — `fieldname`, `fieldtype`, `label` —
# with the builder's own extras beside it. Everything written here is checked
# against that shape and against the doctype's own metadata, because
# `format_data` is rendered by a Jinja template on the server: a `fieldname`
# nobody checked is a value nobody meant to print, and an `html` element is a
# template that runs.
# --------------------------------------------------------------------------- #

# The elements a format may hold that are not fields of the document. Frappe's
# own builder offers exactly these, and the generator's template branches on
# each by name — anything else falls through to "render the docfield", which is
# why the set is closed rather than merely documented.
ELEMENTS = ("HTML", "Spacer", "Divider", "Image", "Barcode")

# Where a page number may sit, and Frappe's own words for it.
PAGE_NUMBERS = ("Hide", "Top Left", "Top Center", "Top Right",
                "Bottom Left", "Bottom Center", "Bottom Right")

# How a row of columns distributes what is left over. Named CSS classes in the
# generator's template, so the set is closed there too.
JUSTIFY = ("space-between", "space-evenly", "center", "right-end")

# What a label does. `hide` is the generator's own word for "value only".
LABELS = ("show", "hide")

ALIGN = ("left", "center", "right")

# Bounds. A print format is a page, and a page that needs more than this is a
# report.
SECTIONS = 40
COLUMNS = 6
FIELDS = 60
TABLE_COLUMNS = 12

# Fieldtypes that are layout in the *form* and have nothing to print. The
# generator would render each as an empty labelled div.
NOT_PRINTABLE = frozenset({
	"Section Break", "Column Break", "Tab Break", "Fold", "Button",
	"Heading", "Table MultiSelect",
})

# Child tables, which print as a table of their own columns rather than as a
# value. Frappe's own `table_fields`, named here so the palette and the
# sanitiser agree without importing the model layer twice.
TABLE_TYPES = frozenset({"Table"})


def palette(doctype: str) -> dict:
	"""What the builder may put on the page, for one doctype.

	Three things, because they behave differently once dropped: the document's
	own fields, its child tables with their columns, and the elements that are
	not fields at all.
	"""
	meta = frappe.get_meta(doctype)
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You cannot read {0}.").format(doctype), frappe.PermissionError)

	fields, tables = [], []
	for df in meta.fields:
		if df.fieldtype in NOT_PRINTABLE:
			continue
		if df.fieldtype in TABLE_TYPES:
			tables.append({
				"fieldname": df.fieldname,
				"label": _(df.label or df.fieldname),
				"fieldtype": df.fieldtype,
				"options": df.options,
				"columns": _child_columns(df.options),
			})
			continue
		fields.append({
			"fieldname": df.fieldname,
			"label": _(df.label or df.fieldname),
			"fieldtype": df.fieldtype,
		})

	# The id, which is not a docfield and is on almost every format anybody
	# has ever drawn.
	fields.insert(0, {"fieldname": "name", "label": _("ID"), "fieldtype": "Data"})

	return {
		"fields": fields,
		"tables": tables,
		"elements": [{"fieldtype": one, "label": _(one)} for one in ELEMENTS],
	}


def _child_columns(child_doctype: str | None) -> list[dict]:
	"""The columns a child table offers, in the order the child declares them."""
	if not child_doctype:
		return []
	try:
		meta = frappe.get_meta(child_doctype)
	except frappe.DoesNotExistError:
		return []
	return [
		{"fieldname": df.fieldname, "label": _(df.label or df.fieldname),
		 "fieldtype": df.fieldtype}
		for df in meta.fields
		if df.fieldtype not in NOT_PRINTABLE and df.fieldtype not in TABLE_TYPES
	]


# --------------------------------------------------------------------------- #
# Reading a layout back out of what the browser sent
# --------------------------------------------------------------------------- #

def _one_of(value, allowed, fallback=None):
	value = str(value or "").strip()
	return value if value in allowed else fallback


def _number(value, low, high, fallback):
	try:
		found = float(value)
	except (TypeError, ValueError):
		return fallback
	return min(max(found, low), high)


def _layout(raw, doctype: str) -> dict:
	"""Shape whatever the browser sent into the layout the generator renders.

	Dropping rather than refusing, one element at a time: a format is drawn
	over minutes and a single unknown key should not lose the drawing. What is
	*not* dropped quietly is a fieldname the doctype does not have — that is
	the one mistake whose symptom is a blank space on a printed invoice, so it
	is refused by name.
	"""
	raw = frappe.parse_json(raw) if isinstance(raw, str) else raw
	if not isinstance(raw, dict):
		raw = {}

	known = _known(doctype)
	found = {
		"sections": [
			_section(one, doctype, known)
			for one in (raw.get("sections") or [])[:SECTIONS]
			if isinstance(one, dict)
		],
	}
	for zone in ("header", "footer"):
		found[zone] = _section(raw.get(zone) or {}, doctype, known)
		# The generator reads a zone as `{"columns": [...]}` rather than as a
		# section, so it carries no justify of its own beyond that.
	return found


def _known(doctype: str) -> dict:
	"""Every fieldname this doctype can print, and what type each is."""
	meta = frappe.get_meta(doctype)
	found = {"name": "Data"}
	for df in meta.fields:
		if df.fieldtype in NOT_PRINTABLE:
			continue
		found[df.fieldname] = df.fieldtype
	return found


def _section(raw: dict, doctype: str, known: dict) -> dict:
	columns = [
		_column(one, doctype, known)
		for one in (raw.get("columns") or [])[:COLUMNS]
		if isinstance(one, dict)
	]
	found = {"columns": columns}
	justify = _one_of(raw.get("justify"), JUSTIFY)
	if justify:
		found["justify"] = justify
	if raw.get("gap") is not None:
		found["gap"] = int(_number(raw.get("gap"), 0, 200, 20))
	return found


def _column(raw: dict, doctype: str, known: dict) -> dict:
	found = {
		"fields": [
			shaped
			for one in (raw.get("fields") or [])[:FIELDS]
			if isinstance(one, dict) and (shaped := _element(one, doctype, known))
		],
	}
	if raw.get("width") is not None:
		found["width"] = _number(raw.get("width"), 0.1, 12, 1)
	return found


def _element(raw: dict, doctype: str, known: dict) -> dict | None:
	"""One thing on the page: a field of the document, or an element."""
	fieldtype = str(raw.get("fieldtype") or "").strip()

	if fieldtype in ELEMENTS:
		return _decoration(raw, fieldtype)

	fieldname = str(raw.get("fieldname") or "").strip()
	if not fieldname:
		return None
	if fieldname not in known:
		frappe.throw(_("{0} has no field called {1}.").format(doctype, fieldname))

	found = {
		"fieldname": fieldname,
		"fieldtype": known[fieldname],
		"label": str(raw.get("label") or "")[:140] or fieldname,
	}
	if _one_of(raw.get("show_label"), LABELS) == "hide":
		found["show_label"] = "hide"

	if known[fieldname] in TABLE_TYPES:
		found["table_columns"] = _table_columns(raw, fieldname, doctype)
	return found


def _table_columns(raw: dict, fieldname: str, doctype: str) -> list[dict]:
	"""Which of a child table's columns print, in the order they were dragged."""
	child = frappe.get_meta(doctype).get_field(fieldname)
	offered = {one["fieldname"]: one for one in _child_columns(child and child.options)}
	offered["idx"] = {"fieldname": "idx", "label": _("No."), "fieldtype": "Int"}

	found = []
	for one in (raw.get("table_columns") or [])[:TABLE_COLUMNS]:
		if not isinstance(one, dict):
			continue
		column = offered.get(str(one.get("fieldname") or "").strip())
		if not column:
			continue
		shaped = dict(column)
		if one.get("label"):
			shaped["label"] = str(one["label"])[:140]
		if one.get("width") is not None:
			shaped["width"] = _number(one.get("width"), 1, 100, 10)
		found.append(shaped)
	return found


def _decoration(raw: dict, fieldtype: str) -> dict:
	"""An element that is not a field: a rule, a gap, an image, some HTML.

	`HTML` is the one that carries real weight — the generator renders it as a
	Jinja template with the document in scope, which is what makes a total in
	words or a conditional line possible and is also why it is only reachable
	by somebody who may already change every setting in the workspace.
	"""
	found = {"fieldtype": fieldtype}

	if fieldtype == "HTML":
		found["html"] = str(raw.get("html") or "")[:20000]
	elif fieldtype == "Spacer":
		found["height"] = int(_number(raw.get("height"), 1, 400, 16))
	elif fieldtype in ("Image", "Barcode"):
		align = _one_of(raw.get("align"), ALIGN, "left")
		if align != "left":
			found["align"] = align
		if raw.get("width"):
			found["width"] = str(raw["width"])[:20]
		if fieldtype == "Image":
			if raw.get("image_url"):
				found["image_url"] = str(raw["image_url"])[:500]
			if raw.get("fieldname"):
				found["fieldname"] = str(raw["fieldname"])[:140]
		else:
			found["fieldname"] = str(raw.get("fieldname") or "")[:140]
	return found


# --------------------------------------------------------------------------- #
# The page a format is drawn on
# --------------------------------------------------------------------------- #

# What the builder sets on the Print Format document itself rather than in the
# layout: the paper around the drawing. Each is bounded, because margins reach
# the PDF engine's command line and `page_number` names a CSS class.
SETUP = {
	"margin_top": (0, 100, 15),
	"margin_bottom": (0, 100, 15),
	"margin_left": (0, 100, 15),
	"margin_right": (0, 100, 15),
	"font_size": (6, 40, 14),
}


def _setup(raw) -> dict:
	raw = frappe.parse_json(raw) if isinstance(raw, str) else (raw or {})
	if not isinstance(raw, dict):
		raw = {}

	found = {}
	for key, (low, high, fallback) in SETUP.items():
		if key in raw:
			found[key] = _number(raw[key], low, high, fallback)
	found["font_size"] = int(found.get("font_size", SETUP["font_size"][2]))

	page_number = _one_of(raw.get("page_number"), PAGE_NUMBERS)
	if page_number:
		found["page_number"] = page_number
	if "align_labels_right" in raw:
		found["align_labels_right"] = int(bool(raw["align_labels_right"]))
	if "show_label_colon" in raw:
		found["show_label_colon"] = int(bool(raw["show_label_colon"]))
	if raw.get("font"):
		found["font"] = str(raw["font"])[:140]
	if raw.get("default_print_language"):
		language = str(raw["default_print_language"])[:20]
		if frappe.db.exists("Language", language):
			found["default_print_language"] = language
	return found


def format_of(name: str) -> dict:
	"""One format, as the builder opens it."""
	doc = frappe.get_doc("Print Format", name)
	if not doc.print_format_builder_beta and not doc.format_data:
		frappe.throw(
			_("{0} was written as a template rather than drawn, so it cannot be "
			  "opened here. It still prints.").format(name)
		)

	return {
		"name": doc.name,
		"doctype": doc.doc_type,
		"disabled": bool(doc.disabled),
		"standard": doc.standard == "Yes",
		"layout": frappe.parse_json(doc.format_data) or {"sections": [],
		                                                 "header": {"columns": []},
		                                                 "footer": {"columns": []}},
		"setup": {
			"margin_top": doc.margin_top,
			"margin_bottom": doc.margin_bottom,
			"margin_left": doc.margin_left,
			"margin_right": doc.margin_right,
			"font_size": doc.font_size,
			"font": doc.font or "",
			"page_number": doc.page_number or "Hide",
			"align_labels_right": bool(doc.align_labels_right),
			"show_label_colon": bool(doc.show_label_colon),
			"default_print_language": doc.default_print_language or "",
		},
	}


def save_format(doctype: str, label: str, layout, setup=None, name: str = "") -> dict:
	"""Create or replace a drawn format.

	A standard format — one that ships with an app, in its source tree — is
	never edited here: the next deploy would overwrite it, and the person who
	drew it would never find out why their work went away.
	"""
	from frappe.model.rename_doc import rename_doc

	label = str(label or "").strip()[:140]
	if not label:
		frappe.throw(_("A format needs a name."))

	shaped = _layout(layout, doctype)
	page = _setup(setup)

	if name:
		doc = frappe.get_doc("Print Format", name)
		if doc.doc_type != doctype:
			frappe.throw(_("{0} does not print {1}.").format(name, doctype))
		if doc.standard == "Yes":
			frappe.throw(
				_("{0} ships with the app that defines it, so it is read-only "
				  "here. Duplicate it to make it yours.").format(name)
			)
	else:
		if frappe.db.exists("Print Format", label):
			frappe.throw(_("A format called {0} already exists.").format(label))
		doc = frappe.new_doc("Print Format")
		doc.doc_type = doctype
		doc.standard = "No"
		doc.print_format_type = "Jinja"

	doc.name = doc.name or label
	doc.print_format_builder_beta = 1
	doc.custom_format = 0
	doc.raw_printing = 0
	doc.format_data = frappe.as_json(shaped)
	for key, value in page.items():
		doc.set(key, value)

	# Print Format grants write to System Manager, and every workspace member is
	# a Website User by design. The door is the settings gate in `workspace.py`,
	# which has already been walked through to reach here.
	doc.flags.ignore_permissions = True
	doc.save()

	if label != doc.name:
		# The default is a Property Setter holding the format's *name*, so a
		# rename would quietly leave the doctype pointing at something that is
		# no longer there — and "our invoices stopped using our format" is a
		# thing somebody finds out from a customer.
		was_default = frappe.db.get_value("Property Setter", {
			"doc_type": doctype, "property": "default_print_format",
		}, "value") == doc.name

		# `frappe.rename_doc` is the whitelisted wrapper and takes no
		# `ignore_permissions`; the model's own does, which is what a Website
		# User walking through our gate needs.
		rename_doc("Print Format", doc.name, label, force=True,
		           ignore_permissions=True)
		doc = frappe.get_doc("Print Format", label)
		if was_default:
			set_default(doctype, label)

	frappe.db.commit()
	return format_of(doc.name)


def delete_format(name: str) -> None:
	"""Remove a drawn format, and the default that pointed at it."""
	doc = frappe.get_doc("Print Format", name)
	if doc.standard == "Yes":
		frappe.throw(_("{0} ships with the app that defines it.").format(name))

	default = frappe.db.get_value("Property Setter", {
		"doc_type": doc.doc_type, "property": "default_print_format",
	}, "value")
	if default == name:
		set_default(doc.doc_type, "")

	frappe.delete_doc("Print Format", name, ignore_permissions=True)
	frappe.db.commit()


def set_default(doctype: str, name: str) -> list[dict]:
	"""Which format a document prints with when nobody picks one.

	Frappe stores this as a Property Setter on the doctype rather than on the
	format, which is what makes it survive an app upgrade — and what makes an
	empty value mean "back to Standard" rather than "no format".
	"""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	name = str(name or "").strip()
	if name and name != "Standard":
		if not frappe.db.exists("Print Format", {"name": name, "doc_type": doctype}):
			frappe.throw(_("{0} does not print {1}.").format(name, doctype))
	else:
		name = ""

	make_property_setter(doctype, None, "default_print_format", name, "Data",
	                     for_doctype=True, validate_fields_for_doctype=False)
	frappe.db.commit()
	return formats(doctype)


def draft_preview(doctype: str, layout, setup=None, name: str = "",
                  letterhead: str = "") -> dict:
	"""Render a layout that has not been saved, against a real record.

	The builder's canvas draws boxes; only the generator knows what the type
	renderers, the letter head and the print style do to them. Rendering the
	unsaved format through the same generator the PDF uses is the only way the
	preview cannot drift from the print.
	"""
	from frappe.utils.print_format_generator import PrintFormatGenerator
	from frappe.www.printview import set_link_titles, validate_print

	sample = str(name or "") or _sample(doctype)
	if not sample:
		return {"html": "", "style": "", "empty": True}

	document = frappe.get_doc(doctype, sample)
	document.check_permission("read")
	validate_print(document)
	set_link_titles(document)

	draft = frappe.new_doc("Print Format")
	draft.doc_type = doctype
	draft.name = "Draft"
	draft.standard = "No"
	draft.print_format_builder_beta = 1
	draft.format_data = frappe.as_json(_layout(layout, doctype))
	for key, value in _setup(setup).items():
		draft.set(key, value)

	generator = PrintFormatGenerator(draft, document, letterhead or None)
	return {"html": generator.get_html_preview(), "style": "", "empty": False}


def _sample(doctype: str) -> str:
	"""A record to draw the preview over: the newest this person may read."""
	rows = frappe.get_list(doctype, fields=["name"], order_by="modified desc",
	                       limit_page_length=1, ignore_permissions=False)
	return rows[0]["name"] if rows else ""


# --------------------------------------------------------------------------- #
# Letter heads
#
# The one piece of the print stack that is a document rather than a setting: a
# letter head is HTML, it belongs to the workspace rather than to any format,
# and it is what makes a printed page look like it came from somebody.
# --------------------------------------------------------------------------- #

LETTER_HEADS = 20
LETTER_HEAD_HTML = 20000
ALIGNMENTS = ("Left", "Center", "Right")


def letter_head(name: str) -> dict:
	doc = frappe.get_doc("Letter Head", name)
	return {
		"name": doc.name,
		"default": bool(doc.is_default),
		"disabled": bool(doc.disabled),
		"content": doc.content or "",
		"footer": doc.footer or "",
		"image": doc.image or "",
		"image_height": doc.image_height or 0,
		"image_width": doc.image_width or 0,
		"align": doc.align or "Left",
		"footer_align": getattr(doc, "footer_align", "") or "Left",
	}


def save_letter_head(label: str, values: dict, name: str = "") -> dict:
	"""Create or change one, through the document so its HTML is sanitised.

	`Letter Head` runs its own `validate`, which builds `content` from the
	image where one was uploaded and scrubs the HTML — a good reason not to
	write the table directly.
	"""
	label = str(label or "").strip()[:140]
	if not label:
		frappe.throw(_("A letter head needs a name."))
	if not isinstance(values, dict):
		values = {}

	if name:
		doc = frappe.get_doc("Letter Head", name)
	else:
		if frappe.db.count("Letter Head") >= LETTER_HEADS:
			frappe.throw(_("That is as many letter heads as one workspace can hold."))
		if frappe.db.exists("Letter Head", label):
			frappe.throw(_("A letter head called {0} already exists.").format(label))
		doc = frappe.new_doc("Letter Head")
		doc.letter_head_name = label

	doc.source = "HTML"
	doc.content = str(values.get("content") or "")[:LETTER_HEAD_HTML]
	doc.footer = str(values.get("footer") or "")[:LETTER_HEAD_HTML]
	doc.image = str(values.get("image") or "")[:500]
	doc.image_height = _number(values.get("image_height"), 0, 500, 0)
	doc.image_width = _number(values.get("image_width"), 0, 500, 0)
	doc.align = _one_of(values.get("align"), ALIGNMENTS, "Left")
	if doc.meta.get_field("footer_align"):
		doc.footer_align = _one_of(values.get("footer_align"), ALIGNMENTS, "Left")
	doc.is_default = int(bool(values.get("default")))
	doc.disabled = int(bool(values.get("disabled")))

	doc.flags.ignore_permissions = True
	doc.save()

	if label != doc.name:
		from frappe.model.rename_doc import rename_doc

		rename_doc("Letter Head", doc.name, label, force=True,
		           ignore_permissions=True)
		doc = frappe.get_doc("Letter Head", label)

	frappe.db.commit()
	return letter_head(doc.name)


def delete_letter_head(name: str) -> None:
	frappe.delete_doc("Letter Head", name, ignore_permissions=True)
	frappe.db.commit()
