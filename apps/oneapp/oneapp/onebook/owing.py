"""What is owed, and how late.

`docs/ONEBOOK.md` §4. The Invoices screen carries an `outstanding_amount`
column and totals it, which answers *how much* — and a receivables clerk's
actual question is *how long*. An invoice for two thousand that went out last
week and one for two thousand that went out in March are the same number and
completely different problems, and the first is the only one of the two that
any list in this space could tell you about.

An ageing is the report every business with customers opens on a Monday, and
ERPNext ships it twice — `accounts_receivable` and `accounts_payable`, which
are the same report against the other side of the ledger.

## Their report, called rather than copied

The same argument as §1 and §3, and here the thing not to own twice is the
bucketing. What looks like "subtract two dates" carries a set of decisions:
whether a document ages from its due date or its posting date, what happens to
a credit note against an invoice from a different month, how a payment part-way
through is apportioned across the buckets, and which ledger a partly-settled
advance belongs in. All of that is `ReceivablePayableReport`, it runs off the
Payment Ledger rather than off the invoices, and a second version of it is a
second answer to "are we owed this".

**The roll-up by party is ours**, and that is a smaller claim than it sounds.
ERPNext also ships `accounts_receivable_summary`, which is the same report
grouped — so calling it would be a second query over the same ledger to get
sums we already hold. What this module adds up is a column of numbers their
report has already decided; adding them per party is arithmetic, not an
opinion, and the detail rows stay in the payload beside the totals so the two
can be checked against each other on screen.

## One shape for both sides

Measured rather than assumed: the two reports return the same row —
`party`, `voucher_type`, `voucher_no`, `due_date`, `outstanding`, `age` and six
`range0..range5` buckets — differing only in the columns neither screen draws
(a territory on one, a bill number on the other). So one payload serves both
and `Owing.vue` draws either.

## What it refuses

The invoice doctype for that side, at read: receivables are a User grant in
OneBook and payables are the bookkeeper's, which is the same line the two
screens are already on either side of. Asked here as well as at the rail,
because a rail is a suggestion and the URL is a door.
"""

import frappe
from frappe import _

from .statements import _company

#: The two sides, and the report behind each.
#:
#: Named rather than discovered, the same as `statements.REPORTS` and for the
#: same reason: a whitelisted endpoint that ran any report by name would run
#: everything else ERPNext ships against a filter dictionary a caller composed.
SIDES = {
	"receivable": {
		"module": "erpnext.accounts.report.accounts_receivable"
		          ".accounts_receivable",
		"label": "Owed to us",
		# What the screen is *about*, which is also the grant checked on the
		# way in — and the reason these are two screens rather than one with a
		# switch: in OneBook a receivable is everybody's and a payable is the
		# bookkeeper's.
		"doctype": "Sales Invoice",
		"party": "Customer",
	},
	"payable": {
		"module": "erpnext.accounts.report.accounts_payable.accounts_payable",
		"label": "Owed by us",
		"doctype": "Purchase Invoice",
		"party": "Supplier",
	},
}

#: Where the buckets break, in days.
#:
#: Thirty, sixty, ninety, a hundred and twenty — which is not a choice so much
#: as the convention every ledger in the world is read in, and ERPNext's own
#: default. Held here rather than offered as four number boxes: a workspace
#: that reports on 45/90 is a workspace with a reason, and the day one asks,
#: this is one line and a setting rather than a rewrite.
BREAKS = (30, 60, 90, 120)

#: The bucket columns their report emits, in order. `range0` is the one people
#: forget: it is everything *not yet due*, which on a healthy ledger is most of
#: the money and is the difference between "we are owed 400k" and "we are owed
#: 400k and 380k of it is not late".
BUCKETS = ("range0", "range1", "range2", "range3", "range4", "range5")

#: What a document may be aged from. Their two, and both are real: a
#: receivables clerk chases against the date the money was promised, and an
#: auditor sizing a bad-debt provision reads from the date it was billed.
BASES = ("Due Date", "Posting Date")

#: How many documents one pass carries. Past this the answer is a narrower
#: filter rather than a longer page — and the party roll-up above it is
#: complete either way, because it is summed from the whole answer before this
#: cut is taken.
MOST = 500


def _allowed(side: dict) -> None:
	"""Whether this reader may see this side of the ledger."""
	if not frappe.has_permission(side["doctype"], "read"):
		raise frappe.PermissionError(
			_("You cannot read {0}.").format(_(side["doctype"])))


