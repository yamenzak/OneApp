"""ERPNext, and what this product does to it.

`docs/ERP-SPACES.md` is the argument for building over ERPNext rather than
beside it: a project, a task, a timesheet, a general ledger and a customer are
solved problems, and a second copy of any of them is a schema a workspace has
to keep in step with the first. Three spaces — OneProject, OneCRM, OneBook —
own no doctypes at all for that reason, and OneHR owns none either.

What follows is the price of that, itemised. It is short, and the shortness is
the point: four controllers, eight hooks, twelve tables carrying a column of
ours, and five functions we call rather than re-solve.
"""

APP = "erpnext"
NAME = "ERPNext"

#: Their doctype, our controller. One, and it carries fields their
#: schema has no notion of, written on save.
SUBCLASSED = {
}

# Not `Employee`, and it is worth saying why here rather than leaving it to be
# proposed again. OneHR is thirty screens over HRMS and reaches Employee
# through fields and permlevels only — `docs/ERP-SPACES.md` §5. A controller
# there would be behaviour on the one doctype three spaces read.

#: Their doctype, our handler beside theirs. Additive, so the failure mode is
#: ours breaking their save rather than their behaviour going missing.
HOOKED = {
	"Sales Invoice": "Two. `onespace/retention.py` applies the part of an "
	                 "invoice a construction customer keeps until the job is "
	                 "proved; `onebook/origin.py` stamps which space raised "
	                 "it.",
	"Purchase Invoice": "`onebook/origin.py` — which space raised it.",
	"Payment Entry": "`onebook/origin.py` — which space raised it.",
	"Journal Entry": "`onebook/origin.py`. The one where it earns its keep: a "
	                 "payroll run's bank entry is a Journal Entry with an "
	                 "account row referencing the run, and nothing on the "
	                 "list said so.",
}

#: Their tables carrying a column of ours. Declared in the space manifests —
#: `oneapp_control/spaces/*.py` — and applied by the tenant seeder, so this is
#: a read-back rather than a second list: `tests/test_adapters.py` assembles
#: the manifests and holds them to this.
#:
#: Each says which space asked for it, because that is the question somebody
#: has when they find a `custom_` column they did not expect.
EXTENDED = {
	"Employee": "RUA.",
	"Journal Entry": "OneBook — `custom_origin`.",
	"Payment Entry": "OneBook — `custom_origin`.",
	"Project": "OneProject — health and a manager. RUA — its own stage.",
	"Purchase Invoice": "OneBook — `custom_origin`.",
	"Purchase Order": "RUA.",
	"Quotation": "RUA.",
	"Quotation Item": "RUA.",
	"Sales Invoice": "OneBook — `custom_origin`. RUA — retention.",
	"Task": "OneProject — the state, the cycle, the labels and the rank "
	        "(`docs/WORK.md` §12).",
}

