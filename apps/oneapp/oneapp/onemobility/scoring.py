"""Writing down what was claimed, and checking it.

README §7a asks for this in one sentence — *every prediction is written down
with what it predicted and when, and a job scores it against what happened* —
and the sentence is doing more work than it looks like. Without it there is no
answer to "is it any good", nothing to tell a customer, and no way to notice the
day it stopped working because a line was rerouted. A forecast nobody scores is
a decoration.

**The whole design turns on when the row is written.** The tempting version is a
nightly job that recomputes yesterday's forecast and compares it against
yesterday: no new table, no bookkeeping. It is also worthless, because the
history it would forecast from now contains the day being judged. That model is
being asked whether it agrees with itself and it always does. So a prediction is
written *before* the answer exists, and the table it goes in is append-then-fill:
claimed one night, settled another.

Two passes, in that order, nightly:

    claim     tomorrow's forecast, per line and hour, recorded as it stands now
    settle    yesterday's claims, against what the roll-up now says happened

`claim` runs whether or not anybody is looking, and that is deliberate. Writing
predictions only when a screen asks for one would mean a workspace nobody opened
has no record, a busy one has thousands of duplicates, and the score depends on
who visited — which is a metric about traffic wearing a metric about accuracy.

What is scored is **the band, not the number**. `inside` — did what happened land
between the median and the 95th percentile — is the headline, and the absolute
error is the supporting detail. That ordering is the point: a forecast that is
confidently wrong and one that is uncertain and right have similar errors and
are not the same product, and only the first destroys trust.
"""

from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from . import facets as facetlib
from . import forecast
from . import model
from . import network as networklib
from ..shared import facts

#: How far ahead a nightly claim is made. One day, and it is the honest choice
#: rather than the easy one: `forecast` will answer a fortnight out, and a claim
#: made a fortnight out is the one worth scoring — but recording fourteen claims
#: a night for every line and hour is fourteen times the rows to say something
#: the one-day claim already says. One night ahead, plus the horizon claim below
#: on the day of the week it is cheap to make.
AHEAD_DAYS = 1

#: A long claim, once a week, on the same weekday each time. This is what
#: answers "and how good is it a fortnight out", which is a different question
#: from the nightly one and is the question a customer actually asks before
#: planning against it.
LONG_AHEAD_DAYS = 14
LONG_ON_WEEKDAY = 6

#: What a claim has to rest on before it is worth recording. A `learning`
#: reading scored against reality is a measurement of how little data there was,
#: which is true and is not what this table is for.
ENOUGH = forecast.ENOUGH


