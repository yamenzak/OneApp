"""The bank feed, turned into a reconciliation.

`docs/ONEBOOK.md` §3. OneBook's Bank feed screen lists `Bank Transaction` rows
newest first and narrowed by nothing, which is right for reading a statement
and is not a reconciliation. A reconciliation is the other question: for each
line the bank says happened, which document in these books is it — and the
answer is a ranking rather than a lookup, because a bank line carries a date,
an amount, a reference string and sometimes a name, and a payment carries the
same four with none of them guaranteed to agree.

## Their matcher, called rather than copied

ERPNext's `get_linked_payments` runs one query per document type — Payment
Entry, Journal Entry, Sales Invoice, Purchase Invoice — and each computes a
**rank** from four things: the amount matching exactly, the reference number
matching, the party matching, and the unallocated amount matching. The rows
come back sorted by it.

That ranking is the whole product. It is also four queries of forty lines each
with a sign convention per direction — a deposit looks for `paid_to` and a
withdrawal for `paid_from`, a deposit may match a Sales Invoice and never a
Purchase Invoice — and `subtract_allocations` on top, which takes off what a
voucher has already been reconciled against elsewhere. Writing that again would
be writing a second opinion about which payment a bank line is.

So this module does four things their tool does not: it asks the caller's own
permission, it narrows what may be matched against to an allowlist this file
holds, it shapes the answer into rows a browser draws, and it gives the whole
thing an address that is not the desk.

## What it refuses

`Bank Transaction` at `write`, because every verb here writes: matching sets a
clearance date on the voucher and an allocation on the transaction, and
unmatching takes both off. Reading the feed asks for `read`, which in OneBook
is the bookkeeper and above.

**The document types are not the request's.** `MATCHABLE` below is the
allowlist, and a caller naming something else gets the four. ERPNext's own
function takes the list from its dialog, where every other app's
`get_matching_queries` hook can add to it; here the four are the four OneBook
grants, so a match cannot be made against a doctype this space does not carry.

## What it is not

Not a view type — `docs/ONEBOOK.md` §1 makes that argument for the statements
and it is the same one here, more so: a reconciliation is two lists side by
side where the right-hand one is a function of the row selected in the left.

Not a bank feed importer either. Getting the statement in is Frappe's own
`Bank Statement Import`, and a workspace with a real feed has
`Bank Transaction` rows already.
"""

import frappe
from frappe import _

#: What a bank line may be matched against, and the whole of it.
#:
#: ERPNext's tool takes this list from its own dialog's checkboxes, which is
#: also how another app's `get_matching_queries` hook joins in. Held here
#: instead, because a whitelisted endpoint taking a list of document types from
#: the request is an endpoint that decides what to query from the request —
#: and because these four are exactly what OneBook grants. A fifth would be a
#: grant first and a line here second.
#:
#: `bank_transaction` is deliberately absent: matching one bank line against
#: another is how an internal transfer between two accounts of the same company
#: is settled, and this workspace has one bank account until somebody says
#: otherwise. `docs/ONEBOOK.md` §5 is where that is tracked.
MATCHABLE = ("payment_entry", "journal_entry", "sales_invoice",
             "purchase_invoice")

#: The extra key ERPNext's matcher reads as "only the ones whose amount is
#: exactly this". It is in the same list as the document types rather than
#: being a parameter, which is theirs rather than a choice.
EXACT = "exact_match"

#: How many lines one pass of the feed offers. A statement is a month and a
#: month is rarely more than this; past it the answer is a narrower date range
#: rather than a longer page, because a reconciliation is done a screen at a
#: time and a list nobody can reach the bottom of is a list nobody finishes.
MOST = 200

#: And how many candidates one line offers. ERPNext ranks them, so the tail of
#: a long list is by construction the part that matches on nothing.
CANDIDATES = 20