#: Their functions we call rather than re-solve. Five, and each is a thing it
#: would be wrong to write ourselves.
CALLED = {
	"erpnext.setup.setup_wizard.setup_wizard.setup_complete":
		"The setup wizard's last step, called programmatically. The desk is "
		"not part of this product, so on a One workspace that wizard is "
		"never run — and until it is there is no Company, no Fiscal Year and "
		"no chart of accounts. Reimplementing it would be a second copy of a "
		"hundred fixtures to keep in step. `onespace/books.py`.",
	"erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts"
	".get_charts_for_country":
		"Which charts of accounts a country may pick from. The same list the "
		"wizard offers. `onespace/books.py`.",
	# The three statements, called rather than copied — `docs/ONEBOOK.md` §1.
	# Each carries the sign convention per root type, the chart's tree order,
	# period columns built from a fiscal year and a periodicity, accumulated
	# values, presentation currency and the closing-entry handling that decides
	# whether an opening balance is one. A second implementation of any of them
	# is a second answer to "what did we earn".
	"erpnext.accounts.report.trial_balance.trial_balance":
		"The trial balance, behind OneBook's screen of the same name. "
		"`onebook/statements.py`.",
	"erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement":
		"The profit and loss. `onebook/statements.py`.",
	"erpnext.accounts.report.balance_sheet.balance_sheet":
		"The balance sheet. `onebook/statements.py`.",
	# The two ageings — `docs/ONEBOOK.md` §4. What is not ours to own twice is
	# the bucketing: whether a document ages from its due date or its posting
	# date, what a credit note against an earlier month does to it, how a part
	# payment is apportioned across the buckets, and which ledger a partly
	# settled advance belongs in. All of it runs off the Payment Ledger rather
	# than off the invoices.
	"erpnext.accounts.report.accounts_receivable.accounts_receivable":
		"What is owed to us, aged. `onebook/owing.py`.",
	"erpnext.accounts.report.accounts_payable.accounts_payable":
		"What we owe, aged. The same report against the other side. "
		"`onebook/owing.py`.",
	# And the opening-balance importer, behind OneBook's Opening invoices page
	# — `docs/ONEBOOK.md` §2. Reached through the engine's Single page, which
	# names the method in `onespace/singles.py` and nowhere else. It fills in
	# the Temporary Opening account, the party type, the quantity and the
	# dates, creates a missing party where the page said to, scopes each
	# invoice to its own savepoint so one bad row does not undo the forty
	# before it, and enqueues past fifty rows.
	"erpnext.accounts.doctype.opening_invoice_creation_tool"
	".opening_invoice_creation_tool.OpeningInvoiceCreationTool.make_invoices":
		"One opening invoice per party, against the Temporary Opening "
		"account. `onespace/singles.py`.",
	# The bank reconciliation, called rather than copied — `docs/ONEBOOK.md`
	# §3. The ranking is the product: one query per document type, each
	# counting how many of the amount, the reference and the party agree, with
	# a sign convention per direction and `subtract_allocations` on top. A
	# second opinion about which payment a bank line is would be exactly the
	# wrong thing to own.
	"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool"
	".get_bank_transactions":
		"The statement lines for one bank account, unreconciled or all. "
		"`onebook/reconcile.py`.",
	"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool"
	".get_account_balance":
		"What the books say is in a bank account as the bank would see it — "
		"the balance less what has not cleared. `onebook/reconcile.py`.",
	"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool"
	".get_linked_payments":
		"What a bank line could be, ranked. `onebook/reconcile.py`.",
	"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool"
	".reconcile_vouchers":
		"Tie a bank line to the documents it is: allocate, set the clearance "
		"date on each, move the line's status. `onebook/reconcile.py`.",
	# The two steps of the selling chain — `docs/ONEBOOK.md` §5. Both are
	# `get_mapped_doc` definitions: a field map per doctype, a per-row
	# condition that skips what is already fulfilled, and a postprocess that
	# reprices against today's rate and recalculates the taxes. Rewriting
	# either would be rewriting "what carries forward from a quote to an
	# order", which has twenty answers in it and no interesting ones.
	"erpnext.selling.doctype.quotation.mapper.make_sales_order":
		"A quotation, accepted. `onebook/orders.py`.",
	"erpnext.selling.doctype.sales_order.mapper.make_sales_invoice":
		"What is left of an order, invoiced — their mapper takes off what has "
		"already been billed, row by row. `onebook/orders.py`.",
	# And the party side of the same question, driven rather than drawn.
	"erpnext.accounts.party.get_party_account":
		"A party's receivable or payable account, which is the one filter "
		"`Payment Reconciliation` cannot work out for itself. "
		"`onebook/reconcile.py`.",
	"erpnext.crm.doctype.opportunity.opportunity.Opportunity":
		"The base class the deal subclasses.",
	"erpnext.crm.doctype.lead.lead.Lead":
		"The base class the lead subclasses.",
	"erpnext.projects.doctype.task.task.Task":
		"The base class the project task subclasses.",
}
