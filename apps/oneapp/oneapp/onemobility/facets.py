"""How a person narrows a screen, said once for every screen that narrows.

The map and Insights ask the same question — *only this line, only this
vehicle, only the metro* — of different tables, and before this they each
carried their own answer: `live.at` took a `line` string, `insights.rhythm`
took a different `line` string, and nothing took a vehicle at all. Two
implementations of one idea is how a filter comes to mean something slightly
different on two screens of one product, and nobody notices until an operator
compares them.

So there is one vocabulary here, and both endpoints read it.

A facet is one of two things:

* **Direct** — the fact table has the column. `line` and `vehicle` are stored
  on an observation, `stop` on a stop event, so narrowing is a `WHERE`.
* **Through** — the fact table has no such column and never should. A mode is a
  property of a *line*, not of a position, and denormalising "Metro" onto forty
  million rows to save a lookup would be the wrong trade by four orders of
  magnitude. So `mode=Metro` resolves against the reference doctype first and
  arrives as the set of lines it names.

Which is also why this is server-side. The resolution reads doctypes, so it
runs as the person asking and cannot widen what they may see; a browser that
resolved its own facets would be a browser deciding which lines exist.

**A facet a table cannot answer is refused, not ignored.** Asking Insights for
one vehicle's rhythm over a year is a fair question with an unfair answer —
`serviceHour` has no vehicle column, so the honest reply is that this table
cannot say, and `unavailable` carries it to the screen so the control can grey
itself out rather than quietly showing everybody's numbers.
"""

import frappe
from frappe import _

#: How many rows a `through` facet may resolve to before the `IN` list stops
#: being a filter and starts being a table scan with extra steps. A network
#: with more than this many lines in one mode is a network that wants the
#: facet the other way round.
MAX_RESOLVED = 500

#: The whole vocabulary. `column` is the fact column a facet lands on; `through`
#: says it lands there by way of another doctype's field.
#:
#: Labels are callables because `_()` at import time is the language of
#: whoever first loaded the module, which on a shared bench is nobody's.
FACETS = {
	"line": {
		"label": lambda: _("Line"),
		"icon": "lucide-route",
		"column": "line",
		"doctype": "Transit Line",
		"title": "short_name",
		"subtitle": "line_name",
		"order_by": "short_name asc",
	},
	"vehicle": {
		"label": lambda: _("Vehicle"),
		"icon": "lucide-bus",
		"column": "vehicle",
		"doctype": "Transit Vehicle",
		"title": "label",
		"subtitle": "vehicle_key",
		"order_by": "label asc",
	},
	"stop": {
		"label": lambda: _("Stop"),
		"icon": "lucide-map-pin",
		"column": "stop",
		"doctype": "Transit Stop",
		"title": "stop_name",
		"subtitle": "stop_code",
		"order_by": "stop_name asc",
	},
	# Through the *line* and not the vehicle, though both carry a mode. A
	# person choosing "Metro" on a map means the metro network; a fleet whose
	# vehicle records disagree with the lines they run on is a data problem to
	# see rather than a second facet to choose between.
	"mode": {
		"label": lambda: _("Mode"),
		"icon": "lucide-train-front",
		"column": "line",
		"through": ("Transit Line", "mode"),
	},
	"agency": {
		"label": lambda: _("Agency"),
		"icon": "lucide-building-2",
		"column": "line",
		"through": ("Transit Line", "agency"),
		"doctype": "Transit Agency",
		"title": "agency_name",
		"order_by": "agency_name asc",
	},
	"zone": {
		"label": lambda: _("Zone"),
		"icon": "lucide-layers",
		"column": "stop",
		"through": ("Transit Stop", "zone"),
	},
}