#: How far either side of a bank line to look for the document it is, when the
#: screen is not showing a date range of its own.
#:
#: There has to be a range: ERPNext's queries end in `posting_date BETWEEN from
#: AND to`, and passing nothing is `BETWEEN NULL AND NULL`, which matches no
#: rows at all — measured, and it is the reason this is a named pair rather
#: than two `None`s passed through.
#:
#: The two numbers are not symmetrical on purpose. A payment is *entered* after
#: it happens and sometimes long after, so a bank line from March can be a
#: payment somebody keyed in April; a payment entered a year before the money
#: moved is somebody's mistake rather than this line. So: a year behind, a
#: month ahead.
LOOK_BACK = 365
LOOK_AHEAD = 30


def _allowed(write: bool = False) -> None:
	"""Whether this reader may be here at all.

	`Bank Transaction` is the doctype every verb in this module reads or
	writes, so it is the one permission worth asking. In OneBook it is a
	Manager grant, which is the bookkeeper — the seat this space is mostly
	about, and the only one that should be deciding which payment a bank line
	is.
	"""
	if not frappe.has_permission("Bank Transaction", "write" if write else "read"):
		frappe.throw(
			_("Reconciling the bank is for whoever keeps the books."),
			frappe.PermissionError,
		)


def _account(bank_account: str) -> dict:
	"""One of this workspace's own bank accounts, or a refusal.

	A `Bank Account` row may belong to a customer or a supplier — that is what
	`is_company_account` is for — and one of those is a payee's details rather
	than a ledger. Reconciling against it would be reconciling a statement we
	do not have.
	"""
	found = frappe.db.get_value(
		"Bank Account", bank_account,
		["name", "account_name", "account", "company", "is_company_account"],
		as_dict=True,
	)
	if not found or not found.get("is_company_account"):
		frappe.throw(_("{0} is not an account of this workspace.")
		             .format(bank_account), frappe.PermissionError)
	if not found.get("account"):
		frappe.throw(
			_("{0} has no ledger account behind it, so nothing it says can be "
			  "compared with the books.").format(found.get("account_name")))
	return found


@frappe.whitelist(methods=["GET"])
def accounts() -> dict:
	"""The bank accounts this workspace keeps, for the picker at the top.

	Read rather than linked, because the screen needs one of these before it
	can ask anything and a picker with one option should arrive already
	answered.
	"""
	_allowed()
	rows = frappe.get_all(
		"Bank Account",
		filters={"is_company_account": 1, "disabled": 0},
		fields=["name", "account_name", "account", "company", "bank"],
		order_by="is_default desc, account_name asc",
	)
	return {"accounts": [dict(one) for one in rows]}


@frappe.whitelist(methods=["GET"])
def feed(bank_account: str, since: str = "", until: str = "",
         settled: int = 0) -> dict:
	"""The statement lines, and what the books say the balance was.

	`settled` asks for the reconciled ones as well, which is the one thing
	somebody wants after they have finished: a screen that hides what it has
	just done gives no way to check it, and no way to undo one.

	The balance is ERPNext's `get_account_balance`, which is not
	`get_balance_on`: it takes off the cheques written and not yet presented
	and adds back the deposits not yet cleared, which is the number a statement
	is actually compared against.
	"""
	from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
		get_account_balance,
		get_bank_transactions,
	)

	_allowed()
	account = _account(bank_account)

	rows = get_bank_transactions(
		bank_account, from_date=since or None, to_date=until or None,
		all_transactions=bool(int(settled or 0)),
	) or []

	# As at the end of the range, or as at today where the screen is showing
	# everything. A balance with no date on it is not a balance.
	from frappe.utils import nowdate

	asof = until or nowdate()
	try:
		balance = get_account_balance(bank_account, asof, account["company"])
	except Exception:
		# A balance that cannot be worked out is a missing number on the band,
		# not a screen that will not open. The lines are the page.
		frappe.clear_last_message()
		balance = None

	return {
		"account": account,
		"rows": [_line(one) for one in rows[:MOST]],
		"more": len(rows) > MOST,
		# What the books say is in this account, *as the bank would see it* —
		# ERPNext's own `get_account_balance` rather than `get_balance_on`,
		# which is the difference that matters: it takes back off the payments
		# this workspace has recorded and the bank has not cleared, and adds
		# back the ones the bank cleared and nobody recorded. On a workspace
		# that has reconciled nothing it is the opening balance, and it walks
		# towards the statement as the lines below are matched, which is the
		# whole point of showing it here.
		"balance": balance,
		"asof": asof,
		# What the feed itself adds up to over the range, which is the other
		# half of the comparison and is ours to sum rather than theirs.
		"movement": sum(_money(one.get("deposit")) - _money(one.get("withdrawal"))
		                for one in rows),
		"outstanding": sum(_money(one.get("unallocated_amount")) for one in rows),
	}


