"""OneBook — the ledger, and everything the other spaces post into it.

`docs/CLEANUP.md` §5 and §7. Every other space *raises* money: OnePeople runs a
payroll, OneProject bills a project, OneCRM quotes a deal. None of them posts,
pays or reconciles anything, and that is deliberate — the line is drawn once,
here, and the three of them read the result rather than keeping a second set of
totals. What this space owns is the other half: the invoice that is owed, the
bill that is due, the payment that clears it, the journal underneath and the
chart it all lands in.

Until this stage it was a **reference entitlement**: eight ERPNext doctypes, no
screens, and a docstring saying nobody had decided to build a books app. It
existed so the entitlement pipeline had something running through it end to end.
That job is done — four real spaces now run through the same pipeline — and what
is left is the thing the pipeline was a stand-in for.

It is over ERPNext's accounting and invents nothing. `docs/ERP-SPACES.md` is the
argument and it applies here hardest of all: a general ledger is the most solved
problem in business software, a second one is a set of books that does not
agree with the first, and the interesting work is entirely in *which* of the
hundred and ninety-three doctypes in that module a person is ever shown.

**Nineteen of them**, and the number is the point. ERPNext's Accounts module has
193 doctypes and a desk that lists all of them; a bookkeeper uses about a dozen
and a business owner about four. What is left out is not hidden — it is
somebody else's job, or it is a setting, or it is a report that this product
draws as a dashboard over a list it already has.

**Generally applicable, and deliberately plain.** It says Invoice and Bill and
Journal, which is what every accountant on earth calls them, and it does not
invent house words for things that already have names.
"""

import json

SPACE = {
	"space_code": "onebook",
	"space_label": "OneBook",
	"module": "OneBook",
	# The Frappe role prefix, so the four seats are `Books-User`,
	# `Books-Manager`, `Books-Audit` and `Books-Admin`. Plural, because the
	# thing a bookkeeper keeps is the books and a `Book-Manager` sounds like
	# somebody who runs one.
	"role_name": "Books",
	# ERPNext for everything, and HRMS for the three doctypes under **Raised
	# elsewhere** — a workspace without either is one where some of these
	# screens are empty, and `entitlements/apps.py` refuses the grant with the
	# app named rather than succeeding into that.
	"requires_apps": "erpnext,hrms",
	"icon": "lucide-book-open",
	"brand": "onebook",
	"sort_order": 10,
	# Restricted on the way in like every other shipped space; an operator
	# turns it on. `install()` writes this only when the space is new, so the
	# switch stays where the operator put it.
	"availability": "Restricted",
	"description": "Invoices, bills, payments and the ledger under them.",
	# Light, and amber off the mark. A page of money is a page of numbers, and
	# numbers on a dark ground at 13px is the screen people print instead of
	# reading. The accent moves the solid buttons and the tab indicator, which
	# on this space is mostly the Submit button — so it is the colour of the
	# one irreversible thing here, which is fair warning.
	"theme": json.dumps({
		"mode": "light",
		"accent": "#b45309",
		"radius": "soft",
	}),
}

# --------------------------------------------------------------------------- #
# The three jobs, and the fourth that is derived
#
# Every other space had to argue about how many honest seats it has. This one
# does not, because accounting has had the answer for four hundred years and it
# is the reason the four seats in `spaces/roles.py` are the four they are.
#
# **User raises.** Somebody makes an invoice and sends it. They can see what a
# customer owes and what the chart looks like, and they cannot post a payment,
# write a journal or touch an account. In most workspaces this is whoever runs
# the sales desk, and in a small one it is the owner.
#
# **Manager keeps the books.** Payments, journals, purchase invoices, bank
# reconciliation — everything that moves money or decides which account it
# moved between. This is the bookkeeper, and it is the seat this space is
# mostly about.
#
# **Admin owns the shape.** The chart of accounts, the fiscal year, the
# accounting periods. Three things that are changed about twice a year and
# whose change reaches every number on every screen, which is exactly the
# profile of a thing that belongs one rung above the person using it daily.
#
# **Audit reads and writes nothing**, which `registry.laddered` derives at Read
# from every grant below without this file saying a word. It is worth naming
# because this is the space the seat was invented for: an auditor is a real
# person who turns up once a year, is given the books, and must not be able to
# change one of them.
# --------------------------------------------------------------------------- #

