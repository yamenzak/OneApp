# OneCRM — Frappe CRM, read against ours

OneCRM already exists: eight screens over ERPNext's CRM module, two roles, and
two fields ERPNext was missing. `docs/ERP-SPACES.md` §4 is what it is and why.
This document is the next arc, and it starts from somebody else's app.

**Frappe CRM** (`frappe/crm`) is the closest thing in the ecosystem to the
product OneCRM wants to be: a sales desk somebody actually enjoys opening,
built on the same framework, by the people who wrote the framework. It is worth
reading the way `docs/HORILLA.md` reads Horilla — not for code to copy wholesale
but for the decisions it got right that we have not made yet, and the ones it
got wrong for us.

It is **AGPL-3.0**, like this repository. So unlike Horilla, code may actually
be taken — `CLAUDE.md` names `frappe/crm` explicitly — and taking it carries
three obligations that are not optional: keep Frappe's copyright notice, say at
the top of the file what it was derived from, and never move that file to a
permissive licence.

---

## 1. The rule, restated

OneCRM is ERPNext's CRM module the way OnePeople is Frappe HR and OneProject is
ERPNext's Projects. Their `Lead` is the lead, their `Opportunity` is the deal,
their `Quotation` is the quote, their `Customer` is the other side of a won one.
Ours is the presentation and the handful of things their schema cannot say.

That rule already held when the space was built. Nothing below changes it, and
one section of this document exists to say why reading Frappe CRM *strengthens*
it rather than weakening it: their schema is a second CRM beside ERPNext's, with
a bridge (`ERPNext CRM Settings`) to keep the two in step. We have seen where
that ends — `docs/WORK.md` §12 is twelve stages of unwinding exactly this shape
in OneProject — and we are not doing it again.

**Generally available, and that is the sharpest difference.** Every app in this
product has to work for a plumber, a law firm, a ministry and a shop. Frappe CRM
does not: it is B2B by construction, in ways that are structural rather than
cosmetic, and §4 is the measurement.

---

## 2. What Frappe CRM is, measured

Forty-eight doctypes, a Vue front end of its own, and five integrations. The
part that matters is small and is mostly *not* schema.

**The record page** is the whole product. A lead or a deal opens as one page:
a header with the name and the owner, a side panel of fields somebody can
rearrange, and a tabbed middle holding **Activity, Emails, Comments, Data
(field changes), Calls, Tasks, Notes, Attachments** — with Activity being all of
them merged in one column. Everything a salesperson does to a record happens
there and nothing navigates away. It is very good, and it is the thing to take.

**Statuses are rows, not a Select.** `CRM Lead Status` and `CRM Deal Status`
each carry a name, a **colour**, a **position** and a **type** — one of Open,
Ongoing, On Hold, Won, Lost. A deal status also carries a **probability**, which
it writes onto the deal when the deal moves. So a team names its own columns,
the board draws them in the team's order, and the engine still knows which
column means *won* without reading the word somebody chose.

That is the same move `One Task State` is in OneProject — `docs/WORK.md` §12 —
and arriving at it twice independently is the strongest argument there is for
it.

**A status change log.** `CRM Status Change Log` is a child table on the lead
and the deal: from, to, the two datetimes, and the **duration**. Written on
every status change. It is how a pipeline review answers "this has been sitting
in Negotiation for forty days", which is the question a pipeline review is for,
and neither ERPNext nor OneCRM can answer it at all.

**Service levels.** `CRM Service Level Agreement` is 359 lines and the best-built
thing in the app: a condition deciding which records it applies to, priorities
with a first-response target, working hours per weekday, a holiday list, and —
the good part — **rolling responses**, so an SLA is not only about the first
reply but about every reply after it. It writes `response_by`, `sla_status`,
`first_responded_on` and `first_response_time` onto the record.

**Telephony.** Twilio and Exotel, both built in, both writing a `CRM Call Log`
with a recording URL, a duration and a link back to the record. `telephony_medium`
includes **Manual**, which is the part that needs no integration at all.