def _money(value) -> float:
	from frappe.utils import flt

	return flt(value)


def _line(row: dict) -> dict:
	"""One statement line, as the browser draws it.

	`amount` and `direction` rather than a deposit column and a withdrawal
	column: a bank line is one or the other and never both, and two columns of
	which one is always blank is how a feed comes to be twice as wide as it
	needs to be.
	"""
	deposit, withdrawal = _money(row.get("deposit")), _money(row.get("withdrawal"))
	return {
		"name": row.get("name"),
		"date": str(row.get("date") or ""),
		"amount": deposit or withdrawal,
		"direction": "in" if deposit else "out",
		"currency": row.get("currency") or "",
		"description": row.get("description") or "",
		"reference": row.get("reference_number") or "",
		"kind": row.get("transaction_type") or "",
		"party": row.get("party") or "",
		"party_type": row.get("party_type") or "",
		"status": row.get("status") or "",
		"allocated": _money(row.get("allocated_amount")),
		"unallocated": _money(row.get("unallocated_amount")),
	}


@frappe.whitelist(methods=["GET"])
def matches(transaction: str, since: str = "", until: str = "",
            exact: int = 0) -> dict:
	"""What in these books this line could be, best first.

	ERPNext's ranking, described at the top of this module. `exact` narrows it
	to candidates whose amount is the line's amount to the penny, which is the
	first thing somebody reaches for on a busy account and the reason their own
	dialog has the same switch.

	`since` and `until` are the range the feed is showing, passed through so
	that narrowing the statement narrows what it could be — which is what
	somebody means by narrowing it. Absent, the window is `LOOK_BACK` and
	`LOOK_AHEAD` around the line's own date.
	"""
	from frappe.utils import add_days, getdate

	from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
		get_linked_payments,
	)

	_allowed()
	line = _transaction(transaction)

	when = getdate(line.date)
	kinds = list(MATCHABLE) + ([EXACT] if int(exact or 0) else [])
	found = get_linked_payments(
		line.name, kinds,
		from_date=since or str(add_days(when, -LOOK_BACK)),
		to_date=until or str(add_days(when, LOOK_AHEAD)),
	) or []
	return {
		"transaction": _line(line.as_dict()),
		"matches": [_candidate(one) for one in found[:CANDIDATES]],
		"more": len(found) > CANDIDATES,
		# What is already tied to this line, which is what makes Unmatch an
		# offer rather than a guess.
		"tied": [{
			"doctype": one.payment_document, "name": one.payment_entry,
			"amount": _money(one.allocated_amount),
			"cleared": str(one.clearance_date or ""),
			"how": one.reconciliation_type or "",
		} for one in (line.payment_entries or [])],
	}


def _transaction(name: str):
	"""One submitted bank line, or a refusal.

	Submitted, because a draft statement line is a row somebody is still
	importing and allocating against it would tie a payment to something that
	may never exist.
	"""
	line = frappe.get_doc("Bank Transaction", name)
	line.check_permission("read")
	if line.docstatus != 1:
		frappe.throw(_("That line is not part of the statement yet."))
	return line


