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
# `control` is "FormControl:<type>", "Editor:<format>", or the bare name of a
# component in the barrel. Anything else fails the guard.
FIELD_TYPES = {
    # -- text ---------------------------------------------------------------
    "Data":            ("FormControl:text",      "text",     "lucide-type",          True),
    "Small Text":      ("FormControl:textarea",  "text",     "lucide-align-left",    True),
    "Text":            ("FormControl:textarea",  "text",     "lucide-align-left",    True),
    "Long Text":       ("FormControl:textarea",  "text",     "lucide-align-left",    True),
    # Source, not prose: markup and data a person edits as markup and data. All
    # four go to CodeMirror through frappe-ui's CodeEditor, with the language
    # picked in `FieldControl` — `options` on a Code field is where Frappe puts
    # it. A textarea over JSON is a customer counting braces by eye.
    "Code":            ("CodeEditor",            "code",     "lucide-code",          True),
    "JSON":            ("CodeEditor",            "code",     "lucide-braces",        True),
    # Frappe's *source* editor, and the one most easily mistaken for a rich one:
    # HTML Editor stores markup somebody wrote by hand. Getting this and Text
    # Editor the right way round is the whole point of separating them.
    "HTML Editor":     ("CodeEditor",            "html",     "lucide-code-xml",      True),
    # Prose. frappe-ui's TipTap editor on its own subpath, which round-trips
    # both of Frappe's prose formats — `format` is what differs, not the
    # component. An earlier note here said the editor was too heavy and not
    # SSR-safe to be worth it; there is no SSR in this product, and the weight
    # is one async chunk on a route that has a rich-text field.
    "Markdown Editor": ("Editor:markdown",       "text",     "lucide-file-text",     True),
    "Text Editor":     ("Editor:html",           "html",     "lucide-pilcrow",       True),
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

    # A gallery of the record's own attachments, and the one entry here whose
    # field holds nothing at all.
    #
    # Frappe lists it in `no_value_fields` and in `display_fieldtypes`: the
    # desk control renders the *record's* File rows, optionally narrowed by
    # `link_filters` on the docfield, and an upload attaches to the record.
    # So "several attachments under one field" is already how Frappe models
    # it — the field is a window onto the record's attachments rather than a
    # place a list of them is stored.
    #
    # `editable` is False because there is no value to write. The control
    # still uploads and deletes; it does so through the File endpoints, which
    # is what `_writable` correctly refuses to let a record save do.
    "Attachment Gallery": ("AttachmentGallery",  "hidden",   "lucide-images",        False),
}

# What frappe-ui's Editor will round-trip. It declares three; Frappe stores two
# of them, and `json` is the editor's own document model rather than a
# fieldtype. Named here so `tests/test_field_types.py` can check the table
# against the component instead of against memory.
EDITOR_FORMATS = {"html", "markdown"}

