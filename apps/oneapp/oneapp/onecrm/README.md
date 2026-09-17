# OneCRM

Leads, deals, quotations and what happens next on each — over ERPNext's own
sales schema, with the four things a desk needs that ERPNext does not have.

Who opens it: whoever sells. Which in a plumber is the owner, in a ministry is
a procurement officer, and in a sales team is a rep with a manager over them —
and the schema has to serve all three, which is most of why this is not
`frappe/crm`.

`docs/ONECRM.md` is the study: what Frappe CRM gets right that we did not, why
their schema is the wrong shape for a product that has to serve a plumber and a
ministry as well as a sales team, and the seven stages. This file is the
module.

## The one decision everything follows from

**The sales schema is ERPNext's.** A `Lead` is theirs, an `Opportunity` is the
deal, a `Quotation` is the quotation and a `Customer` is what a won deal
becomes. `Deal` and `Lead` here are `override_doctype_class` subclasses, not
tables.

That is the same rule OnePeople and OneProject follow, and it is what makes a
won deal reach accounting without a bridge: a Quotation becomes a Sales Order
becomes an Invoice, all of it ERPNext's, none of it ours.

What this module owns is the four things a desk needs that ERPNext has no noun
for: **a stage that is a row**, **a log of where a deal has been**, **a call as
a record**, and **a promise about answering, measured**.

## The decisions that cost something

**A stage is a row, not a word.** ERPNext's `Opportunity.sales_stage` is a
Link, and `One Deal Stage` replaces the list behind it with one a workspace
owns: a name, a `category` mapping onto ERPNext's own vocabulary, a
`probability`, a colour and a position. A team selling scaffolding and a team
selling software do not have the same pipeline and should not be asked to
pretend.

The rule the space is most emphatic about is the grant that follows: **Read for
a User and Write for a Manager**. A rep who can invent a stage can move a deal
into one, and the forecast quietly stops meaning anything.

**Where a deal has been is a log, and the log is not editable.** `One Stage
Change` records entering and leaving with the days between, written by
`progress.log_the_move` on validate. `stage` on it is `Data` and **not** a Link
— a log records what a value *was*, and a Link that can be renamed or deleted
makes history mutable.

Capped at 100 rows. A deal that has been round the houses two hundred times is
a deal whose first fifty moves nobody will read.

**A call is a record, not a comment.** `One Call` has a person, a direction, a
number, a time, minutes and an outcome, because "did anybody ring them back" is
a question a desk asks constantly and a note in a timeline cannot answer it.

Manage rather than Write, and not `if_owner`: a call log whose rows a rep
cannot correct is a call log they stop writing, and a desk where you cannot see
that a colleague already rang this person rings them twice.

**Answering is measured against a target, and the target is the whole feature.**
`One Response Target` is an SLA: which records it covers (`applies_when`,
compiled rules rather than eval), a working week, a holiday list, and a level
per priority saying how long there is to respond and to resolve.

`rolling` is the half that is easy to get wrong. A conversation is not one
question: a customer replies and the clock starts again. So an answer stops it
and a reply from their side restarts it, and `custom_rounds` counts how many
times.

**`position` is written from the declared order.** Every target seeded at the
same position sorted by name, so "Answer a lead" beat "Answer a web lead" and
the narrow target could never win. Found by reading rows back, not by a test.

**The party is not a company.** `docs/ONECRM.md` stage 7: a product that has to
serve a plumber and a ministry cannot assume the other side of a deal is an
organisation with a registered name. The workspace's own word for a screen is
`OneSpace Word`, and a space that calls Deals *Donations* changes what every
colleague reads.

## What is not built

1. **A forecast that is not a sum.** `probability` on a stage times the amount
   is what the widget draws, and a weighted sum is not a forecast — it is an
   arithmetic identity that looks like one.
2. **Sequences.** A cadence of touches over days, which is what a sales desk
   buys a CRM for and is a scheduler plus a template plus an opt-out.
3. **A target per customer.** One set of targets for the workspace. A
   contract-level SLA is `applies_when` over a field nothing writes yet.