DOCTYPES = [
	# ----- Everybody in the space ----------------------------------------- #
	#
	# What we are owed. `Manage` rather than Write because raising an invoice
	# and cancelling the one you raised in error are the same job, and a draft
	# nobody can delete is a list that fills up with mistakes.
	("Sales Invoice", "Manage", 0),
	# The masters an invoice resolves a link against. Read, because picking a
	# customer is not permission to invent one — OneCRM owns the party and
	# `docs/CLEANUP.md` §7 says entities live once.
	("Customer", "Read", 0),
	("Item", "Read", 0),
	("Company", "Read", 0),
	("Currency", "Read", 0),
	("Account", "Read", 0),
	("Cost Center", "Read", 0),
	("Mode of Payment", "Read", 0),
	("Payment Terms Template", "Read", 0),
	("Sales Taxes and Charges Template", "Read", 0),
	("Fiscal Year", "Read", 0),
	("Accounting Period", "Read", 0),
	# The ledger itself, read by everybody who may see any of it. A GL Entry is
	# written by the documents above and by nothing else — there is no New
	# button on this doctype anywhere in ERPNext either — so Read is not a
	# restriction, it is the only access that exists.
	("GL Entry", "Read", 0),
	# The engine's own. A screen that cannot save a view is a screen people
	# stop using in the second week; `if_owner`, so a saved view is the saver's.
	("OneSpace Saved View", "Write", 1),
	("OneSpace Word", "Read", 0),

	# ----- Manager: the bookkeeper ---------------------------------------- #
	#
	# The money moving, and the account it moved between. Everything on this
	# rung is a thing that changes a balance.
	("Payment Entry", "Manage", 0, "manager"),
	("Journal Entry", "Manage", 0, "manager"),
	("Purchase Invoice", "Manage", 0, "manager"),
	# Who we pay. OneCRM owns the customer and nothing owns the supplier, so
	# this space does — a supplier exists because you owe them money, which is
	# the whole of what is known about one here. When OneInventory is built it
	# will want the same doctype and it will read it, the way OneProject reads
	# a Sales Invoice.
	("Supplier", "Manage", 0, "manager"),
	("Supplier Group", "Read", 0, "manager"),
	("Purchase Taxes and Charges Template", "Read", 0, "manager"),
	# The bank feed and what it is reconciled against.
	("Bank Transaction", "Manage", 0, "manager"),
	# And the tool behind the party side of the same question — the one grant
	# here with no screen, deliberately. `Payment Reconciliation` is a doctype
	# that is never saved: its `db_update` is a no-op, which is Frappe's way of
	# saying it is a question rather than a record. `onebook/reconcile.py`
	# drives it from a button on the Payments screen, and §3 of
	# `docs/ONEBOOK.md` says why rendering its form would be a worse version of
	# it than the button is.
	("Payment Reconciliation", "Write", 0, "manager"),
	("Bank Account", "Write", 0, "manager"),
	("Bank", "Read", 0, "manager"),
	# What the other spaces raised, read and never written. This is the half of
	# the space `docs/CLEANUP.md` §5 is actually about: the bookkeeper sees the
	# payroll register because they are the one paying it, and sees an approved
	# expense claim because it is a liability until somebody settles it. They
	# cannot approve either — that is OnePeople's, and the grant says so by
	# being Read.
	("Salary Slip", "Read", 0, "manager"),
	("Payroll Entry", "Read", 0, "manager"),
	("Expense Claim", "Read", 0, "manager"),
	("Employee", "Read", 0, "manager"),
	("Project", "Read", 0, "manager"),
	("OneSpace Word", "Write", 0, "manager"),

	# ----- Admin: the shape of the books ---------------------------------- #
	("Account", "Manage", 0, "admin"),
	("Cost Center", "Manage", 0, "admin"),
	("Fiscal Year", "Manage", 0, "admin"),
	("Accounting Period", "Manage", 0, "admin"),
	# Where a set of books begins and where a year of it ends —
	# `docs/ONEBOOK.md` §2. Both are Admin because both are once-a-year and
	# both reach every number on every screen: taking an opening balance twice
	# doubles the books, and closing a period stops everybody else posting.
	#
	# `Opening Invoice Creation Tool` is a Single, so this grant is what the
	# engine's Single page checks rather than what a list is narrowed by —
	# `oneapp/onespace/singles.py`. Write rather than Manage because there is
	# no document to create or delete: there is one, and it is never saved.
	("Opening Invoice Creation Tool", "Write", 0, "admin"),
	("Period Closing Voucher", "Manage", 0, "admin"),
	("Mode of Payment", "Manage", 0, "admin"),
	("Payment Terms Template", "Manage", 0, "admin"),
	("Sales Taxes and Charges Template", "Manage", 0, "admin"),
	("Purchase Taxes and Charges Template", "Manage", 0, "admin"),
]

