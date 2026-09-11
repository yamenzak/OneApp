"""What a workbook asks a model for, and why the answer is a plan.

Every other surface in this arc takes text back and puts it somewhere. A
spreadsheet cannot, and the reason is the decision the whole module rests on:
**the browser evaluates formulas and the server stores what it computed** —
`docs/SHEETS.md` §1. A server that wrote `=SUM(D2:D20)` into a cell would be
writing a workbook whose `values` slice disagrees with its `sheet` slice, and
every reader downstream (the read-back, a print format, the CSV a share link
serves) takes the value. There is no browser here to recompute it.

So a model does not write cells. It answers with a **plan** — a short list of
operations in a closed vocabulary — the plan is validated here against the
workbook that actually exists, and the grid applies it in the browser, where
the engine recomputes and the ordinary save takes what it produced. Applying
goes through `sheet.setCell` and `formats.applyToRange`, which is what the
toolbar and the formula bar already go through, so one press of Undo takes the
whole plan back and a colleague in the same workbook sees it arrive.

That is the same split as `onespace/ai/actions.py` — a model asks, a person's
press does — arrived at from the other direction: not for safety, but because
the arithmetic has to happen where the engine is.

## The vocabulary, and why it is this small

    tab      a new sheet in the workbook
    set      a rectangle of values or formulas, anchored at one cell
    format   a style over a range
    name     a named range

Four, closed, and each validated before it leaves this module: a tab that does
not exist is refused, a reference that does not parse is refused, a style key
nothing declares is dropped, and a plan bigger than `MAX_CELLS` is refused
whole rather than half-applied. A model that invented a fifth operation has
answered nothing, which is the direction worth failing in.

What is deliberately *not* here is the writing verbs. Improve, proofread and
change the tone are about prose, and a grid has none: the closest useful thing
is "write this formula", which is what `set` is.
"""

import json
import re

import frappe
from frappe import _

from oneapp.onespace.ai import gateway, index, streaming
from oneapp.onespace.ai.features import ai_feature

from . import book, codec, refs

#: Rows of each tab that reach the model. A model does not need the whole
#: workbook to know what its columns are — it needs the headings and enough
#: rows to see the shape.
SAMPLE_ROWS = 12

#: And columns. Past this a sheet is a database export, and what is being
#: asked for is a formula rather than a reading of every field.
SAMPLE_COLS = 16

#: Cells one plan may write. The same ceiling the store has, so a plan that
#: would not fit is refused before it is applied rather than half-way through.
MAX_PLAN_CELLS = 2_000

#: Steps one plan may hold. A plan longer than this is a script, and a script
#: is a thing somebody should be able to read before it runs.
MAX_STEPS = 24

#: What a style may say. Closed, because these are the keys the grid's own
#: format layer understands — anything else is dropped rather than passed
#: through to be ignored somewhere less visible.
STYLE_KEYS = {"bold", "italic", "underline", "align", "valign", "numberFormat",
              "background", "color"}

ALIGNS = {"left", "center", "right"}
VALIGNS = {"top", "middle", "bottom"}

#: The number formats the grid ships. A model asking for one it does not have
#: would produce cells that look untouched.
NUMBER_FORMATS = {"general", "number", "currency", "percent", "date", "time",
                  "text", "accounting", "scientific"}

COLOUR = re.compile(r"^#[0-9A-Fa-f]{6}$")

#: A named range's label. The engine keys them upper-case and a label with a
#: space in it is a label a formula cannot say.
LABEL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")

