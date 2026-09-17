"""The three statements a set of books exists to produce.

`docs/ONEBOOK.md` §1. A trial balance, a profit and loss and a balance sheet
are the reports an accountant asks for and the reason anybody keeps books at
all. OneBook shipped without them — twenty-one screens, a ledger, and no way to
answer "what did we earn" — which is the gap the retrospective after
`docs/CLEANUP.md` stage 13 named first.

## Their reports, called rather than copied

ERPNext ships all three, each with an `execute(filters)` that returns
`(columns, data)`. Each carries things that are easy to get wrong and expensive
to get wrong twice: the sign convention per root type, the chart's tree order
and indent, period columns built from a fiscal year and a periodicity,
accumulated values, presentation currency, and the closing-entry handling that
decides whether an opening balance is one.

Writing the queries ourselves is not hard — a trial balance is a grouped sum —
and that is not the objection. The objection is that a second implementation of
a financial statement is a second answer to "what did we earn", and the day the
two disagree is the day somebody has to decide which of them the auditor was
shown.

So the seam is three entries in `oneapp/adapters/erpnext.py` and this module,
which does three things their reports do not: asks the caller's own
permissions, fills in the filters from the workspace rather than from a form,
and flattens `(columns, data)` into one shape for all three.

## One shape, because they already share one

Measured rather than assumed: all three return rows carrying `account`,
`account_name`, `indent` and `currency`, plus one or more `Currency` columns —
one per period. The differences are which columns and which rows are totals,
and both are visible in the payload. So `Statement.vue` draws any of them and a
fourth report of the same shape needs a row in `REPORTS` and nothing else.

## What it refuses

A statement reads every posting in the company, so the permission is not a
formality. The caller must be able to read `GL Entry`, which in OneBook is
every seat including Audit and in a space that does not grant it is nobody.
That is the same check the Ledger screen makes, asked here because a report is
not a list and none of the list machinery runs.
"""

import frappe
from frappe import _

#: The reports this serves, and the module each lives in.
#:
#: Named rather than discovered, and the reason is the permission above: a
#: whitelisted endpoint that ran any report by name would run `Bisect
#: Accounting Statements` and everything else ERPNext ships, against a filter
#: dictionary a caller composed. This is an allowlist of three.
REPORTS = {
	"trial-balance": {
		"module": "erpnext.accounts.report.trial_balance.trial_balance",
		"label": "Trial balance",
		# A trial balance is a year, not a range of periods: its columns are
		# opening, movement and closing rather than one per month.
		"period": False,
	},
	"profit-and-loss": {
		"module": "erpnext.accounts.report.profit_and_loss_statement"
		          ".profit_and_loss_statement",
		"label": "Profit and loss",
		"period": True,
	},
	"balance-sheet": {
		"module": "erpnext.accounts.report.balance_sheet.balance_sheet",
		"label": "Balance sheet",
		"period": True,
	},
}

#: How a period report may be cut. ERPNext's own words, because they end up in
#: its filters — and the set is short because a statement cut finer than a
#: month is a ledger.
PERIODS = ("Monthly", "Quarterly", "Half-Yearly", "Yearly")

#: What a column has to be to hold a number. Everything else in the payload is
#: the account, its name, its number and its currency.
MONEY = "Currency"


def _company() -> str:
	"""The workspace's company.

	One per workspace — `docs/WORKSPACE-SETTINGS.md`, and `onespace/books.py`
	refuses a second — so this is a read rather than a choice, and a filter the
	screen does not have to offer.
	"""
	found = frappe.get_all("Company", pluck="name", limit=1)
	if not found:
		frappe.throw(_("This workspace has no company yet."))
	return found[0]


def _year(fiscal_year: str = "") -> dict:
	"""The fiscal year asked for, or the one today is in.

	Falling back to the *current* year rather than the newest: a workspace that
	has set up next year in advance would otherwise open every statement on a
	year with nothing in it.
	"""
	if fiscal_year:
		found = frappe.db.get_value(
			"Fiscal Year", fiscal_year,
			["name", "year_start_date", "year_end_date"], as_dict=True)
		if found:
			return found
		frappe.throw(_("{0} is not a fiscal year.").format(fiscal_year))

	today = frappe.utils.nowdate()
	rows = frappe.get_all(
		"Fiscal Year",
		filters={"year_start_date": ("<=", today), "year_end_date": (">=", today),
		         "disabled": 0},
		fields=["name", "year_start_date", "year_end_date"], limit=1,
	)
	if rows:
		return rows[0]

	rows = frappe.get_all(
		"Fiscal Year", filters={"disabled": 0},
		fields=["name", "year_start_date", "year_end_date"],
		order_by="year_start_date desc", limit=1,
	)
	if not rows:
		frappe.throw(_("This workspace has no fiscal year yet."))
	return rows[0]