**And the rest**, briefly: WhatsApp through a third-party app; domain enrichment
that calls an external service to fill an organisation from its website;
Facebook lead-form syncing; a dashboard with forecast-versus-actual and average
time-to-close; per-user saved views with kanban settings; a field-layout editor;
form scripts, which are arbitrary JavaScript stored in a doctype.

---

## 3. What they get right that we do not

Three things, in the order they are worth doing.

### The record is the workspace, and the timeline is everything at once

Ours has a timeline — `RecordActivity.vue` — and it merges exactly three kinds:
a comment, a field change, and the creation. Mail is a different tab, files are
a different tab, and a call has nowhere to be at all. Theirs merges emails,
calls, comments, field changes, notes, tasks and attachments into one column,
and the answer to "what happened on this deal" is one scroll.

The gap is not the tabs. It is that **we cannot answer the question in one
place**, and on a sales desk that question is the job.

### A deal inherits the lead's history

`get_deal_activities` starts by fetching the lead's activities and prepending
them, so a deal converted last month still shows the first email that started
it. ERPNext links `Opportunity.party_name` back to the Lead and shows nothing
of it. Losing the history at the moment of conversion is the same complaint
`docs/ERP-SPACES.md` §4 already makes about losing the next step.

### The status change log

Covered above. It is twenty lines of controller and it is the only way to see
where a pipeline is stuck.

---

## 4. Where Frappe CRM is the wrong shape for us

This is the part the brief is emphatic about, and it is not a matter of
wording: **Frappe CRM is organisation-first in its schema.**

* `CRM Deal`'s **title field is `organization`**. A deal with a private person
  has no title.
* A deal *has* an `organization` Link and a `contacts` child table. The
  organisation is the spine; people hang off it.
* `CRM Lead` carries `no_of_employees`, `annual_revenue`, `industry`,
  `website`, `linkedin`, `twitter`, `facebook` and `company_description` — nine
  fields about a company, on the record that is supposed to be a person.
* Enrichment is "fill this in from the company's website domain", which is not
  a thing a private customer or a government department has.

ERPNext's model is better for a general product, and this is the one place
where "unglamorous" wins outright. **`Opportunity.opportunity_from` is a Link to
DocType and `party_name` is a Dynamic Link against it**, so a deal is with a
Lead, a Customer or a Prospect — a person, a company, a public body, whatever
the workspace deals with. `Customer.customer_type` is Individual or Company.
`Lead` carries `lead_name` *and* `company_name` as separate fields, and neither
is required.

So: we take their **presentation** and keep our **party**. Concretely, nothing
in OneCRM may assume there is a company. The record header says the party and
what kind of party it is; the organisation fields appear when there is an
organisation and are not a hole in the page when there is not; and no screen is
called Organisations in a workspace that sells to people.

Two smaller ones, for the same reason:

* **"Deal" and "Lead" are the house words of one industry.** They are the right
  default and they should be renameable per workspace, the way a space is
  already renameable. A charity has donors and a clinic has referrals.
* **Sales hierarchy.** Theirs is a tree of users with `reports_to` for "my
  team's pipeline". ERPNext already has `Sales Person` as a tree, and OnePeople
  already has `Employee.reports_to`. A third tree is the thing this repository
  keeps refusing.

---

## 5. What is ours to add, and what to leave

**Take, as ideas and in places as code:**

| Theirs | Ours | Why |
| --- | --- | --- |
| `CRM Deal Status` / `CRM Lead Status` | `One Deal Stage`, a row with colour, position, category and probability | `Sales Stage` has a name and nothing else; `status` is a fixed Select. Same move as `One Task State`. |
| `CRM Status Change Log` | `One Stage Change`, a child table on Lead and Opportunity | Where a pipeline is stuck, which nothing else answers |
| `CRM Service Level Agreement` | `One Response Target`, narrower | A lead nobody answered in two days is lost whether it is a person or a ministry |
| `CRM Call Log` | `One Call`, manual first | A call is the commonest thing on a sales desk and has nowhere to live |
| The all-in-one record page | The record shell we already have, with the timeline widened | The question "what happened here" should be one scroll |
| Deal inherits the lead's timeline | The same, over `party_name` | History should survive conversion |

**Leave, and say why:**

* **Domain enrichment.** It calls a paid third party and it only works for
  companies with websites. A workspace that wants it can have it as an app.