# --------------------------------------------------------------------------- #
# Where a document came from
#
# The one field this space adds, and the reason it is worth adding is the
# checkpoint `docs/CLEANUP.md` §9 sets for this stage: a payslip and a project
# invoice in one place. Getting them onto one rail is the easy half. The half
# that matters is that once they are there, nothing on the screen says *which
# of them somebody else raised* — and a bookkeeper's first question about any
# row in these lists is exactly that, because it decides who they go and ask.
#
# ERPNext already knows. A Sales Invoice carries the project it belongs to; a
# payroll bank entry carries a `Journal Entry Account` row pointing at the
# Payroll Entry; a payment settling an expense claim carries a reference row
# naming it. Three different places, none of them a column, none of them
# sortable, all of them requiring the record to be open.
#
# So `custom_origin` is a **cache of a join**, read off the document's own
# links on save by `onebook/origin.py` and never typed. It holds a space code
# from `oneapp/catalogue.py` — `onehr`, `oneproject`, `onecrm` — or nothing at
# all, which means somebody raised it here. Read-only in every seat, because a
# provenance somebody can edit is a provenance.
# --------------------------------------------------------------------------- #

#: The four documents that can arrive from somewhere else. A Purchase Invoice
#: is on the list because a project's subcontractor bill is the other half of
#: billing the project, and leaving it off would answer the question on three
#: screens out of four.
POSTED_INTO = ("Sales Invoice", "Purchase Invoice", "Payment Entry",
               "Journal Entry")

ORIGIN = {
	"fieldname": "custom_origin",
	"label": "Raised by",
	"fieldtype": "Data",
	"read_only": 1,
	"in_standard_filter": 1,
	"description": "Which space raised this, worked out from what the document "
	               "already points at — a project, a payroll run, a claim. "
	               "Blank means somebody raised it in OneBook. Written by "
	               "`onebook/origin.py` and by nothing else.",
}

CUSTOM_FIELDS = [
	{**ORIGIN, "dt": "Sales Invoice", "insert_after": "project"},
	{**ORIGIN, "dt": "Purchase Invoice", "insert_after": "project"},
	{**ORIGIN, "dt": "Payment Entry", "insert_after": "project"},
	# The one that has no `project` to sit after, because a Journal Entry has
	# no project at all — it is the document ERPNext posts everything else
	# *through*, which is also why it is the one most likely to have come from
	# somewhere else.
	{**ORIGIN, "dt": "Journal Entry", "insert_after": "user_remark"},
]