# Frappe's `no_value_fields`, minus Table and Table MultiSelect which carry
# data and are placed above. These are layout: they render nothing on their own
# and are skipped rather than displayed.
LAYOUT_TYPES = (
    "Section Break", "Column Break", "Tab Break", "HTML", "Button",
    "Image", "Fold", "Heading",
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


# --------------------------------------------------------------------------- #
# Filter operators
#
# Ported from Frappe's own filter UI — `frappe/public/js/frappe/ui/filters/
# filter.js`, where `conditions` is the list and `invalid_condition_map` says
# which of them a fieldtype may not use. Frappe writes it as a deny list per
# fieldtype; it is inverted into an allow list here, because a deny list has the
# wrong failure mode on a server: a fieldtype nobody thought about would get
# every operator rather than none.
#
# This is the whole reason the filter surface can be wider than "contains". A
# value that carries its own operator used to be dropped outright, since there
# was no way to tell `["like", "%x%"]` from `["descendants of", …]`. Now the
# operator is a separate, named field and it is checked against this table, so a
# filter can say what Frappe's own filter can say and no more.
# --------------------------------------------------------------------------- #

# operator -> label, in the order Frappe lists them.
# Lower case, because that is what Frappe's query layer knows: its filter UI
# labels these "Between" and "Timespan" and lowercases them on the way in
# (`_operator.lower()`), and a filter is stored here as the query, not as the
# label.
OPERATORS = {
    "=":        "Equals",
    "!=":       "Not Equals",
    "like":     "Like",
    "not like": "Not Like",
    "in":       "In",
    "not in":   "Not In",
    "is":       "Is",
    ">":        "Greater Than",
    "<":        "Less Than",
    ">=":       "Greater Than Or Equal To",
    "<=":       "Less Than Or Equal To",
    "between":  "Between",
    "timespan": "Timespan",
}

# A date reads better with words than with symbols, and Frappe relabels them for
# exactly these two fieldtypes.
OPERATOR_LABELS_BY_TYPE = {
    "Date":     {"<": "Before", ">": "After", "<=": "On or Before", ">=": "On or After"},
    "Datetime": {"<": "Before", ">": "After", "<=": "On or Before", ">=": "On or After"},
}

# Frappe's own groupings, kept by name so the deny lists below read the way its
# do.
_RANGE = ("between", "timespan")
_COMPARISON = (">", "<", ">=", "<=")
_LIKE = ("like", "not like")
_IN = ("in", "not in")
_EQUALITY = ("=", "!=")

_TEXT_FIELDS = (
    "Code", "HTML Editor", "Markdown Editor", "Text Editor", "Small Text",
    "Long Text", "Text", "Password",
)
_NUMERIC_FIELDS = ("Rating", "Int", "Float", "Percent")

_INVALID = {
    "Date":     _LIKE,
    "Time":     _RANGE,
    "Data":     _RANGE,
    "Currency": _RANGE,
    "Link":     _RANGE + _COMPARISON,
    "Color":    _RANGE + _COMPARISON,
    "Datetime": _LIKE + _IN + _EQUALITY,
    "Select":   _LIKE + _RANGE + _COMPARISON,
    # A checkbox is one of two things. Everything but equality is noise.
    "Check":    tuple(op for op in OPERATORS if op != "="),
    **{f: _RANGE + _COMPARISON + _IN for f in _TEXT_FIELDS},
    **{f: _LIKE + _RANGE + _IN for f in _NUMERIC_FIELDS},
}


# Frappe does not look a fieldtype up directly. `set_fieldtype` first rewrites
# the docfield to whatever can actually render a filter value for it — a Phone
# or an Attach or a Barcode all become a Data box — and `hide_invalid_conditions`
# then falls back to the rewritten type's deny list when the original has none of
# its own. Without this step a Phone field would offer Between and Timespan,
# because nothing names Phone.
#
# Frappe's own list, from `set_fieldtype`.
_AS_IF = {
    **{f: "Data" for f in (
        "Text", "Small Text", "Text Editor", "Code", "Attach", "Attach Image",
        "Markdown Editor", "HTML Editor", "Phone", "JSON", "Barcode",
        "Dynamic Link", "Read Only",
    )},
    "Check": "Select",
}

# Where Frappe stops, and we do not. These reach the end of its rewrite with no
# deny list of their own, which in a deny list means every operator — Timespan
# on a Signature, Between on an Icon. Harmless in a desk somebody administers,
# not something to offer a customer, so they are classified here instead.
#
# Deliberately narrower than Frappe. The guard reads Frappe's map back and
# compares the fieldtypes it names; these are the ones it does not.
_OURS = {
    **{f: "Int" for f in ("Long Int", "Duration", "Slider")},
    "Autocomplete": "Data",
    # Rows in a child table rather than a value on the document. Frappe can
    # filter one, but only with a four-part filter naming the child doctype; a
    # three-part filter on the parent names a column that is not there, and the
    # database says so. So: shown, never filtered.
    "Table": None,
    "Table MultiSelect": None,
    # A hex string, a blob of coordinates, an icon name. Equality is the only
    # question worth asking, and `is` is the useful one.
    "Signature": "narrow",
    "Geolocation": "narrow",
    "Icon": "narrow",
}

_NARROW = ("=", "!=", "is")


def operators_for(fieldtype: str) -> tuple:
    """Which operators a filter on this fieldtype may use.

    An allow list rather than Frappe's deny list, and that is the whole point:
    a deny list gives a fieldtype nobody thought about every operator, which is
    the wrong way round for something a browser can send.
    """
    if fieldtype not in FIELD_TYPES:
        return _NARROW

    if fieldtype in _INVALID:
        invalid = set(_INVALID[fieldtype])
    else:
        stand_in = _AS_IF.get(fieldtype) or _OURS.get(fieldtype, "missing")
        if stand_in is None:
            return ()
        if stand_in == "narrow":
            return _NARROW
        if stand_in == "missing":
            return _NARROW
        invalid = set(_INVALID.get(stand_in, ()))

    return tuple(op for op in OPERATORS if op not in invalid)


# The default Frappe reaches for when a filter is first added, from
# `get_default_condition`. A Data field is almost always a substring search, and
# a date is almost always a range.
def default_operator(fieldtype: str, fieldname: str = "") -> str:
    if fieldname in ("_assign", "_liked_by"):
        # Stored as a JSON array, so an exact match can never hit.
        return "like"
    if fieldtype in ("Date", "Datetime"):
        return "between"
    stands_in_for = _AS_IF.get(fieldtype) or _OURS.get(fieldtype)
    text = fieldtype in ("Data",) + _TEXT_FIELDS or stands_in_for == "Data"
    default = "like" if text else "="
    # Never an operator this field's own menu does not contain, or the filter
    # opens on something its dropdown cannot show.
    allowed = operators_for(fieldtype)
    if not allowed:
        # Nothing to filter by. An empty string rather than a plausible-looking
        # operator, so a caller that ignores this gets a filter the server drops
        # rather than one it half-accepts.
        return ""
    return default if default in allowed else allowed[0]


# What the value control has to be, once the operator is known. Frappe does this
# in `set_fieldtype` by rewriting the docfield; the same decision, named.
#
#   choice     a Select of fixed options carried alongside
#   set        Set / Not Set
#   timespan   the relative-date vocabulary below
#   range      two dates
#   multi      a list of values
#   link       a picker against the linked doctype
#   value      whatever the field itself renders
def value_shape(fieldtype: str, operator: str) -> str:
    if operator == "is":
        return "set"
    if operator == "timespan":
        return "timespan"
    if operator == "between":
        return "range"
    if operator in _IN:
        return "multi"
    if fieldtype == "Check":
        return "choice"
    if fieldtype == "Select":
        return "choice"
    if fieldtype in ("Link", "Dynamic Link") and operator in _EQUALITY:
        return "link"
    # Frappe falls back to a plain Data box for everything else, including a
    # Link under `like`: matching part of a name is a text question.
    return "value"


IS_OPTIONS = (("set", "Set"), ("not set", "Not Set"))

CHECK_OPTIONS = (("1", "Yes"), ("0", "No"))

# Frappe's relative-date vocabulary, in its order. The server hands these
# straight to Frappe's own `timespan` operator, so the strings have to be the
# ones it knows.
TIMESPANS = (
    ("last 7 days", "Last 7 Days"),
    ("last 14 days", "Last 14 Days"),
    ("last 30 days", "Last 30 Days"),
    ("last 90 days", "Last 90 Days"),
    ("last week", "Last Week"),
    ("last month", "Last Month"),
    ("last quarter", "Last Quarter"),
    ("last 6 months", "Last 6 Months"),
    ("last year", "Last Year"),
    ("yesterday", "Yesterday"),
    ("today", "Today"),
    ("tomorrow", "Tomorrow"),
    ("this week", "This Week"),
    ("this month", "This Month"),
    ("this quarter", "This Quarter"),
    ("this year", "This Year"),
    ("next 7 days", "Next 7 Days"),
    ("next 14 days", "Next 14 Days"),
    ("next 30 days", "Next 30 Days"),
    ("next week", "Next Week"),
    ("next month", "Next Month"),
    ("next quarter", "Next Quarter"),
    ("next 6 months", "Next 6 Months"),
    ("next year", "Next Year"),
)
