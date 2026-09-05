"""Every Frappe fieldtype, and what renders it.

Generated from `scripts/field_types.py`, which is checked against Frappe's own
`data_fieldtypes` — so a fieldtype Frappe adds fails the build here rather than
rendering as a text box that saves a string into a Currency column.
"""

import os
from .spec import BANNER


def fields_js(app: str, spec: dict) -> str:
    """The fieldtype map, as the SPA reads it."""
    import json as _json
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import field_types
    from app_icons import (
        ACTIVITY_ICONS, DEFAULT_ACTIVITY_ICON, DEFAULT_NOTIFICATION_ICON,
        DEFAULT_TAB_ICON, NOTIFICATION_ICONS,
        STATE_ICON_WORDS, STATE_ICONS, TAB_ICON_WORDS, TAB_ICONS,
    )
    from field_types import (
        DATA_OPTIONS, FIELD_TYPES, LAYOUT_TYPES, NUMERIC_CELLS, STATE_COLORS,
        WORD_COLORS,
    )

    table = {
        fieldtype: {
            "control": control,
            "cell": cell,
            "icon": icon,
            "editable": editable,
        }
        for fieldtype, (control, cell, icon, editable) in FIELD_TYPES.items()
    }

    return BANNER + """
/**
 * Every Frappe fieldtype, and what renders it.
 *
 * Generated from scripts/field_types.py, which is checked against Frappe's own
 * `data_fieldtypes` — so a fieldtype Frappe adds fails the build here rather
 * than rendering as a text box that saves a string into a Currency column.
 *
 * `control` is a FormControl type as "FormControl:<type>", or the name of a
 * component in the barrel. `null` means shown but never offered: colour,
 * signature and geolocation have no frappe-ui counterpart, and a control that
 * cannot produce the right shape is worse than none.
 */

export const FIELD_TYPES = %(table)s

/** Layout fields. They carry no value and are skipped rather than rendered. */
export const LAYOUT_TYPES = %(layout)s

/** What `options` on a Data field refines the input to. Frappe's own list. */
export const DATA_OPTIONS = %(data_options)s

/**
 * Cells whose value is a number, and so sits against the right edge.
 *
 * By cell rather than by fieldtype: the cell is what already decides how a
 * value is drawn, so a Currency and an Int are one question here, and a
 * fieldtype added to the map lands in a bucket without a second list to
 * remember.
 */
export const NUMERIC_CELLS = %(numeric_cells)s

export function isNumericCell(cell) {
  return NUMERIC_CELLS.includes(cell)
}

/** DocType State's palette, in Badge themes. */
export const STATE_COLORS = %(state_colors)s

/** Frappe's own word lists, so a status reads the same colour as in the desk. */
const WORD_COLORS = %(word_colors)s

/**
 * The glyphs a status may carry, written as literals so Tailwind emits them.
 *
 * A second closed set beside SPACE_ICONS, closed for the same reason and
 * answering a different question: those say what an app *is*, these say where a
 * record *stands*.
 */
export const STATE_ICONS = %(state_icons)s

/** Which glyph a state's own words earn, in order — first match wins. */
const STATE_ICON_WORDS = %(state_icon_words)s

/**
 * The icon for one value of a status Select.
 *
 * Derived from the words rather than declared, because the alternative is
 * typing an icon name beside all fifty-odd options and the words already say
 * it — `Failed` and `Broken` mean the same thing to a reader and should not
 * need two decisions. A doctype that disagrees declares its own, and that
 * override arrives on the state itself.
 *
 * Never nothing: a Select shown as a badge is a category even where it is not a
 * status, and a row where half the badges carry an icon reads as broken rather
 * than as varied. Those get the neutral tag.
 */
export function valueIcon(value, states = []) {
  if (!value) return ''

  const declared = states.find((s) => s.title === value)
  if (declared?.icon) return declared.icon

  const text = String(value).toLowerCase()
  for (const [icon, words] of STATE_ICON_WORDS) {
    if (words.some((word) => text.includes(word))) return icon
  }
  return 'lucide-tag'
}

/**
 * The glyphs a tab may carry, written as literals so Tailwind emits them.
 *
 * A third closed set, for the same build-time reason as the other two. Frappe
 * has no icon property on a Tab Break — a doctype's tabs are a label and
 * nothing else — so this is how a form laid out by somebody who never heard of
 * OneSpace still gets a strip of tabs that reads as one.
 */
export const TAB_ICONS = %(tab_icons)s

/** Which glyph a tab's own words earn, in order — first match wins. */
const TAB_ICON_WORDS = %(tab_icon_words)s

const DEFAULT_TAB_ICON = '%(default_tab_icon)s'

/**
 * The icon for one tab, by its label.
 *
 * `declared` is a manifest's override, keyed by the tab's label — the escape
 * hatch for a tab whose words say nothing useful. Checked against the closed
 * set rather than trusted: a name outside it emits no CSS and draws a blank,
 * which is worse than the derived glyph it replaced.
 *
 * Never nothing. A strip where three tabs carry an icon and the fourth does
 * not reads as a tab that failed to load.
 */
export function tabIcon(label, declared = null) {
  const override = declared?.[label]
  if (override && TAB_ICONS.includes(override)) return override

  const text = String(label || '').trim().toLowerCase()
  for (const [icon, words] of TAB_ICON_WORDS) {
    if (words.some((word) => text.includes(word))) return icon
  }
  return DEFAULT_TAB_ICON
}

/**
 * The glyphs a timeline entry may carry, written as literals so Tailwind emits
 * them.
 *
 * The fourth closed set. One timeline over a record means a comment and a
 * field change sit in the same column, and a column of identical avatars makes
 * two different events look like one.
 */
export const ACTIVITY_ICONS = %(activity_icons)s

const DEFAULT_ACTIVITY_ICON = '%(default_activity_icon)s'

/** The glyph for one kind of timeline entry. */
export function activityIcon(kind) {
  return ACTIVITY_ICONS[kind] || DEFAULT_ACTIVITY_ICON
}

/**
 * The glyphs a notification may carry.
 *
 * Known rather than closed, unlike the four above: `Notification Type` is a
 * doctype, so a site may add one, and a type nobody has drawn gets the bell.
 */
export const NOTIFICATION_ICONS = %(notification_icons)s

const DEFAULT_NOTIFICATION_ICON = '%(default_notification_icon)s'

/** The glyph for one kind of notification. */
export function notificationIcon(kind) {
  return NOTIFICATION_ICONS[kind] || DEFAULT_NOTIFICATION_ICON
}

// Named rather than counted. Stripping this with a hand-written offset is how
// every FormControl type lost its first letter — "date" became "ate", which is
// not in the union, and FormControl answers an unknown type with a plain text
// box and no warning. So the whole record dialog rendered as text inputs and
// nothing anywhere said so.
const FORM_CONTROL = 'FormControl:'

const FALLBACK = {
  control: FORM_CONTROL + 'text',
  cell: 'text',
  icon: 'lucide-circle-help',
  editable: false,
}

/**
 * How to render one field.
 *
 * An unknown fieldtype falls back to a read-only text cell rather than to an
 * editable one: if we do not know what it is, we do not know how to write it.
 */
export function fieldSpec(field) {
  const base = FIELD_TYPES[field?.fieldtype] || FALLBACK

  // `options` on a Data field says what it really holds — an email, a URL, a
  // phone number — and the browser has better keyboards and validation for
  // each than it does for "text".
  if (field?.fieldtype === 'Data' && DATA_OPTIONS[field.options]) {
    return { ...base, control: FORM_CONTROL + DATA_OPTIONS[field.options] }
  }
  return base
}

// The prose editor, and the format it round-trips. Frappe's Text Editor and
// Markdown Editor are the same component storing different text, so the table
// names both as `Editor:<format>` rather than as two components that do not
// exist.
const EDITOR = 'Editor:'

/** The FormControl `type`, or null when this field needs a named component. */
export function formControlType(field) {
  const { control } = fieldSpec(field)
  return control && control.startsWith(FORM_CONTROL) ? control.slice(FORM_CONTROL.length) : null
}

/** The component name, or null when a FormControl handles it. */
export function controlComponent(field) {
  const { control } = fieldSpec(field)
  if (!control || control.startsWith(FORM_CONTROL)) return null
  return control.startsWith(EDITOR) ? 'Editor' : control
}

/**
 * The Editor's `format`, or null for every field that is not one.
 *
 * Named rather than sliced at the call site for the reason the FORM_CONTROL
 * comment above gives: a hand-written offset is how every control type once
 * lost its first letter, and an Editor handed a format it does not know
 * renders an empty document rather than complaining.
 */
export function editorFormat(field) {
  const { control } = fieldSpec(field)
  return control && control.startsWith(EDITOR) ? control.slice(EDITOR.length) : null
}

/**
 * Filter operators, ported from Frappe's own filter UI.
 *
 * Frappe writes this as a deny list per fieldtype (`invalid_condition_map`);
 * it is inverted into an allow list here and generated into the server module
 * too, so the menu a person sees and the check the server makes are the same
 * table. `tests/test_field_types.py` reads Frappe's `filter.js` back and fails
 * when the two drift.
 */
export const OPERATORS = %(operators)s

/** Frappe relabels the comparisons for a date: "Before" reads better than "<". */
export const OPERATOR_LABELS_BY_TYPE = %(operator_labels)s

const VALID_OPERATORS = %(valid_operators)s

/** Frappe's relative-date vocabulary, in its order. */
export const TIMESPANS = %(timespans)s

const DEFAULT_OPERATORS = %(default_operators)s

const EQUALITY = ['=', '!=']
const IN = ['in', 'not in']

/** Which operators a filter on this field may use. */
export function operatorsFor(field) {
  return VALID_OPERATORS[field?.fieldtype] || ['=', '!=', 'is']
}

/** What an operator is called on this field. */
export function operatorLabel(field, operator) {
  return OPERATOR_LABELS_BY_TYPE[field?.fieldtype]?.[operator] || OPERATORS[operator] || operator
}

/** What a filter opens on: a substring for text, a range for a date. */
export function defaultOperator(field) {
  // Stored as a JSON array, so an exact match can never hit.
  if (['_assign', '_liked_by'].includes(field?.fieldname)) return 'like'
  return DEFAULT_OPERATORS[field?.fieldtype] || '='
}

/**
 * What the value control has to be, once the operator is known.
 *
 * Frappe does this by rewriting the docfield in `set_fieldtype`. Naming the
 * decision instead means the server can check a value without rendering one,
 * which is why this same function exists on both sides.
 */
export function valueShape(field, operator) {
  if (operator === 'is') return 'set'
  if (operator === 'timespan') return 'timespan'
  if (operator === 'between') return 'range'
  if (IN.includes(operator)) return 'multi'
  const fieldtype = field?.fieldtype
  if (fieldtype === 'Check' || fieldtype === 'Select') return 'choice'
  if (['Link', 'Dynamic Link'].includes(fieldtype) && EQUALITY.includes(operator)) return 'link'
  // Everything else is a plain box, a Link under `like` included: matching part
  // of a name is a text question.
  return 'value'
}

/** Set / Not Set, which is what `is` asks. */
export const IS_OPTIONS = [
  { value: 'set', label: 'Set' },
  { value: 'not set', label: 'Not Set' },
]

/** A checkbox is one of two things, and neither of them is a text box. */
export const CHECK_OPTIONS = [
  { value: '1', label: 'Yes' },
  { value: '0', label: 'No' },
]

export function isLayout(fieldtype) {
  return LAYOUT_TYPES.includes(fieldtype)
}

/**
 * The Badge theme for a value.
 *
 * The doctype's own `states` first — Frappe stores a colour per status right on
 * the doctype, so a badge is coloured by what the doctype declares rather than
 * by anything guessed here. Only then the word lists, which are Frappe's, so a
 * status that has no declared colour still reads the same as it does in the
 * desk. Then gray, which is an answer rather than a failure.
 */
export function valueTheme(value, states = []) {
  if (!value) return 'gray'

  const declared = states.find((s) => s.title === value)
  if (declared) return STATE_COLORS[declared.color] || 'gray'

  const text = String(value).toLowerCase()
  for (const [theme, words] of WORD_COLORS) {
    if (words.some((word) => text.includes(word))) return theme
  }
  return 'gray'
}
""" % {
        "table": _json.dumps(table, indent=2, sort_keys=True),
        "layout": _json.dumps(list(LAYOUT_TYPES), indent=2),
        "data_options": _json.dumps(DATA_OPTIONS, indent=2, sort_keys=True),
        "numeric_cells": _json.dumps(list(NUMERIC_CELLS), indent=2),
        "state_colors": _json.dumps(STATE_COLORS, indent=2, sort_keys=True),
        "state_icons": _json.dumps(STATE_ICONS, indent=2),
        "state_icon_words": _json.dumps(
            [[icon, list(words)] for icon, words in STATE_ICON_WORDS], indent=2),
        "tab_icons": _json.dumps(TAB_ICONS, indent=2),
        "activity_icons": _json.dumps(ACTIVITY_ICONS, indent=2, sort_keys=True),
        "default_activity_icon": DEFAULT_ACTIVITY_ICON,
        "notification_icons": _json.dumps(NOTIFICATION_ICONS, indent=2, sort_keys=True),
        "default_notification_icon": DEFAULT_NOTIFICATION_ICON,
        "tab_icon_words": _json.dumps(
            [[icon, list(words)] for icon, words in TAB_ICON_WORDS], indent=2),
        "default_tab_icon": DEFAULT_TAB_ICON,
        "word_colors": _json.dumps([[t, list(w)] for t, w in WORD_COLORS], indent=2),
        "operators": _json.dumps(field_types.OPERATORS, indent=2),
        "operator_labels": _json.dumps(field_types.OPERATOR_LABELS_BY_TYPE, indent=2),
        "valid_operators": _json.dumps(
            {t: list(field_types.operators_for(t)) for t in FIELD_TYPES},
            indent=2, sort_keys=True),
        "timespans": _json.dumps(
            [{"value": v, "label": l} for v, l in field_types.TIMESPANS], indent=2),
        "default_operators": _json.dumps(
            {t: field_types.default_operator(t) for t in FIELD_TYPES},
            indent=2, sort_keys=True),
    }