def _candidate(row: dict) -> dict:
	"""One thing this line could be.

	`rank` is carried through rather than turned into a word here: it is a
	small integer counting how many of the four things agreed, and the browser
	draws it as that — how strong a match this is — beside the row.
	"""
	return {
		"doctype": row.get("doctype"),
		"name": row.get("name"),
		"rank": int(row.get("rank") or 0),
		"amount": _money(row.get("paid_amount")),
		"reference": row.get("reference_no") or "",
		"reference_date": str(row.get("reference_date") or ""),
		"date": str(row.get("posting_date") or ""),
		"party": row.get("party") or "",
		"party_type": row.get("party_type") or "",
		"currency": row.get("currency") or "",
	}


@frappe.whitelist(methods=["POST"])
def match(transaction: str, vouchers) -> dict:
	"""This line is those documents.

	Through ERPNext's `reconcile_vouchers`, which is the solved half: it adds
	the rows, refuses a duplicate reference, allocates oldest first up to the
	line's amount, sets the clearance date on each voucher and moves the
	transaction's status on. Every one of those is a thing to get wrong twice.

	What is checked here is that the documents are ones this reader may reach
	and of a type this module matches against — a payload is a list from a
	browser, and `reconcile_vouchers` would take any doctype and name.
	"""
	from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
		reconcile_vouchers,
	)

	_allowed(write=True)
	line = _transaction(transaction)

	if isinstance(vouchers, str):
		vouchers = frappe.parse_json(vouchers)
	if not isinstance(vouchers, list) or not vouchers:
		frappe.throw(_("Nothing is ticked."))

	allowed = {kind.replace("_", " ").title() for kind in MATCHABLE}
	chosen = []
	for one in vouchers:
		if not isinstance(one, dict):
			frappe.throw(_("Those rows could not be read."))
		doctype, name = one.get("doctype"), one.get("name")
		if doctype not in allowed:
			frappe.throw(
				_("A bank line is not matched against {0} here.").format(doctype),
				frappe.PermissionError,
			)
		if not name or not frappe.db.exists(doctype, name):
			frappe.throw(_("{0} {1} is not there any more.").format(doctype, name))
		frappe.has_permission(doctype, "read", doc=name, throw=True)
		# Two keys and no amount: how much of the line each voucher takes is
		# `allocate_payment_entries`' to work out from what the voucher is
		# worth and what it has already been allocated elsewhere. A number
		# from the browser here would be a number that disagrees with the
		# ledger the moment somebody reconciles the same payment twice.
		chosen.append({"payment_doctype": doctype, "payment_name": name})

	reconcile_vouchers(line.name, frappe.as_json(chosen))
	return {"ok": True, "count": len(chosen)}


@frappe.whitelist(methods=["POST"])
def unmatch(transaction: str) -> dict:
	"""And this line is not, after all.

	`remove_payment_entries` is ERPNext's own and does the half that is easy to
	forget: taking the clearance date back off every voucher, not just the rows
	off the transaction. A reconciliation nobody can undo is one nobody trusts
	enough to do quickly.
	"""
	_allowed(write=True)
	line = _transaction(transaction)
	if not line.payment_entries:
		frappe.throw(_("Nothing is matched to that line."))

	count = len(line.payment_entries)
	line.remove_payment_entries()
	return {"ok": True, "count": count}


# --------------------------------------------------------------------------- #
# The other side of the same question
#
# A bank line asks "which document in these books is this". A payment that is
# already in the books asks the party version of it: "which invoices does this
# settle". ERPNext answers the second with `Payment Reconciliation`, and
# `docs/ONEBOOK.md` §3 says why that doctype is not a screen here.
#
# The short version: its form is three grids of results and a Link to `DocType`,
# its flow is three buttons pressed in order against a document that is never
# saved, and two of its three tables are things the tool *found* rather than
# things anybody types. Rendered as a form it is a worse version of itself.
#
# What a bookkeeper actually does with it, nine times in ten, is one sentence:
# *this receipt pays the oldest invoices that are open.* That is a verb on the
# payment, and `spaceview/actions.py` is where a verb on a record lives — so
# this is one button on the Payments screen rather than a fourth entry in the
# rail. The tenth time, where somebody wants to split a receipt across invoices
# out of order, is `docs/ONEBOOK.md` §5's list of what is deliberately out.
#
# It has to go through their tool rather than through the payment itself,
# and that is the part worth knowing: a **submitted** Payment Entry's
# references cannot simply be edited. Allocating one after the fact is ledger
# surgery — a Payment Ledger Entry against each invoice, the invoice's
# outstanding amount moved, a gain or loss booked where the rates differ — and
# `reconcile_allocations` is where all of that lives.
# --------------------------------------------------------------------------- #