PLAN_SYSTEM = """You are given a spreadsheet and one instruction, and you \
answer with a short plan of changes to it.

Answer with one JSON object and nothing else:

{"note": "", "steps": []}

`note` is one short line telling the person what the plan does, for them to \
read before they accept it. Every step is one of exactly these four:

{"op": "tab", "name": "Summary"}
{"op": "set", "tab": "Costs", "ref": "E1", "values": [["Total"], ["=C2*D2"]]}
{"op": "format", "tab": "Costs", "ref": "E2:E40", "style": {"numberFormat": "currency"}}
{"op": "name", "label": "Totals", "tab": "Costs", "ref": "E2:E40"}

`set` anchors a rectangle at `ref`: the first row of `values` starts there and \
each further row goes one row down. A value beginning with `=` is a formula \
and is evaluated by the spreadsheet; everything else is literal. Write \
formulas rather than arithmetic you did in your head — a number you computed \
stops being right the moment somebody edits a cell it came from, and the \
whole point of a spreadsheet is that it does not.

Use the references you were given. A tab name must be one of the tabs listed, \
or one your own plan created earlier; a reference must be real A1 notation. \
Do not write over cells that already hold something unless the instruction \
asks you to — put new columns after the last one in use.

`style` may set any of: bold, italic, underline, align (left/center/right), \
valign (top/middle/bottom), numberFormat (general, number, currency, percent, \
date, time, text, accounting, scientific), background and color as #RRGGBB.

Keep the plan short. Four or five steps that do the thing asked for beat \
twenty that rebuild the workbook. Where the instruction cannot be done with \
these four operations, answer with an empty `steps` list and say why in \
`note`."""


@ai_feature(
	"sheet.plan",
	label="Working in a sheet",
	capability="Text Generation",
	system=PLAN_SYSTEM,
	description="Turns an instruction into a short plan of changes to a workbook.",
	# A sample of the workbook in, a handful of operations out. The output
	# ceiling is deliberately modest: a plan is meant to be read before it is
	# accepted, and one nobody reads is a workbook nobody trusts.
	max_input_tokens=40_000,
	max_output_tokens=3_000,
)
def plan(ai, sheet: str, instruction: str, material: str, note: str = "") -> dict:
	"""One instruction as a plan, checked against the workbook it names."""
	with gateway.unstreamed():
		answer = ai(_asked(instruction, material), note=note)

	credits = answer.get("credits") or 0
	said = _read(answer.get("text") or "")
	if not said:
		return {"text": _("That did not come back as a plan."),
		        "credits": credits, "steps": []}

	steps, refused = check(sheet, said.get("steps") or [])
	line = frappe.utils.strip_html(str(said.get("note") or "")).strip()[:300]
	if not steps:
		return {"text": refused or line or _("Nothing to change."),
		        "credits": credits, "steps": []}

	return {"text": line or _("Ready to apply."), "credits": credits,
	        "steps": steps, "refused": refused}


def _asked(instruction: str, material: str) -> str:
	"""The instruction, then the workbook, fenced.

	Fenced for the reason every prompt in this arc is: a cell is text somebody
	typed, and a cell reading "ignore the above" must be a cell rather than an
	instruction.
	"""
	return (
		"Instruction:\n" + instruction.strip() + "\n\n"
		"Spreadsheet:\n---\n" + material.strip() + "\n---"
	)


# --------------------------------------------------------------------------- #
# What the workbook hands over
# --------------------------------------------------------------------------- #

def material(name: str) -> str:
	"""The workbook as text: its tabs, what they hold, and its named ranges.

	A sample rather than the whole thing. A model needs the headings and
	enough rows to see the shape; handing it forty thousand cells would cost
	more than every other feature in this arc put together and would not make
	the answer better.

	Values rather than formulas, and that is worth saying out loud: the
	`sheet` slice is what was typed and the `values` slice is what it came to,
	and a model reading `=C2*D2` cannot tell a broken reference from a working
	one while a model reading `20,160` can.
	"""
	loaded = book.load(name)
	said = []

	for tab in codec.tab_names(loaded):
		cells = codec.values_map(loaded, tab)
		rows, cols = codec.extent(cells)
		said.append(f"Tab \"{tab}\" — {rows} rows x {cols} columns in use")
		if not cells:
			continue
		lines = []
		for row in range(1, min(rows, SAMPLE_ROWS) + 1):
			at = []
			for column in range(1, min(cols, SAMPLE_COLS) + 1):
				value = cells.get(refs.format(row, column))
				at.append("" if value in (None, "") else str(value)[:60])
			lines.append(" | ".join(at).rstrip(" |"))
		said.append("\n".join(lines))
		if rows > SAMPLE_ROWS:
			said.append(f"… and {rows - SAMPLE_ROWS} more rows")

	named = codec.named_ranges(loaded)
	if named:
		said.append("Named ranges: " + ", ".join(
			f"{row.get('name') or key} = {row.get('sheet') or ''}!{row.get('range') or ''}"
			for key, row in named.items()
		))

	return "\n\n".join(said)


