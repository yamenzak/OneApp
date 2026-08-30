"""Every Frappe fieldtype, and what renders it.

Canonical here. Emitted into both SPAs as `src/lib/fields.js` and into the
tenant app as `oneapp_core/fieldtypes.py`, so the browser and the server never
disagree about whether something is editable.

The list is Frappe's own — `frappe/model/__init__.py`, `data_fieldtypes` plus
`no_value_fields`. `tests/test_field_types.py` reads that file and fails when
Frappe adds one we have not placed, because the failure mode of a missing entry
is a field that silently renders as plain text and saves a string into a
Currency column.

Three columns matter:

  `control`  what a form renders. A FormControl `type` where one fits — those
             are checked against frappe-ui's own union, which is why 'number'
             appears rather than 'int' — or a named component for the rest.
  `cell`     how a list cell reads it, which is not the same question: a Check
             is a Switch in a form and a tick in a list.
  `editable` whether we offer to write it at all. False is a real answer:
             Geolocation has no frappe-ui counterpart, and a control that
             cannot produce the right shape is worse than none.
"""

# fieldtype -> (control, cell, icon, editable)
#
# `control` is either "FormControl:<type>" or the bare name of a component in
# the barrel. Anything else fails the guard.
FIELD_TYPES = {
    # -- text ---------------------------------------------------------------
    "Data":            ("FormControl:text",      "text",     "lucide-type",          True),
    "Small Text":      ("FormControl:textarea",  "text",     "lucide-align-left",    True),
    "Text":            ("FormControl:textarea",  "text",     "lucide-align-left",    True),
    "Long Text":       ("FormControl:textarea",  "text",     "lucide-align-left",    True),
    "Code":            ("FormControl:textarea",  "code",     "lucide-code",          True),
    "JSON":            ("FormControl:textarea",  "code",     "lucide-braces",        True),
    "Markdown Editor": ("FormControl:textarea",  "text",     "lucide-file-text",     True),
    "HTML Editor":     ("FormControl:textarea",  "html",     "lucide-code-xml",      True),
    # frappe-ui ships a TipTap Editor on its own subpath. It is heavy and not
    # SSR-safe, so a record dialog gets a textarea and the rich editor is a
    # deliberate choice an app makes with a custom component.
    "Text Editor":     ("FormControl:textarea",  "html",     "lucide-pilcrow",       True),
    "Password":        ("Password",              "hidden",   "lucide-key-round",     True),
    "Phone":           ("FormControl:tel",       "text",     "lucide-phone",         True),
    "Read Only":       ("FormControl:text",      "text",     "lucide-lock",          False),

    # -- numbers ------------------------------------------------------------
    "Int":             ("FormControl:number",    "number",   "lucide-hash",          True),
    "Long Int":        ("FormControl:number",    "number",   "lucide-hash",          True),
    "Float":           ("FormControl:number",    "number",   "lucide-hash",          True),
    "Currency":        ("FormControl:number",    "currency", "lucide-wallet",        True),
    "Percent":         ("FormControl:number",    "percent",  "lucide-percent",       True),
    "Rating":          ("Rating",                "rating",   "lucide-star",          True),
    "Duration":        ("Duration",              "duration", "lucide-timer",         True),
    "Slider":          ("Slider",                "number",   "lucide-sliders",       True),

    # -- booleans -----------------------------------------------------------
    "Check":           ("Switch",                "check",    "lucide-toggle-left",   True),

    # -- choices ------------------------------------------------------------
    "Select":          ("FormControl:select",    "badge",    "lucide-list",          True),
    "Autocomplete":    ("FormControl:combobox",  "text",     "lucide-text-cursor-input", True),
    "Link":            ("Combobox",              "link",     "lucide-link",          True),
    "Dynamic Link":    ("Combobox",              "link",     "lucide-link-2",        True),
    "Table MultiSelect": ("MultiSelect",         "tags",     "lucide-tags",          True),

    # -- time ---------------------------------------------------------------
    "Date":            ("FormControl:date",      "date",     "lucide-calendar",      True),
    "Datetime":        ("FormControl:datetime",  "datetime", "lucide-calendar-clock", True),
    "Time":            ("FormControl:time",      "time",     "lucide-clock",         True),

    # -- files --------------------------------------------------------------
    "Attach":          ("FileUploader",          "attachment", "lucide-paperclip",   True),
    "Attach Image":    ("FileUploader",          "image",    "lucide-image",         True),

    # -- no frappe-ui counterpart -------------------------------------------
    #
    # Shown, never offered. A colour picker, a signature pad and a map are all
    # real components frappe-ui does not have, and a text box that writes a hex
    # string into a Signature field is worse than a read-only value.
    "Color":           (None,                    "color",    "lucide-palette",       False),
    "Signature":       (None,                    "text",     "lucide-signature",     False),
    "Geolocation":     (None,                    "text",     "lucide-map-pin",       False),
    "Barcode":         (None,                    "text",     "lucide-scan-barcode",  False),
    "Icon":            (None,                    "icon",     "lucide-shapes",        False),

    # -- structural ---------------------------------------------------------
    # A child table is a list inside a record. Neither a form control nor a
    # cell; an app that needs one uses a custom component.
    "Table":           (None,                    "hidden",   "lucide-table",         False),
}

# Frappe's `no_value_fields`, minus Table and Table MultiSelect which carry
# data and are placed above. These are layout: they render nothing on their own
# and are skipped rather than displayed.
LAYOUT_TYPES = (
    "Section Break", "Column Break", "Tab Break", "HTML", "Button",
    "Image", "Fold", "Heading", "Attachment Gallery",
)

# `options` on a Data field refines what the browser should offer. Frappe's own
# `data_field_options`.
DATA_OPTIONS = {
    "Email": "email",
    "Phone": "tel",
    "URL": "url",
    "Name": "text",
    "Barcode": "text",
    "IBAN": "text",
}

# The FormControl `type` union, from frappe-ui's own FormControlProps. Anything
# emitted as "FormControl:x" has to be in here or it silently falls through to
# a TextInput — which is how a date field becomes a text box nobody notices.
FORM_CONTROL_TYPES = {
    "date", "datetime-local", "email", "file", "month", "number", "password",
    "search", "tel", "text", "time", "url", "week", "range",
    "textarea", "select", "checkbox", "combobox", "multiselect",
    "daterange", "datetime",
}

# DocType State's colour vocabulary, mapped onto frappe-ui Badge themes. Frappe
# stores these on the doctype itself, so a status badge is coloured by what the
# doctype declares rather than by anything we invent.
STATE_COLORS = {
    "Blue": "blue", "Cyan": "teal", "Gray": "gray", "Green": "green",
    "Light Blue": "blue", "Orange": "orange", "Pink": "pink",
    "Purple": "violet", "Red": "red", "Yellow": "amber",
}

# When a doctype declares no states, Frappe guesses from the word. Same lists
# as `frappe.utils.guess_style`, so a status reads the same colour here as it
# does in the desk.
WORD_COLORS = (
    ("amber", ("pending", "review", "medium", "not approved", "draft", "queued")),
    ("red", ("open", "urgent", "high", "failed", "rejected", "error",
             "cancelled", "overdue", "expired")),
    ("green", ("closed", "finished", "converted", "completed", "complete",
               "confirmed", "approved", "yes", "active", "available", "paid",
               "success")),
    ("blue", ("submitted", "in progress", "working", "scheduled")),
)