def years() -> list[str]:
	"""Every year a statement may be asked for, newest first."""
	return frappe.get_all("Fiscal Year", filters={"disabled": 0}, pluck="name",
	                      order_by="year_start_date desc")


def _filters(kind: str, year: dict, company: str, periodicity: str) -> dict:
	"""What one report wants, which is not what another wants.

	The two period reports take a from/to fiscal year and a periodicity; the
	trial balance takes one year and a date range inside it. Both are filled in
	from the workspace rather than asked for, because a company and a fiscal
	year are facts about the site and a form that asks for them is a form that
	can be answered wrongly.
	"""
	common = {
		"company": company,
		"presentation_currency": frappe.get_cached_value(
			"Company", company, "default_currency"),
	}
	if REPORTS[kind]["period"]:
		return {
			**common,
			"filter_based_on": "Fiscal Year",
			"from_fiscal_year": year["name"],
			"to_fiscal_year": year["name"],
			"period_start_date": str(year["year_start_date"]),
			"period_end_date": str(year["year_end_date"]),
			"periodicity": periodicity,
			"accumulated_values": 0,
		}
	return {
		**common,
		"fiscal_year": year["name"],
		"from_date": str(year["year_start_date"]),
		"to_date": str(year["year_end_date"]),
		# Without this an opening balance is whatever the ledger held before
		# the first of the year, including the entry that closed the year
		# before — which double-counts the retained earnings the closing
		# voucher just moved.
		"with_period_closing_entry_for_opening": 1,
	}


def _shape(columns: list, data: list) -> dict:
	"""`(columns, data)` as one payload, for any of the three.

	Rows arrive with an `indent` and a `parent_account`, and the totals ERPNext
	appends arrive with neither — quoted labels like `'Total Income (Credit)'`
	and a blank row between sections. Both are kept and marked rather than
	dropped: a statement without its totals is a list of accounts, and the
	blank rows are how a reader tells income from expenses.
	"""
	money = [one for one in columns
	         if (one.get("fieldtype") or "") == MONEY]

	rows = []
	for row in data or []:
		if not row:
			# ERPNext's own section break. Kept, because it is the only thing
			# separating income from expenses on a P&L.
			rows.append({"kind": "gap"})
			continue
		account = row.get("account") or ""
		total = not row.get("parent_account") and row.get("indent") is None
		rows.append({
			"kind": "total" if total else "account",
			"account": account,
			"label": (row.get("account_name") or account).strip("'"),
			"indent": int(row.get("indent") or 0),
			"is_group": bool(row.get("is_group")),
			"currency": row.get("currency") or "",
			"values": [row.get(one["fieldname"]) for one in money],
		})

	return {
		"columns": [{"key": one["fieldname"], "label": one["label"]}
		            for one in money],
		"rows": rows,
	}


@frappe.whitelist()
def statement(kind: str, fiscal_year: str = "", periodicity: str = "Yearly") -> dict:
	"""One statement, as the screen draws it."""
	if kind not in REPORTS:
		frappe.throw(_("{0} is not a statement.").format(kind))
	if periodicity not in PERIODS:
		periodicity = "Yearly"

	# The same permission the Ledger screen asks for. A report is not a list,
	# so none of the list machinery runs and nothing else would ask.
	if not frappe.has_permission("GL Entry", "read"):
		raise frappe.PermissionError(_("You cannot read the ledger."))

	company = _company()
	year = _year(fiscal_year)
	report = frappe.get_module(REPORTS[kind]["module"])
	columns, data = report.execute(
		frappe._dict(_filters(kind, year, company, periodicity)))[:2]

	return {
		**_shape(columns, data),
		"kind": kind,
		"label": _(REPORTS[kind]["label"]),
		"company": company,
		"fiscal_year": year["name"],
		"years": years(),
		"periodicity": periodicity if REPORTS[kind]["period"] else "",
		"periods": list(PERIODS) if REPORTS[kind]["period"] else [],
	}