* **Facebook lead forms.** One channel of one vendor. The general shape — a
  form that pushes leads in — belongs to OneForms when that exists.
* **WhatsApp.** Depends on a third-party app we do not ship. Worth revisiting
  when OneMail's channel story is settled — `docs/EMAIL.md`.
* **Form scripts.** Arbitrary JavaScript stored in a row and run in every
  reader's browser. Whatever it buys, it is not worth that.
* **Their fields-layout editor.** We have manifests and saved views, and a
  second customisation surface with its own storage is `docs/UNIFICATION.md`'s
  whole complaint.
* **Their dashboard.** Ours is declared per screen and measured over exactly the
  rows the screen is showing, which is better. What is worth taking is two
  *measures*: average time to close, and forecast against actual.

---

## 6. The stages

Each stage is a commit, ends somewhere a person can look, and does not depend on
the one after it.

**1. The stages become rows.** `One Deal Stage` — name, colour, position,
category, probability — with `custom_stage` on Opportunity, the category
writing ERPNext's own `status`, and the board drawn from the rows rather than
from the manifest's declared order. *Checkpoint: a workspace renames a column
on the pipeline and the board, the badge and the forecast all follow.*

> **Landed, and narrower than this said.** There is no `One Lead Stage`: a lead
> already has `qualification_status`, three values in a sensible order, and
> OneCRM's board was already drawn by it. A third status would be the thing
> `docs/WORK.md` §12 forbids.
>
> It went wider in one place instead, because the same gap turned out to be the
> engine's rather than the space's. A board over a **Link** drew only the values
> present on the page, so an empty column did not exist — and the whole use of a
> board is moving a card into one. `view_settings.board.columns_from` is a
> screen saying the rows of the table it links to *are* the columns, in that
> table's own order; `views._columns_from` reads them, permission-checked, and
> falls back to what it always did for a reader who may not read that table.
> OneProject's boards moved onto it in the same commit and dropped their
> declared `STATE_ORDER`, which closes the "per-project columns" item
> `onetask/README.md` §4 has been carrying since stage 5.

**2. Where a deal is stuck.** `One Stage Change` on both, written on save, and
a "days in stage" column the pipeline can be sorted by. *Checkpoint: a board
card says how long it has sat there, and the list sorts by it.*

> **Landed, on the deal only and with the column a date.** A lead's stage is
> `qualification_status`, three values in a sensible order that OneCRM's board
> was already drawn by; a second log against a Select would be the second
> status §12 of `docs/WORK.md` forbids.
>
> And the sortable half is `custom_stage_since`, a Datetime, rather than a day
> count. A number would be wrong by one every midnight and would need a
> nightly job to be right; sorted ascending a date is the same list, and the
> record shows the elapsed time from it. The log itself is one row per stage
> *entered* rather than one per transition — the same information, and "New,
> 7 days · Qualifying, 21 days · Proposal, still here" is a history somebody
> can scan where from/to pairs are a diff nobody reads.

**3. The timeline is everything at once.** Mail, calls, notes and attachments
join comments and field changes in `RecordActivity`, filtered by kind, with the
server merging them the way `onecalendar/diary.py` merges a week. *Checkpoint:
one scroll answers what happened on a deal.*

> **Landed, with the sources a registry and two of the four left out.** Mail
> and attachments joined; a **call** has no doctype until stage 5 and joins by
> adding one line to `surround.SOURCES` when it does, which is the whole
> reason the sources are a list rather than four queries in a row.
>
> **Notes did not, and will not.** A comment already is one. ERPNext's `notes`
> child table on Lead and Opportunity is a second store for the same sentence,
> and a surface that showed both would be `docs/UNIFICATION.md`'s complaint
> written out.
>
> The merge is the server's because every source is a read under the reader's
> own permissions — a record is not a key that unlocks the mail about it, and
> the browser cannot enforce that. The filter row is built from what is
> actually in the column, so a record with no mail is not offered a Mail filter
> that answers nothing.

**4. A deal remembers where it came from.** The lead's timeline prepended to the
deal's, through `party_name`, with the conversion itself as an entry.
*Checkpoint: a converted deal shows the first email that started it.*