def about(name: str) -> str:
	"""One sentence saying what this workbook is, and what it is about.

	Not translated: written at a model, in the language the rest of the prompt
	is in — the same argument `onemail/intelligence.py` makes.
	"""
	title = frappe.db.get_value("File", name, "file_name") or "a workbook"
	from oneapp.shared import binding

	said = f'This is a spreadsheet called "{title}" in a business workspace.'
	rows = [one for one in binding.sources(name) if one.get("reference_name")]
	if rows:
		said += " It is about " + ", ".join(
			f"{one.get('reference_doctype')} {one.get('reference_name')}" for one in rows
		) + "."
	return said


# --------------------------------------------------------------------------- #
# Checking a plan against the workbook it names
# --------------------------------------------------------------------------- #

def check(name: str, steps) -> tuple[list[dict], str]:
	"""The steps that are real, and one line about the ones that were not.

	Checked here rather than in the browser, and against the workbook rather
	than against the shape of the JSON: a tab that does not exist, a reference
	that does not parse and a rectangle bigger than the store allows are three
	ways a plan looks fine and destroys a sheet.

	Partial rather than all-or-nothing, with one exception: a plan too big for
	the store is refused whole, because half a plan applied is a workbook
	nobody asked for.
	"""
	if not isinstance(steps, list):
		return [], _("That did not come back as a plan.")

	known = set(codec.tab_names(book.load(name)))
	found, dropped, cells = [], 0, 0

	for raw in steps[:MAX_STEPS]:
		if not isinstance(raw, dict):
			dropped += 1
			continue
		try:
			step = _step(raw, known)
		except (ValueError, refs.BadRef):
			dropped += 1
			continue
		if step["op"] == "tab":
			known.add(step["name"])
		cells += step.get("cells", 0)
		found.append({k: v for k, v in step.items() if k != "cells"})

	if cells > MAX_PLAN_CELLS:
		return [], _("That plan would write more cells than one sheet holds.")

	if dropped:
		return found, _("{0} of the steps named something that is not in this "
		                "sheet and were left out.").format(dropped)
	return found, ""


def _step(raw: dict, known: set) -> dict:
	"""One step, normalised — or `ValueError`, which drops it."""
	op = str(raw.get("op") or "").strip().lower()

	if op == "tab":
		name = str(raw.get("name") or "").strip()[:64]
		if not name or name in known:
			raise ValueError("no tab name")
		return {"op": "tab", "name": name}

	if op == "name":
		label = str(raw.get("label") or "").strip()
		if not LABEL.match(label):
			raise ValueError("bad label")
		tab = _tab(raw, known)
		top, left, bottom, right = refs.parse_range(str(raw.get("ref") or ""))
		return {"op": "name", "label": label, "tab": tab,
		        "ref": refs.format_range(top, left, bottom, right)}

	if op == "format":
		tab = _tab(raw, known)
		top, left, bottom, right = refs.parse_range(str(raw.get("ref") or ""))
		style = _style(raw.get("style"))
		if not style:
			raise ValueError("nothing to apply")
		return {"op": "format", "tab": tab,
		        "ref": refs.format_range(top, left, bottom, right),
		        "style": style,
		        "cells": (bottom - top + 1) * (right - left + 1)}

	if op == "set":
		tab = _tab(raw, known)
		row, column = refs.parse(str(raw.get("ref") or ""))
		values = raw.get("values")
		if not isinstance(values, list) or not values:
			raise ValueError("nothing to write")
		grid, wide = [], 0
		for line in values:
			line = line if isinstance(line, list) else [line]
			grid.append(["" if one is None else str(one)[:2_000] for one in line])
			wide = max(wide, len(line))
		if row + len(grid) - 1 > refs.MAX_ROW or column + wide - 1 > refs.MAX_COLUMN:
			raise ValueError("off the grid")
		return {"op": "set", "tab": tab, "ref": refs.format(row, column),
		        "values": grid, "cells": len(grid) * max(wide, 1)}

	raise ValueError("no such operation")