def _filters(company: str, asof: str, basis: str) -> dict:
	"""What their report wants, filled in from the workspace.

	A company and a date, and neither is a form field: one workspace has one
	company, and the date somebody wants an ageing as at is today in every case
	but the one where they are closing a month — which is what `asof` is for.
	"""
	ranges = dict(zip(("range1", "range2", "range3", "range4"), BREAKS))
	return {
		"company": company,
		"report_date": asof,
		"ageing_based_on": basis,
		**ranges,
	}


def _money(value) -> float:
	from frappe.utils import flt

	return flt(value)


def _row(row: dict, side: dict) -> dict:
	"""One open document, as the browser draws it."""
	party = row.get("party") or ""
	return {
		"party": party,
		# The party's own name where the report carried one — it does for a
		# Customer and not always for a Supplier — because a receivables screen
		# that says `CUST-00042` is a screen somebody has to look things up
		# from.
		"party_label": (row.get("customer_name") or row.get("supplier_name")
		                or party or _("No party")),
		"doctype": row.get("voucher_type") or "",
		"voucher": row.get("voucher_no") or "",
		"date": str(row.get("posting_date") or ""),
		"due": str(row.get("due_date") or ""),
		# Their number, and negative where a document is not due yet. Kept
		# signed: "−14 days" is how somebody reads "a fortnight of grace left".
		"age": int(row.get("age") or 0),
		"outstanding": _money(row.get("outstanding")),
		"currency": row.get("currency") or row.get("account_currency") or "",
		"buckets": [_money(row.get(one)) for one in BUCKETS],
		# What this is *for*, where the document carries one. A project invoice
		# chased without knowing which project is a phone call that goes badly.
		"project": row.get("project") or "",
	}


def _labels(columns: list) -> list[dict]:
	"""The bucket headings, as their report words them.

	Read off the columns rather than composed from `BREAKS`, so the headings on
	screen and the numbers under them cannot come apart — the day somebody
	changes a boundary, one edit moves both.
	"""
	by_name = {one.get("fieldname"): one for one in columns or []}
	return [{"key": one, "label": (by_name.get(one) or {}).get("label") or one}
	        for one in BUCKETS]


def _by_party(rows: list[dict]) -> list[dict]:
	"""The same money, one line per party, worst first.

	Sorted by what is *late* rather than by what is outstanding, which is the
	whole point of the screen: the biggest balance on the page is usually
	somebody's largest customer paying normally, and the row worth a Monday
	morning is the smaller one with everything in the last two buckets.
	"""
	found: dict[str, dict] = {}
	for row in rows:
		one = found.setdefault(row["party"] or row["party_label"], {
			"party": row["party"],
			"party_label": row["party_label"],
			"currency": row["currency"],
			"outstanding": 0.0,
			"buckets": [0.0] * len(BUCKETS),
			"documents": 0,
			"oldest": 0,
		})
		one["outstanding"] += row["outstanding"]
		one["documents"] += 1
		one["oldest"] = max(one["oldest"], row["age"])
		for at, value in enumerate(row["buckets"]):
			one["buckets"][at] += value

	# `range0` is what is not due yet, so "late" is everything after it.
	parties = list(found.values())
	for one in parties:
		one["late"] = sum(one["buckets"][1:])
	parties.sort(key=lambda one: (one["late"], one["outstanding"]), reverse=True)
	return parties


@frappe.whitelist(methods=["GET"])
def owing(kind: str, asof: str = "", basis: str = "Due Date") -> dict:
	"""One side of the ledger, aged."""
	side = SIDES.get(kind)
	if not side:
		frappe.throw(_("{0} is not a side of the ledger.").format(kind))
	if basis not in BASES:
		basis = BASES[0]
	_allowed(side)

	company = _company()
	asof = asof or frappe.utils.nowdate()
	report = frappe.get_module(side["module"])
	answer = report.execute(frappe._dict(_filters(company, asof, basis)))
	columns, data = answer[0], answer[1]

	rows = [_row(one, side) for one in (data or []) if one]
	parties = _by_party(rows)
	totals = [sum(one["buckets"][at] for one in parties)
	          for at in range(len(BUCKETS))]

	return {
		"kind": kind,
		"label": _(side["label"]),
		"party_kind": _(side["party"]),
		"company": company,
		"asof": asof,
		"basis": basis,
		"bases": list(BASES),
		"buckets": _labels(columns),
		"parties": parties,
		# The documents behind the roll-up, so a party's line can be opened
		# without a second call — an ageing is read by expanding the one row
		# somebody is about to ring about, and a round trip per expand is a
		# round trip per row on the only screen where that happens twenty
		# times in a minute.
		"rows": rows[:MOST],
		"more": len(rows) > MOST,
		"outstanding": sum(one["outstanding"] for one in parties),
		"late": sum(one["late"] for one in parties),
		"totals": totals,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
	}
