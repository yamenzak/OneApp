"""The map's analytical layers: what the network does *somewhere*.

Insights answers "when" — an hour of the day, a day of the week, a line. This
answers "where", and the two are not interchangeable. A line that averages four
minutes late is a fact about a line; that it loses all four of them on one
bridge between two particular stops is a fact about a *place*, and it is the one
an operator can act on. No chart in this product can hold it, because a chart
has no geography.

**Binned, and averaged inside the bin.** MapLibre ships a `heatmap` layer that
takes points and a weight, and it is the wrong tool here and worth saying why:
it renders kernel *density*, so a cell with two hundred readings averaging thirty
seconds late glows brighter than one with ten readings averaging ten minutes.
Weighting by delay does not fix it — density still dominates. What answers
"where is it late" is the mean per place, so the rows are grouped into a grid
and each cell carries its own average. Density becomes the *opacity*, where it
belongs: a cell nobody has driven through often is drawn faintly, because it is
a weaker claim rather than a cooler one.

A cell is a rounded latitude and longitude. `ROUND(lat, 3)` is about a hundred
metres, which is roughly a city block and comfortably smaller than the distance
between two stops — fine enough to separate a junction from the road either side
of it, coarse enough that a month of a real fleet is thousands of cells rather
than millions.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from ..shared import facts
from . import facets as facetlib
from . import model
from .insights import _window

#: What can be drawn as a surface, and how to read the column behind it.
#:
#: `scale` divides the stored value into the unit a person reads — delay is kept
#: in seconds and read in minutes. `floor` drops the rows that would poison a
#: mean: occupancy is -1 where the feed did not count, which is not zero
#: passengers and must never be averaged as though it were.
SURFACES = {
	"delay": {"column": "delay_s", "scale": 60.0, "floor": None,
	          "label": lambda: _("Minutes behind the timetable")},
	"occupancy": {"column": "occupancy", "scale": 1.0, "floor": 0,
	              "label": lambda: _("Percent of capacity")},
}

#: How many readings a cell needs before its average is drawn at all.
#:
#: Not a performance guard — a correctness one. The mean of three readings is a
#: number, and drawn beside the mean of three thousand it looks like the same
#: kind of number. Below this a cell is dropped rather than faded, because the
#: honest thing to say about one bus that once went through is nothing.
MIN_READINGS = 8

#: The most cells one answer carries. A city at a hundred metres is a few
#: thousand; past this the map is drawing more polygons than it has pixels and
#: the answer wanted a coarser grid.
MAX_CELLS = 6000


def _guard():
	if not frappe.has_permission("Transit Line", "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)


def _spread(values: list) -> tuple:
	"""The range to colour across: the 5th and 95th, not the min and the max.

	One cell where a bus sat broken down for an hour is a real reading and a
	terrible top of scale — it flattens every other cell into the first step of
	the ramp. Trimming both ends keeps the colours spent on the range the
	network actually occupies, and the cells outside it clamp to the ends, which
	is what a reader expects of them anyway.
	"""
	if not values:
		return 0.0, 1.0
	ordered = sorted(values)
	low = ordered[int(len(ordered) * 0.05)]
	high = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
	return (low, high) if high > low else (low, low + 1)


@frappe.whitelist(methods=["GET"])
def surface(kind: str = "delay", facets: str = "", days_back: int = 30,
            precision: int = 3) -> dict:
	"""One measure, averaged into a grid of places.

	Read off `observation` rather than any rolled tier, because none of them
	keeps a position: the roll-ups are per line, per vehicle and per stop, and
	a place is none of those. That bounds this to the hot window, which is said
	on the screen rather than hidden.
	"""
	_guard()
	shape = SURFACES.get(str(kind or "").strip().lower())
	if not shape:
		frappe.throw(_("There is no such layer."))

	start, end = _window(days_back)
	where, unavailable = facetlib.resolve(model.OBSERVATION, facets)
	empty = {"kind": kind, "cells": [], "low": 0, "high": 1, "size": 0,
	         "label": shape["label"](), "unavailable": unavailable,
	         "from": str(start), "to": str(end)}
	if not facts.exists(model.OBSERVATION):
		return empty

	# 2 is roughly a kilometre and 4 about ten metres — either side of that is
	# a grid coarser than a district or finer than the GPS behind it.
	places = max(2, min(cint(precision) or 3, 4))
	column = shape["column"]

	clauses = ["`at` >= %s", "`at` < %s", "`lat` IS NOT NULL", "`lon` IS NOT NULL",
	           f"`{column}` IS NOT NULL"]
	values = [start, end]
	if shape["floor"] is not None:
		clauses.append(f"`{column}` >= {int(shape['floor'])}")
	facetlib.narrow(clauses, values, where)

	rows = frappe.db.sql(
		f"""SELECT ROUND(`lat`, {places}) AS `lat`, ROUND(`lon`, {places}) AS `lon`,
		           AVG(`{column}`) AS `mean`, COUNT(*) AS `readings`
		    FROM `{model.OBSERVATION.table}`
		    WHERE {' AND '.join(clauses)}
		    GROUP BY 1, 2
		    HAVING `readings` >= {int(MIN_READINGS)}
		    ORDER BY `readings` DESC
		    LIMIT {int(MAX_CELLS)}""",
		tuple(values),
		as_dict=True,
	)
	if not rows:
		return empty

	cells = [
		{
			"lat": flt(row["lat"]),
			"lon": flt(row["lon"]),
			"value": round(flt(row["mean"]) / shape["scale"], 2),
			"readings": cint(row["readings"]),
		}
		for row in rows
	]
	low, high = _spread([one["value"] for one in cells])
	seen = [one["readings"] for one in cells]

	return {
		"kind": kind,
		"cells": cells,
		"low": round(low, 2),
		"high": round(high, 2),
		# What the browser draws each cell as: one grid step wide, so the
		# squares tile rather than overlapping or leaving gaps.
		"size": round(10 ** -places, 6),
		# The confidence range, so opacity can be scaled against the same
		# trimmed ends the colour is.
		"quiet": min(seen),
		"busy": _spread(seen)[1],
		"label": shape["label"](),
		"unavailable": unavailable,
		"from": str(start),
		"to": str(end),
	}


@frappe.whitelist(methods=["GET"])
def demand(facets: str = "", days_back: int = 30) -> dict:
	"""Every stop with its position and what happens there.

	The same numbers `insights.stops` ranks, carried with coordinates so they
	can be drawn where they happen. A ranking answers "which stops"; a map
	answers "which part of town", and a corridor of bunched stops along one road
	is a thing only the second one shows.
	"""
	_guard()
	start, end = _window(days_back)
	where, unavailable = facetlib.resolve(model.STOP_HOUR, facets)
	empty = {"stops": [], "unavailable": unavailable, "from": str(start), "to": str(end)}
	if not facts.exists(model.STOP_HOUR):
		return empty

	rows = facts.aggregate(
		model.STOP_HOUR,
		start=start, end=end,
		group=["stop"],
		measures={
			"visits": ("sum", "visits"),
			"dwell_avg": ("avg", "dwell_avg"),
			"headway_avg": ("avg", "headway_avg"),
			"headway_late": ("avg", "headway_p85"),
			"occupancy_avg": ("avg", "occupancy_avg"),
		},
		where=where,
		limit=20000,
	)
	if not rows:
		return empty

	placed = {
		one["name"]: one
		for one in frappe.get_all(
			"Transit Stop",
			filters={"latitude": ("is", "set"), "longitude": ("is", "set")},
			fields=["name", "stop_name", "latitude", "longitude"],
			limit_page_length=0,
		)
	}

	stops = []
	for row in rows:
		at = placed.get(row.get("stop"))
		if not at:
			continue
		headway = flt(row.get("headway_avg")) / 60
		late = flt(row.get("headway_late")) / 60
		stops.append({
			"stop": row["stop"],
			"label": at["stop_name"] or row["stop"],
			"lat": flt(at["latitude"]),
			"lon": flt(at["longitude"]),
			"visits": cint(row.get("visits")),
			"dwell": round(flt(row.get("dwell_avg")), 1),
			"headway": round(headway, 1),
			# How much worse the wait usually is than the timetable implies.
			# Nought where a stop has only ever seen one vehicle, which is
			# unserved rather than bunched and must not top the scale.
			"bunching": round(max(0.0, late - headway), 1) if headway > 0 else 0,
			"occupancy": round(flt(row.get("occupancy_avg")), 1),
		})

	return {"stops": stops, "unavailable": unavailable,
	        "from": str(start), "to": str(end)}