#: Whose payments may be settled this way, and the whole of it.
#:
#: ERPNext's tool also takes an Employee or a Shareholder, which are advances
#: rather than invoices — a staff advance is settled by an expense claim, which
#: is OneHR's, and this space reads those rather than writing them.
SETTLEABLE = ("Customer", "Supplier")


@frappe.whitelist(methods=["POST"])
def settle(name: str) -> dict:
	"""Apply this payment to the party's open invoices, oldest first.

	Through ERPNext's `Payment Reconciliation`, driven rather than drawn: the
	tool is built in memory for this one party, asked what is unsettled,
	narrowed to this one payment, and told to allocate. Nothing is stored — the
	doctype's own `db_update` is a no-op, which is Frappe's way of saying it is
	a question and not a record.

	Oldest first is theirs too. `allocate_entries` walks the invoices in the
	order it found them, which `get_invoice_entries` orders by date, taking as
	much of each as the payment has left.
	"""
	from erpnext.accounts.party import get_party_account

	_allowed(write=True)

	payment = frappe.get_doc("Payment Entry", name)
	payment.check_permission("write")
	if payment.docstatus != 1:
		frappe.throw(_("A payment settles invoices once it is submitted."))
	if payment.party_type not in SETTLEABLE:
		frappe.throw(
			_("A payment to {0} is not settled against invoices.")
			.format(payment.party_type or _("nobody")))
	if not _money(payment.unallocated_amount):
		frappe.throw(_("Every part of this payment is already allocated."))

	tool = frappe.get_single("Payment Reconciliation")
	tool.company = payment.company
	tool.party_type = payment.party_type
	tool.party = payment.party
	tool.receivable_payable_account = get_party_account(
		payment.party_type, payment.party, payment.company)
	tool.get_unreconciled_entries()

	# This payment and no other. The tool found every unsettled payment the
	# party has, which is right for its own screen and wrong for a button
	# pressed on one row: settling four receipts because somebody asked about
	# one is not what the button says.
	mine = [one for one in (tool.payments or [])
	        if one.reference_name == payment.name]
	if not mine:
		frappe.throw(_("This payment is not waiting to be allocated."))
	if not tool.invoices:
		frappe.throw(_("{0} has nothing outstanding.").format(payment.party))

	tool.allocate_entries({
		"payments": [frappe._dict(one.as_dict()) for one in mine],
		"invoices": [frappe._dict(one.as_dict()) for one in tool.invoices],
	})
	if not tool.allocation:
		frappe.throw(_("Nothing of this payment could be allocated."))

	against = [{"invoice": one.invoice_number, "amount": _money(one.allocated_amount)}
	           for one in tool.allocation]
	tool.reconcile()
	return {"ok": True, "count": len(against), "against": against}


def actions() -> dict:
	"""The one verb, on the one screen it belongs to.

	Declared here rather than in the manifest for the reason
	`spaceview/actions.py` opens with: an action names a method, and a list of
	methods a workspace could extend by editing a row is not a thing to have.
	"""
	return {
		"onebook/payments": [
			{
				"key": "settle",
				"label": _("Settle against invoices"),
				"icon": "lucide-hand-coins",
				"scope": "one",
				# Ledger surgery on a submitted document, so it asks first.
				"confirm": _("Apply what is left of this payment to the "
				             "party's open invoices, oldest first?"),
				"method": "oneapp.onebook.reconcile.settle",
			},
		],
	}