def _guard():
	if not frappe.has_permission("Transit Line", "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)


def claim(for_day: date | None = None, made_on: date | None = None) -> int:
	"""Record what the forecast says about a day, as it stands today.

	One row per line per hour, and only where there is enough history to be
	making a claim at all. Idempotent per day: claiming twice deletes and
	rewrites, so a job that ran late and a job that ran twice both leave one set.
	"""
	if not facts.exists(model.SERVICE_HOUR):
		return 0

	today = made_on or getdate()
	day = for_day or (today + timedelta(days=AHEAD_DAYS))
	start, end = forecast._history()

	rows = facts.aggregate(
		model.SERVICE_HOUR,
		start=start, end=end,
		group=["line", "hour"],
		measures={
			"readings": ("sum", "readings"),
			"delay_p50": ("avg", "delay_p50"),
			"delay_p85": ("avg", "delay_p85"),
			"delay_p95": ("avg", "delay_p95"),
		},
		where={"dow": day.weekday()},
	)

	made = datetime.now()
	claims = []
	for row in rows:
		reading = forecast._reading([row], "delay")
		if reading["basis"] < ENOUGH or reading["p50"] is None:
			continue
		claims.append({
			"about": datetime.combine(day, datetime.min.time())
			+ timedelta(hours=cint(row["hour"])),
			"made_at": made,
			"kind": "delay",
			"line": row["line"],
			"stop": "",
			"hour": cint(row["hour"]),
			"dow": day.weekday(),
			"p50": reading["p50"],
			"p85": reading["p85"],
			"p95": reading["p95"],
			"basis": reading["basis"],
			"actual": None,
			"error_s": None,
			"inside": None,
			"scored_at": None,
		})

	facts.ensure(model.PREDICTION, through=day + timedelta(days=1))
	_forget(day)
	return facts.write(model.PREDICTION, claims) if claims else 0


def _forget(day: date):
	"""Drop a day's claims, so claiming again replaces rather than doubles."""
	start = datetime.combine(day, datetime.min.time())
	frappe.db.sql(
		f"DELETE FROM `{model.PREDICTION.table}` "
		f"WHERE `about` >= %s AND `about` < %s",
		(start, start + timedelta(days=1)),
	)


def settle(day: date | None = None) -> int:
	"""Fill in what actually happened, for a day that now has.

	One `UPDATE … JOIN` rather than a row at a time: the two tables are keyed
	the same way — line, hour, day — and the join is the comparison. Doing it in
	Python would be a thousand round trips a night for arithmetic MariaDB does
	in one statement.

	Only rows not already settled are touched, so a job that runs twice does not
	rewrite yesterday's answer with today's roll-up of the same day.
	"""
	if not (facts.exists(model.PREDICTION) and facts.exists(model.SERVICE_HOUR)):
		return 0

	on = day or (getdate() - timedelta(days=1))
	start = datetime.combine(on, datetime.min.time())
	end = start + timedelta(days=1)

	frappe.db.sql(
		f"""
		UPDATE `{model.PREDICTION.table}` AS p
		JOIN `{model.SERVICE_HOUR.table}` AS s
		  ON s.`line` = p.`line` AND s.`hour` = p.`hour`
		 AND s.`at` >= %(start)s AND s.`at` < %(end)s
		SET p.`actual` = s.`delay_avg`,
		    p.`error_s` = s.`delay_avg` - p.`p50`,
		    -- The band, and it is deliberately one-sided. Being *less* late
		    -- than the median was is not a miss: nobody complains that a bus
		    -- arrived inside the range and early in it. The claim being scored
		    -- is "it will not be worse than this".
		    p.`inside` = CASE WHEN s.`delay_avg` <= p.`p95` THEN 1 ELSE 0 END,
		    p.`scored_at` = %(now)s
		WHERE p.`about` >= %(start)s AND p.`about` < %(end)s
		  AND p.`scored_at` IS NULL
		""",
		{"start": start, "end": end, "now": datetime.now()},
	)
	return cint(frappe.db.sql(
		f"SELECT COUNT(*) FROM `{model.PREDICTION.table}` "
		f"WHERE `about` >= %s AND `about` < %s AND `scored_at` IS NOT NULL",
		(start, end),
	)[0][0])


def nightly():
	"""Both passes, in the order they depend on.

	Settle first: it reads the roll-up for yesterday, which `facts.sweep` wrote
	minutes ago and which claiming would otherwise fold into the history it
	forecasts from. Then claim tomorrow, off a history that now includes
	yesterday — which is the freshest honest basis there is.

	Registered after `facts.sweep` in `hooks.py` for the same reason
	`arrivals.build` is registered before it: the order is the whole of it.
	"""
	if not facts.exists(model.SERVICE_HOUR):
		return
	settled = settle()
	claimed = claim()
	today = getdate()
	if today.weekday() == LONG_ON_WEEKDAY:
		claimed += claim(for_day=today + timedelta(days=LONG_AHEAD_DAYS))
	return {"settled": settled, "claimed": claimed}


@frappe.whitelist(methods=["GET"])
def accuracy(facets: str = "", days_back: int = 90) -> dict:
	"""How good this has actually been, off the record rather than off a claim.

	`inside` first, because it is the number that decides whether somebody can
	plan against this: the share of hours where what happened landed inside the
	range that was offered. The typical error is beside it and is the supporting
	detail, not the headline.

	`by_day` is what makes it worth keeping rather than a single figure: the day
	a line is rerouted, this falls, and a number with no history behind it cannot
	show that.
	"""
	_guard()
	end = getdate() + timedelta(days=1)
	start = end - timedelta(days=max(7, min(cint(days_back) or 90, 400)))
	where, unavailable = facetlib.resolve(model.PREDICTION, facets)

	empty = {
		"scored": 0,
		"inside_pct": None,
		"typical_error_s": None,
		"by_day": [],
		"worst": [],
		"from": str(start),
		"to": str(end),
		"unavailable": unavailable,
	}
	if not facts.exists(model.PREDICTION):
		return empty

	rows = facts.rows_between(
		model.PREDICTION,
		datetime.combine(start, datetime.min.time()),
		datetime.combine(end, datetime.min.time()),
		where=where,
	)
	scored = [one for one in rows if one.get("scored_at") and one.get("inside") is not None]
	if not scored:
		return empty

	by_day: dict[str, list] = {}
	for one in scored:
		by_day.setdefault(str(getdate(one["about"])), []).append(one)

	errors = sorted(abs(flt(one["error_s"])) for one in scored)
	middle = errors[len(errors) // 2]

	named = networklib.line_names()
	by_line: dict[str, list] = {}
	for one in scored:
		by_line.setdefault(one["line"], []).append(one)

	worst = [
		{
			"label": named.get(line, line),
			"value": round(100 * sum(cint(x["inside"]) for x in group) / len(group), 1),
			"scored": len(group),
		}
		for line, group in by_line.items()
	]
	worst.sort(key=lambda one: one["value"])

	return {
		**empty,
		"scored": len(scored),
		"inside_pct": round(100 * sum(cint(one["inside"]) for one in scored) / len(scored), 1),
		"typical_error_s": round(middle),
		"by_day": [
			{
				"label": on,
				"value": round(100 * sum(cint(x["inside"]) for x in group) / len(group), 1),
			}
			for on, group in sorted(by_day.items())
		],
		"worst": worst[:10],
	}