SCREENS = [
	{
		# Four blocks and each is a screen of this space, so each draws that
		# screen's own columns and is checked where every list is checked —
		# `onespace/homepage.py`. The first two are the two halves of working
		# capital; the third and fourth are what the other spaces raised and
		# what has actually been paid.
		#
		# A block whose screen the reader cannot open is not sent at all, which
		# is how a User's home and a bookkeeper's differ without either being
		# written: **Payroll** and **Payments** are Manager grants, so somebody
		# raising invoices lands on a page about invoices.
		"screen": "home", "label": "Home", "singular": "Day",
		"icon": "lucide-layout-grid",
		"component": "home",
		"view_settings": json.dumps({"home": {
			"blocks": ["invoices", "bills", "payroll", "payments"],
		}}),
	},

	# ----- Statements ------------------------------------------------------ #
	#
	# The three reports a set of books exists to produce, and the answer to the
	# question the retrospective after `docs/CLEANUP.md` stage 13 asked first:
	# a books space that cannot produce a profit and loss is not a books space.
	#
	# `component` screens rather than a view type, and `docs/ONEBOOK.md` §1 is
	# the argument: a view type is an alternate rendering of the rows a screen
	# has already narrowed to, and a statement is a different aggregation with
	# its own filters over rows no screen lists.
	#
	# First after Home, and above everything else, because this is what
	# somebody opens OneBook *for*. Every other screen here is a document or a
	# list of them; these are the three sentences the documents add up to. The
	# ledger is where a person goes when a number on one of these is wrong,
	# which is why it is four headings further down rather than beside them.
	{
		"screen": "trial-balance", "label": "Trial balance",
		"singular": "Account", "screen_group": "Statements",
		"icon": "lucide-table", "component": "onebook/trial-balance",
	},
	{
		"screen": "profit-and-loss", "label": "Profit and loss",
		"singular": "Account", "screen_group": "Statements",
		"icon": "lucide-chart-line", "component": "onebook/profit-and-loss",
	},
	{
		"screen": "balance-sheet", "label": "Balance sheet",
		"singular": "Account", "screen_group": "Statements",
		"icon": "lucide-chart-pie", "component": "onebook/balance-sheet",
	},

	# ----- Sales ---------------------------------------------------------- #
	{
		# The spine on the receivable side, and the screen the checkpoint is
		# half of: `project` is a column, so a project invoice is visible as
		# one without anybody opening it, and `custom_origin` says so in a word
		# for the rows where the project is somebody else's word for it.
		#
		# Ordered by due date rather than posting date, ascending, which is the
		# one sort a receivables list is ever read in: the oldest thing owed is
		# the thing somebody has to ring about this morning.
		"screen": "invoices", "label": "Invoices", "singular": "Invoice",
		"screen_group": "Sales",
		"icon": "lucide-receipt", "document_type": "Sales Invoice",
		"fields": "customer_name,project,custom_origin,posting_date,due_date,"
		          "grand_total,outstanding_amount,status",
		"order_by": "due_date asc",
		"view_types": "list,report,calendar,dashboard",
		"status_field": "status",
		"field_icons": json.dumps({
			"status": "lucide-flag",
			"outstanding_amount": "lucide-circle-alert",
			"due_date": "lucide-calendar-clock",
		}),
		"view_settings": json.dumps({
			"calendar": {"start_field": "due_date"},
			"tags": ["custom_origin", "status"],
			"dashboard": {
				"period_field": "posting_date",
				"widgets": [
					{"kind": "number", "label": "Invoices", "width": 3},
					{"kind": "number", "label": "Invoiced", "aggregate": "sum",
					 "field": "grand_total", "width": 3},
					{"kind": "number", "label": "Outstanding", "aggregate": "sum",
					 "field": "outstanding_amount", "width": 3},
					{"kind": "number", "label": "Average", "aggregate": "avg",
					 "field": "grand_total", "width": 3},
					{"kind": "donut", "label": "Where each one stands",
					 "group_by": "status", "width": 6},
					# The plot this space exists for, and the reason
					# `custom_origin` is a real column rather than a note: how
					# much of what we are owed was raised by somebody else.
					{"kind": "donut", "label": "Raised by",
					 "group_by": "custom_origin", "width": 6},
					{"kind": "bar", "label": "Owed by customer",
					 "group_by": "customer_name", "aggregate": "sum",
					 "field": "outstanding_amount", "horizontal": True,
					 "width": 6},
					{"kind": "bar", "label": "Billed by project",
					 "group_by": "project", "aggregate": "sum",
					 "field": "grand_total", "horizontal": True, "width": 6},
					{"kind": "line", "label": "Invoiced by month",
					 "group_by": "posting_date", "grain": "month",
					 "aggregate": "sum", "field": "grand_total", "width": 12},
				],
			},
		}),
	},

	# ----- Purchases ------------------------------------------------------ #
	{
		# The other half of working capital. Same shape as the screen above and
		# deliberately so: an accounts payable list and an accounts receivable
		# list ask the same four questions in the same order, and a workspace
		# where they look different is one where somebody reads the wrong
		# column.
		"screen": "bills", "label": "Bills", "singular": "Bill",
		"screen_group": "Purchases",
		"icon": "lucide-file-text", "document_type": "Purchase Invoice",
		"fields": "supplier_name,bill_no,project,custom_origin,posting_date,"
		          "due_date,grand_total,outstanding_amount,status",
		"order_by": "due_date asc",
		"view_types": "list,report,calendar,dashboard",
		"status_field": "status",
		"field_icons": json.dumps({
			"status": "lucide-flag",
			"outstanding_amount": "lucide-circle-alert",
			"due_date": "lucide-calendar-clock",
		}),
		"view_settings": json.dumps({
			"calendar": {"start_field": "due_date"},
			"tags": ["custom_origin", "status"],
			"dashboard": {
				"period_field": "posting_date",
				"widgets": [
					{"kind": "number", "label": "Bills", "width": 3},
					{"kind": "number", "label": "Billed", "aggregate": "sum",
					 "field": "grand_total", "width": 3},
					{"kind": "number", "label": "Outstanding", "aggregate": "sum",
					 "field": "outstanding_amount", "width": 3},
					{"kind": "number", "label": "Average", "aggregate": "avg",
					 "field": "grand_total", "width": 3},
					{"kind": "donut", "label": "Where each one stands",
					 "group_by": "status", "width": 6},
					{"kind": "bar", "label": "Owed to supplier",
					 "group_by": "supplier_name", "aggregate": "sum",
					 "field": "outstanding_amount", "horizontal": True,
					 "width": 6},
					{"kind": "line", "label": "Billed by month",
					 "group_by": "posting_date", "grain": "month",
					 "aggregate": "sum", "field": "grand_total", "width": 12},
				],
			},
		}),
	},
	{
		"screen": "suppliers", "label": "Suppliers", "singular": "Supplier",
		"screen_group": "Purchases",
		"icon": "lucide-truck", "document_type": "Supplier",
		"fields": "supplier_name,supplier_group,country,default_currency,"
		          "payment_terms,on_hold",
		"order_by": "supplier_name asc",
		"view_types": "list,grid",
		"view_settings": json.dumps({
			"tags": ["supplier_group", "country"],
			"grid": {"title_field": "supplier_name",
			         "subtitle_field": "supplier_group",
			         "image_field": "image"},
		}),
	},

	# ----- Money ---------------------------------------------------------- #
	{
		# What actually moved. Posting date descending, because a payments list
		# is read as "what happened" and the newest thing is the answer.
		"screen": "payments", "label": "Payments", "singular": "Payment",
		"screen_group": "Money",
		"icon": "lucide-wallet", "document_type": "Payment Entry",
		"fields": "party_name,payment_type,custom_origin,posting_date,"
		          "mode_of_payment,paid_amount,status",
		"order_by": "posting_date desc",
		"view_types": "list,report,calendar,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "posting_date"},
			"tags": ["payment_type", "mode_of_payment", "custom_origin"],
			"dashboard": {
				"period_field": "posting_date",
				"widgets": [
					{"kind": "number", "label": "Payments", "width": 4},
					{"kind": "number", "label": "Paid", "aggregate": "sum",
					 "field": "paid_amount", "width": 4},
					{"kind": "number", "label": "Received", "aggregate": "sum",
					 "field": "received_amount", "width": 4},
					{"kind": "donut", "label": "In or out",
					 "group_by": "payment_type", "width": 6},
					{"kind": "donut", "label": "How",
					 "group_by": "mode_of_payment", "width": 6},
					{"kind": "line", "label": "Paid by month",
					 "group_by": "posting_date", "grain": "month",
					 "aggregate": "sum", "field": "paid_amount", "width": 12},
				],
			},
		}),
	},
	{
		# Everything the other documents could not say, and the one place a
		# payroll run lands. `voucher_type` is a tag rather than a column
		# because it has nine values and eight of them are one word.
		"screen": "journals", "label": "Journal entries", "singular": "Entry",
		"screen_group": "Money",
		"icon": "lucide-book-open-text", "document_type": "Journal Entry",
		"fields": "title,voucher_type,custom_origin,posting_date,total_debit,"
		          "user_remark",
		"order_by": "posting_date desc",
		"view_types": "list,report,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "posting_date"},
			"tags": ["voucher_type", "custom_origin"],
		}),
	},
	{
		# And the other half of the bank feed: which document in these books
		# each line of it is. A two-pane screen, because the right-hand list is
		# a function of the row selected in the left — `docs/ONEBOOK.md` §3 and
		# `onebook/reconcile.py`, which calls ERPNext's ranking rather than
		# writing a second opinion about which payment a bank line is.
		#
		# Above the feed rather than below it, because reading the statement is
		# what somebody does *while* reconciling it rather than instead.
		"screen": "reconcile", "label": "Reconcile", "singular": "Line",
		"screen_group": "Money",
		"icon": "lucide-git-compare", "document_type": "Bank Transaction",
		"component": "onebook/reconcile",
	},
	{
		# The bank feed, which is the one screen here whose rows nobody in this
		# workspace wrote. Ordered newest first and narrowed by nothing: a
		# reconciliation is done by reading the whole statement, and a filter
		# that hid the matched ones would hide the evidence that they match.
		"screen": "banking", "label": "Bank feed", "singular": "Transaction",
		"screen_group": "Money",
		"icon": "lucide-landmark", "document_type": "Bank Transaction",
		"fields": "date,bank_account,description,reference_number,deposit,"
		          "withdrawal,unallocated_amount,status",
		"order_by": "date desc",
		"view_types": "list,report,calendar,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "date"},
			"tags": ["status", "bank_account"],
			"dashboard": {
				"period_field": "date",
				"widgets": [
					{"kind": "number", "label": "Transactions", "width": 4},
					{"kind": "number", "label": "In", "aggregate": "sum",
					 "field": "deposit", "width": 4},
					{"kind": "number", "label": "Out", "aggregate": "sum",
					 "field": "withdrawal", "width": 4},
					{"kind": "donut", "label": "Reconciled",
					 "group_by": "status", "width": 6},
					{"kind": "bar", "label": "By account",
					 "group_by": "bank_account", "aggregate": "sum",
					 "field": "deposit", "horizontal": True, "width": 6},
				],
			},
		}),
	},
	{
		"screen": "bank-accounts", "hide_in_nav": 1, "label": "Bank accounts",
		"singular": "Bank account", "screen_group": "Money",
		"icon": "lucide-credit-card", "document_type": "Bank Account",
		"fields": "account_name,bank,account,account_type,is_company_account,"
		          "disabled",
		"order_by": "account_name asc",
		"view_types": "list",
	},

	# ----- The ledger ----------------------------------------------------- #
	{
		# The thing the space is named for, and the one screen here with no New
		# button — `hide_new`, because a GL Entry is written by the documents
		# above and by nothing else. ERPNext has no way to make one by hand
		# either; this says so on the screen rather than letting somebody find
		# out from a traceback.
		#
		# Opens as a report rather than a list, which is the one screen in this
		# product where that is the right default: nobody opens the general
		# ledger to click a row, they open it to read down a column and total
		# it.
		"screen": "ledger", "label": "Ledger", "singular": "Entry",
		"screen_group": "Ledger",
		"icon": "lucide-table", "document_type": "GL Entry",
		"fields": "posting_date,account,party,debit,credit,voucher_type,"
		          "voucher_no,cost_center",
		"order_by": "posting_date desc",
		"hide_new": 1,
		"view_types": "report,list,dashboard",
		"view_settings": json.dumps({
			"tags": ["voucher_type", "party_type"],
			"dashboard": {
				"period_field": "posting_date",
				"widgets": [
					{"kind": "number", "label": "Entries", "width": 4},
					{"kind": "number", "label": "Debit", "aggregate": "sum",
					 "field": "debit", "width": 4},
					{"kind": "number", "label": "Credit", "aggregate": "sum",
					 "field": "credit", "width": 4},
					# The two plots that are a trial balance and a day book,
					# drawn off the rows the screen has already narrowed to —
					# which is why they can never disagree with the list above
					# them.
					{"kind": "bar", "label": "Debit by account",
					 "group_by": "account", "aggregate": "sum", "field": "debit",
					 "horizontal": True, "width": 6},
					{"kind": "bar", "label": "Credit by account",
					 "group_by": "account", "aggregate": "sum", "field": "credit",
					 "horizontal": True, "width": 6},
					{"kind": "line", "label": "Posted by month",
					 "group_by": "posting_date", "grain": "month",
					 "aggregate": "sum", "field": "debit", "width": 12},
				],
			},
		}),
	},
	{
		# A chart of accounts is a tree and has never been anything else. Drawn
		# as a list it is four hundred rows whose names all begin with the same
		# three words.
		"screen": "accounts", "label": "Chart of accounts",
		"singular": "Account", "screen_group": "Ledger",
		"icon": "lucide-list-tree", "document_type": "Account",
		"fields": "account_name,account_number,root_type,account_type,"
		          "account_currency,is_group,disabled",
		"order_by": "account_number asc, account_name asc",
		"view_types": "tree,list",
		"view_settings": json.dumps({
			"tree": {"parent_field": "parent_account",
			         "label_field": "account_name"},
			"tags": ["root_type", "account_type"],
		}),
	},
	{
		"screen": "centres", "label": "Cost centres", "singular": "Cost centre",
		"screen_group": "Ledger",
		"icon": "lucide-git-branch", "document_type": "Cost Center",
		"fields": "cost_center_name,cost_center_number,parent_cost_center,"
		          "is_group,disabled",
		"order_by": "cost_center_name asc",
		"view_types": "tree,list",
		"view_settings": json.dumps({
			"tree": {"parent_field": "parent_cost_center",
			         "label_field": "cost_center_name"},
		}),
	},

	# ----- Raised elsewhere ----------------------------------------------- #
	#
	# Three screens this space reads and does not write, and the heading says
	# so rather than leaving somebody to work it out from a missing New button.
	# Every one of them is a liability the moment the other space approves it,
	# and a bookkeeper who cannot see it is a bookkeeper who finds out about
	# the payroll on the day it clears.
	{
		# The payslip, from the paying side. `record: payslip` is OnePeople's
		# record view and this is the second screen to use it — which is the
		# stage-6 argument landing: a payslip is a payslip whichever rail it
		# was opened from, and the alternative was a ninth bespoke page.
		"screen": "payroll", "label": "Payroll", "singular": "Payslip",
		"screen_group": "Raised elsewhere",
		"icon": "lucide-hand-coins", "document_type": "Salary Slip",
		"fields": "employee_name,start_date,end_date,gross_pay,"
		          "total_deduction,net_pay,status",
		"order_by": "start_date desc",
		"hide_new": 1,
		"view_types": "list,report,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"record": {"as": "payslip"},
			"dashboard": {
				"period_field": "start_date",
				"widgets": [
					{"kind": "number", "label": "Payslips", "width": 3},
					{"kind": "number", "label": "Gross", "aggregate": "sum",
					 "field": "gross_pay", "width": 3},
					{"kind": "number", "label": "Deductions", "aggregate": "sum",
					 "field": "total_deduction", "width": 3},
					{"kind": "number", "label": "Net", "aggregate": "sum",
					 "field": "net_pay", "width": 3},
					{"kind": "line", "label": "Net by month",
					 "group_by": "start_date", "grain": "month",
					 "aggregate": "sum", "field": "net_pay", "width": 12},
				],
			},
		}),
	},
	{
		"screen": "runs", "hide_in_nav": 1, "label": "Payroll runs",
		"singular": "Payroll run", "screen_group": "Raised elsewhere",
		"icon": "lucide-calendar", "document_type": "Payroll Entry",
		"fields": "posting_date,payroll_frequency,start_date,end_date,status",
		"order_by": "start_date desc",
		"hide_new": 1,
		"view_types": "list",
		"status_field": "status",
	},
	{
		"screen": "claims", "label": "Expense claims", "singular": "Claim",
		"screen_group": "Raised elsewhere",
		"icon": "lucide-receipt", "document_type": "Expense Claim",
		"fields": "employee_name,posting_date,project,total_claimed_amount,"
		          "total_sanctioned_amount,status",
		"order_by": "posting_date desc",
		"hide_new": 1,
		"view_types": "list,report,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"dashboard": {
				"period_field": "posting_date",
				"widgets": [
					{"kind": "number", "label": "Claims", "width": 4},
					{"kind": "number", "label": "Claimed", "aggregate": "sum",
					 "field": "total_claimed_amount", "width": 4},
					{"kind": "number", "label": "Sanctioned", "aggregate": "sum",
					 "field": "total_sanctioned_amount", "width": 4},
					{"kind": "donut", "label": "Where each one stands",
					 "group_by": "status", "width": 12},
				],
			},
		}),
	},

	# ----- Opening and closing -------------------------------------------- #
	#
	# The two ends of a set of books, and `docs/ONEBOOK.md` §2 is the argument:
	# a workspace arriving from another system has a trial balance on the day
	# it leaves and nothing here took it, and a workspace reaching the end of a
	# year has to move its profit to retained earnings and stop people posting
	# into the year it just closed. ERPNext has all four documents. None of
	# them had a door.
	#
	# Its own heading rather than Setup, because none of these is a setting.
	# Each is a thing somebody does once, on a date, and which every number on
	# every statement is downstream of — which is also why all four sit one
	# rung above the bookkeeper who reads those statements daily.
	{
		# The opening trial balance, as the one document that can carry it: a
		# journal whose debits are what you owned on the day and whose credits
		# are what you owed. `is_opening` is what keeps it out of the profit
		# and loss, and `Opening Entry` is what ERPNext's own statements read
		# to decide that a balance was brought forward rather than earned.
		#
		# Narrowed to those rather than being a second Journals screen, and the
		# New button starts a record the screen will actually show — the two
		# values are `view_settings.create`, checked against these columns on
		# the way in.
		"screen": "opening-journal", "label": "Opening balances",
		"singular": "Opening entry", "screen_group": "Opening and closing",
		"icon": "lucide-book-open", "document_type": "Journal Entry",
		"fields": "title,voucher_type,is_opening,posting_date,total_debit,"
		          "user_remark",
		"filters": json.dumps({"is_opening": "Yes"}),
		"order_by": "posting_date desc",
		"view_types": "list,report",
		"view_settings": json.dumps({
			"create": {"values": {"is_opening": "Yes",
			                      "voucher_type": "Opening Entry"}},
		}),
	},
	{
		# And the other half of arriving: who owed what on the day. A single
		# opening journal says "receivables were this much"; this says which
		# customer each part of it was, which is what somebody has to have
		# before they can chase any of it.
		#
		# A Single, so it is the engine's Single page — `onespace/singles.py`
		# — with ERPNext's own `make_invoices` behind the button. That method
		# is the reason this is a door rather than a screen we wrote: it fills
		# in the Temporary Opening account, the party type, the quantity and
		# the dates, creates a missing party where the page said to, scopes
		# each invoice to its own savepoint so one bad row does not undo the
		# forty before it, and enqueues past fifty rows.
		#
		# The cuts from its form are the usual kind: `cost_center` and
		# `project` are on it and are left off, because an opening balance
		# belongs to the company rather than to a cost centre — ERPNext falls
		# back to the Company default, which is the right answer and the one
		# nobody has to think about.
		"screen": "opening-invoices", "label": "Opening invoices",
		"singular": "Invoice", "screen_group": "Opening and closing",
		"icon": "lucide-file-text",
		"document_type": "Opening Invoice Creation Tool",
		"component": "single",
		"fields": "company,invoice_type,create_missing_party,invoices",
	},
	{
		# Closing a period, which is the lock: a date range after which
		# everything below this heading refuses to post. `closed_documents` is
		# the actual mechanism and it is on the record's own form rather than
		# in these columns, because a list of doctypes is not a column.
		"screen": "periods", "label": "Accounting periods", "singular": "Period",
		"screen_group": "Opening and closing",
		"icon": "lucide-lock", "document_type": "Accounting Period",
		"fields": "period_name,start_date,end_date,company,disabled",
		"order_by": "start_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "start_date", "end_field": "end_date"},
		}),
	},
	{
		# And closing a year, which is the other thing entirely: the entry that
		# empties every income and expense account into retained earnings, so
		# that the balance sheet on the first day of the next year opens with
		# last year's profit in equity and a profit and loss that starts at
		# nought.
		#
		# Submittable, and the one screen in this space where that matters
		# most: ERPNext posts the closing GL entries on submit and reverses
		# them on cancel, which is what makes "we closed the year too early"
		# recoverable. `gle_processing_status` is a column because the posting
		# is enqueued on a large chart and "Completed" is the only word that
		# says the year is actually closed.
		"screen": "closings", "label": "Year end", "singular": "Closing",
		"screen_group": "Opening and closing",
		"icon": "lucide-circle-check",
		"document_type": "Period Closing Voucher",
		"fields": "fiscal_year,company,period_start_date,period_end_date,"
		          "closing_account_head,gle_processing_status",
		"order_by": "period_end_date desc",
		"view_types": "list",
		"status_field": "gle_processing_status",
	},

	# ----- The shape of the books ----------------------------------------- #
	#
	# Everything on this heading is an Admin grant and everything on it is
	# changed about twice a year — the shape the documents above are posted
	# into, rather than anything posted.
	{
		"screen": "years", "label": "Fiscal years", "singular": "Year",
		"screen_group": "Setup",
		"icon": "lucide-calendar", "document_type": "Fiscal Year",
		"fields": "year,year_start_date,year_end_date,is_short_year,disabled",
		"order_by": "year_start_date desc",
		"view_types": "list",
	},
	{
		"screen": "payment-modes", "hide_in_nav": 1, "label": "Payment modes",
		"singular": "Mode", "screen_group": "Setup",
		"icon": "lucide-credit-card", "document_type": "Mode of Payment",
		"fields": "mode_of_payment,type,enabled",
		"order_by": "mode_of_payment asc",
		"view_types": "list",
	},
	{
		"screen": "terms", "hide_in_nav": 1, "label": "Payment terms",
		"singular": "Template", "screen_group": "Setup",
		"icon": "lucide-clock", "document_type": "Payment Terms Template",
		"fields": "template_name,allocate_payment_based_on_payment_terms",
		"order_by": "template_name asc",
		"view_types": "list",
	},
	{
		"screen": "sales-taxes", "hide_in_nav": 1, "label": "Sales taxes",
		"singular": "Template", "screen_group": "Setup",
		"icon": "lucide-percent",
		"document_type": "Sales Taxes and Charges Template",
		"fields": "title,company,is_default,disabled",
		"order_by": "title asc",
		"view_types": "list",
	},
	{
		"screen": "purchase-taxes", "hide_in_nav": 1, "label": "Purchase taxes",
		"singular": "Template", "screen_group": "Setup",
		"icon": "lucide-percent",
		"document_type": "Purchase Taxes and Charges Template",
		"fields": "title,company,is_default,disabled",
		"order_by": "title asc",
		"view_types": "list",
	},
	{
		# Under Setup rather than ungrouped, which is the other spaces' shape
		# and is also the rule the rail keeps: a heading is drawn when the
		# group *changes*, so an ungrouped screen after six groups reopens the
		# blank heading `home` already used.
		"screen": "configuration", "label": "Configuration",
		"singular": "Table", "screen_group": "Setup",
		"icon": "lucide-wrench",
		"component": "configuration",
		"view_settings": json.dumps({"configuration": {"screens": [
			"payment-modes", "terms", "sales-taxes", "purchase-taxes",
			"bank-accounts",
		]}}),
	},
]