def _tab(raw: dict, known: set) -> str:
	"""The tab a step names, which has to be one this workbook has.

	Empty means the first, which is what a one-tab workbook always is and what
	a model that did not bother to say meant.
	"""
	tab = str(raw.get("tab") or "").strip()
	if not tab:
		return next(iter(sorted(known)), "") if known else ""
	if tab not in known:
		raise ValueError("no such tab")
	return tab


def _style(given) -> dict:
	"""A style, with everything nothing declares dropped.

	Dropped rather than refused: a model that added `fontFamily` to an
	otherwise good format step has made one mistake about one key, and
	refusing the step would lose the currency format somebody asked for.
	"""
	if not isinstance(given, dict):
		return {}
	style = {}
	for key, value in given.items():
		if key not in STYLE_KEYS:
			continue
		if key in ("bold", "italic", "underline"):
			style[key] = bool(value)
		elif key == "align" and str(value).lower() in ALIGNS:
			style[key] = str(value).lower()
		elif key == "valign" and str(value).lower() in VALIGNS:
			style[key] = str(value).lower()
		elif key == "numberFormat" and str(value).lower() in NUMBER_FORMATS:
			style[key] = str(value).lower()
		elif key in ("background", "color") and COLOUR.match(str(value)):
			style[key] = str(value)
	return style


def _read(text: str) -> dict:
	"""The answer, out of whatever the model actually wrote.

	Parsed tolerantly for the reason `onemail/filing.py` gives: the gateway
	has no structured-output support yet, so a fenced block and a preamble
	both mean what they say.
	"""
	match = re.search(r"\{.*\}", text or "", re.S)
	if not match:
		return {}
	try:
		found = json.loads(match.group(0))
	except ValueError:
		return {}
	return found if isinstance(found, dict) else {}


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def ask(sheet: str, instruction: str) -> dict:
	"""Turn an instruction into a plan for this workbook. Starts a run.

	The workbook is read here, through `book`'s own gate, so a sheet this
	person may not write is refused in the request rather than in a worker
	where nobody can see it.
	"""
	book.may_write(sheet)
	if not (instruction or "").strip():
		frappe.throw(_("Say what to do."))

	return streaming.begin(
		plan,
		label=_("Working it out"),
		sheet=sheet,
		instruction=instruction.strip(),
		material=material(sheet),
		note=about(sheet),
	)


@frappe.whitelist(methods=["GET"])
def suggest_sources(sheet: str) -> list[dict]:
	"""Records this workbook might want to read, nearest first.

	The same retrieval the document gets — `onedoc/intelligence.py` says why
	there is no model in it — over the sheet's own text rather than its prose.
	"""
	book.may_write(sheet)

	said = (material(sheet) or "").strip() or \
		(frappe.db.get_value("File", sheet, "file_name") or "")
	if not said:
		return []

	from oneapp.onespace import spaceview
	from oneapp.shared import binding

	already = {
		(one.get("reference_doctype"), one.get("reference_name"))
		for one in binding.sources(sheet)
	}

	try:
		near = index.nearest(said[:index.MAX_TEXT], limit=18)
	except Exception:
		frappe.log_error(title="Workbook source retrieval failed",
		                 message=frappe.get_traceback())
		return []

	routes = spaceview.routes({one["doctype"] for one in near})
	found = []
	for one in near:
		if (one["doctype"], one["name"]) in already:
			continue
		if one["doctype"] not in routes:
			continue
		if not frappe.has_permission(one["doctype"], "read", doc=one["name"]):
			continue
		found.append({**one, **routes[one["doctype"]]})
		if len(found) >= 6:
			break
	return found