> **Landed as a declaration rather than a rule about deals.** A screen says
> `view_settings.timeline.inherits` and names the field it was converted from;
> everything else is the engine's. That matters because `party_name` is a
> **Dynamic Link** — a deal may have come from a Lead, a Customer or a Prospect
> — so only the record knows which doctype is on the other end, and a rule
> hard-coded to Lead would have been wrong for two of the three.
>
> One hop, because two is a history and three is an ancestry. The far record's
> entries are read through its *own* screen's rules, so a field that screen
> hides is not a change this reader is shown, and the reader's permission on
> the far end decides: somebody holding the deal and not the lead gets a
> shorter column, not a refusal and not a disclosure. And the creation entry
> says *converted* rather than *created* when there is something on the other
> end — a deal claiming to have been created above six weeks of somebody
> else's email is a deal lying about its own history.

**5. A call is a record.** `One Call` — who, which way, when, how long, what was
said, and what it was about — logged by hand from the record and from the
applet. *Checkpoint: ring somebody, log it in two presses, and see it on the
deal and in the week.*

> **Landed, and it is about anything.** `about_doctype`/`about_name` is a
> dynamic pair, so a call about a job, a tenant, a patient or a supplier is the
> same row — `onecrm/calls.py` lives in this module because selling is where
> somebody asked for it first, and nothing in it is about selling. What was
> taken from Frappe CRM is the idea rather than the integration: their
> `CRM Call Log` carries a `telephony_medium` of **Manual**, because most of
> the value of a call log is having one at all, and a log that only fills in
> when a Twilio account is paid for is a log that is empty on every desk that
> matters.
>
> **The verb writes nothing.** "Log a call" answers `{"create": …}` and the
> engine opens the Calls screen's own New dialog with the record, the time, the
> person and whatever number that doctype was carrying already in it. So it is
> two presses, and the permission to log a call is still the screen's — a
> button that inserted on the reader's behalf would be a second create path
> around it.
>
> **Who was on the other end is read generically.** A candidate list of
> fieldnames tried in order against whatever doctype the button was pressed on,
> rather than a map from doctype to field: an Opportunity keeps a number in
> `contact_mobile`, a Lead in `mobile_no`, and the next app to want this verb
> keeps it somewhere else again. A record with none of them opens the dialog
> with the box blank, which is what a person is about to type into anyway.
>
> And joining the timeline was the one line stage 3 promised — `SOURCES` gained
> a name. Entries are timed by `at` and not `creation`, which is the one thing
> about this source that is different: a call logged on Friday about Tuesday
> belongs on Tuesday, and it is the only kind in that column whose time a
> person types.
>
> *Not built:* a second surface in the dock. The plan said "and from the
> applet" and the applet is OneTask's — a window over ERPNext's `Task` — so
> putting a call button in it would have made it an applet over two things. The
> Calls screen's own New dialog is the second door, and the week is its
> calendar.

**6. Answering, measured.** `One Response Target`: which records, how long,
against a working week and a holiday list, writing the due time and whether it
was met. *Checkpoint: a lead that arrives on Friday evening is not late on
Saturday morning.*