def _guard():
	if not frappe.has_permission("Transit Line", "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)


def chosen(raw) -> dict:
	"""What the caller asked for, reduced to facets that exist.

	A key nobody declared is dropped rather than passed on: every value here
	reaches a query, and the whole reason `FACETS` is a closed table is that a
	screen cannot invent a seventh one on the way past.
	"""
	if isinstance(raw, str):
		raw = frappe.parse_json(raw or "{}")
	if not isinstance(raw, dict):
		return {}
	return {
		key: str(value).strip()
		for key, value in raw.items()
		if key in FACETS and str(value or "").strip()
	}


def resolve(fact, raw) -> tuple[dict, list[str]]:
	"""A fact-table `where` and the facets this table could not honour.

	Returns both halves rather than throwing on the second: a screen with a
	vehicle chosen and a line-grained table in front of it should still draw
	the line-grained answer and say plainly that the vehicle is not in it.
	"""
	_guard()
	columns = set(fact.fields)
	where: dict = {}
	# Every facet this table cannot answer, not only the ones somebody has
	# already chosen. Reporting it on use would mean a control that looks
	# available until the moment it silently does nothing, which is the worst
	# of the three possible behaviours.
	unavailable = [key for key, facet in FACETS.items() if facet["column"] not in columns]

	for key, value in chosen(raw).items():
		facet = FACETS[key]
		if facet["column"] not in columns:
			continue

		if "through" not in facet:
			where[facet["column"]] = value
			continue

		doctype, field = facet["through"]
		names = [
			row["name"]
			for row in frappe.get_all(
				doctype, filters={field: value},
				fields=["name"], limit_page_length=MAX_RESOLVED,
			)
		]
		# Two facets landing on one column intersect rather than replace: a
		# mode and an agency chosen together mean the lines that are both, and
		# writing the second over the first would silently widen the answer.
		if facet["column"] in where:
			already = where[facet["column"]]
			listed = already if isinstance(already, list) else [already]
			names = [one for one in names if one in set(listed)]
		where[facet["column"]] = names

	return where, unavailable


@frappe.whitelist(methods=["GET"])
def offered() -> dict:
	"""Every facet and what it can be set to. One call, because the screen
	needs all of them before it can draw the bar at all.

	Values come from the doctypes, as the person asking — so a facet never
	offers a line somebody's User Permissions hide, and the bar is narrower for
	a depot manager than for the operations desk without a line of code about
	depots.
	"""
	_guard()
	out = []
	for key, facet in FACETS.items():
		out.append(
			{
				"key": key,
				"label": facet["label"](),
				"icon": facet["icon"],
				"options": _options(facet),
			}
		)
	return {"facets": out}


def _options(facet) -> list[dict]:
	"""The values one facet offers, as `{value, label, hint}`.

	Three shapes, because a facet's values live in three different places and
	guessing wrong shows an operator a list of the wrong things:

	* a **Select**'s own options — the operator's vocabulary, so a mode nobody
	  runs today is still offered and one somebody typed by accident is not;
	* a **Link**'s target rows, whose `name` is what the filter compares to;
	* a **Data** field's distinct values, which is the only honest answer for
	  something like a fare zone that nothing constrains.

	Every one of them reads as the person asking, so a facet never offers a
	line their User Permissions hide.
	"""
	if "through" in facet:
		doctype, field = facet["through"]
		meta = frappe.get_meta(doctype).get_field(field)
		kind = meta.fieldtype if meta else ""

		if kind == "Select":
			return [
				{"value": one, "label": _(one), "hint": ""}
				for one in (meta.options or "").split("\n")
				if one.strip()
			]
		if kind != "Link":
			seen = frappe.get_all(
				doctype,
				filters={field: ("is", "set")},
				fields=[f"`{field}` as value"],
				group_by=field,
				order_by=f"{field} asc",
				limit_page_length=MAX_RESOLVED,
			)
			return [
				{"value": row["value"], "label": row["value"], "hint": ""}
				for row in seen if row.get("value")
			]

	source = facet.get("doctype") or (facet["through"][0] if "through" in facet else "")
	title = facet.get("title")
	if not title:
		return [
			{"value": row["name"], "label": row["name"], "hint": ""}
			for row in frappe.get_all(source, fields=["name"], limit_page_length=MAX_RESOLVED)
		]

	fields = ["name", title] + ([facet["subtitle"]] if facet.get("subtitle") else [])
	rows = frappe.get_all(
		source,
		fields=fields,
		order_by=facet.get("order_by") or f"{title} asc",
		limit_page_length=MAX_RESOLVED,
	)
	return [
		{
			"value": row["name"],
			"label": row.get(title) or row["name"],
			"hint": row.get(facet.get("subtitle")) or "",
		}
		for row in rows
	]