> **Landed at a third of the surface, and two things were dropped on purpose.**
> `CRM Service Level Agreement` is 359 lines and the best-built thing in Frappe
> CRM. What is not taken is its **condition expression** — a Python string
> stored on the row and evaluated — because a row an operator can edit must
> never be a row an operator can run code from; this narrows by one field and
> one value, which covers "web leads" and "government deals" and refuses
> anything that would need an interpreter. And its **priority table**, which is
> a second target spelled as a nested row: a desk that answers urgent leads
> faster makes a second `One Response Target`, and that is the same thing
> written where somebody can read it.
>
> What is kept is the part everybody gets wrong. The deadline is walked forward
> through the working week a day and a window at a time, skipping the holiday
> list — ERPNext's own, so a workspace keeps one list for payroll, projects and
> this — and four working hours from six on Friday evening lands at one on
> Monday afternoon. A day has no 24:00, which is why an unstated window ends at
> midnight of the next day rather than at 23:59:59: the second spelling loses a
> second every day it crosses, and a measure that drifts is worse than one that
> is wrong.
>
> **Anything can be the answer**, and the first one is the measurement. A
> message sent through the timeline links `onemail/linking.py` already writes,
> or a call out — stage 5's doctype earning its keep twice. Mail *received* and
> calls *in* are not answers: they are the thing being waited on, and counting
> them would mean a lead that emails twice has answered itself. Never
> unstamped afterwards, because a second email is not a second chance to have
> been on time.
>
> The state is **written** rather than derived, because a list sorts by a
> column and a board groups by one — and the hourly sweep is what that costs:
> nothing saves a lead at the moment its deadline passes, so without it the
> list meant to show the problem shows nothing. It writes the column and not a
> Version row, which would bury the timeline stage 3 built.
>
> And `applies_to` is a Link to **DocType**, not a Select of two. A lead, a job,
> a ticket and a planning application are the same measurement; the doc_events
> hook is `*` and the sweep reads the doctypes the targets name, so nothing in
> this is about selling except which space shipped it first.

**7. The party is not a company.** The record header, the screens and the words:
a deal is with whoever it is with, the organisation block appears when there is
one, and the space's own nouns are renameable. *Checkpoint: a workspace that
sells to private people opens OneCRM and sees nothing about companies.*

> **Landed as two things, and the second is bigger than this space.**
>
> **The header says the party and what kind of party it is.** The deal's
> eyebrow was `customer_name`, which says nothing at all on a deal with
> somebody who is not a customer yet — which is every deal in the pipeline. It
> is now `party_name` with `opportunity_from` beside it, so the page reads
> *Lead · zzNadia Fares*. Both come from ERPNext's own pair: `party_name` is a
> Dynamic Link and `opportunity_from` says which doctype it points at, so a
> deal is with a person, a company or a public body and the header never
> assumes which. `showcase.eyebrow_kind_field` is the whole of the addition —
> one key, available to every space, because "who this is with and what sort of
> thing they are" is not a CRM question.
>
> **The nouns are a workspace's own.** `OneSpace Word` is a row saying what
> this workspace calls one of a space's screens: Deals → Donations, Leads →
> Referrals, Organisations → Households. Three decisions.
>
> It is an **overlay, not an edit**. Screens arrive from the control plane on
> every sync and are rewritten wholesale, so a label typed into an `OneSpace
> Space Screen` row would last fifteen minutes. A row of our own outlives every
> sync and every release, and it stays obvious afterwards what shipped and what
> somebody changed.
>
> It is applied in **one place**. `sync.state()` builds the space list that the
> rail, the switcher, the resolver, the breadcrumbs, the New button and the
> assistant all read, so renaming a screen is renaming it everywhere — or it is
> a rail that disagrees with the page it opens.
>
> And the **word is not the key**. `screen` stays what the address bar spells,
> so a rename changes no url, no saved view, no bookmark and no declaration.
> This renames what a person reads and nothing a machine reads.
>
> The page for it is appended by the engine to every space, the way
> `sync.configured` appends the Configuration page, and it sits as a tab on
> that page. Which turned up the one engine gap this stage needed:
> `view_settings.create` — what a New dialog starts with already in it —
> because the Words page is filtered to one space and its New button was making
> rows the page would not then show. And a guard now checks every space grants
> the table behind a tab the engine gave it; it found RUA on the first run.
>
> *Not built:* hiding ERPNext's nine company fields on a Lead that is a private
> person. They are blank rather than wrong, and a form that hides its own empty
> fields is a form you cannot fill in — the fix is a section somebody collapses,
> which is a change to how every record draws rather than to this space.

---

## 7. What this deliberately does not do

* **No second CRM schema.** No `CRM Deal` beside `Opportunity`, no bridge to
  keep two pipelines in step. `docs/WORK.md` §12 is what that costs.
* **No fork of Frappe CRM.** Where code is taken it is taken file by file, with
  the notice and the derivation line, into modules of ours.
* **No integration that needs somebody else's account** before stage 7. Manual
  first: a call log that works with a desk phone is most of the value of one
  that works with Twilio.
* **No new tree of people.** "My team's deals" is answered from what a workspace
  already has.
