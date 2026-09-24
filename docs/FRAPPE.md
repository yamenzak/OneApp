# Frappe's own doctypes, read against One

Frappe v17 `develop` ships **301 doctypes**, 107 of them child tables. This is every one of the 194 that is not a child table, and what One does with it. ERPNext and HRMS are a different question and a different count — `docs/ERP-SPACES.md` is that one.

Generated from the source rather than remembered: the manifests in `apps/oneapp_control/oneapp_control/spaces/`, the `SCREENS` in them, and every `frappe.get_doc`/`get_all`/`db.*` call under `apps/oneapp` and `apps/oneapp_control`. `tests/test_frappe_coverage.py` reads it back.

## The seven answers

| | | count |
|---|---|--:|
| **screen** | a space declares a screen over it, and somebody opens it | 4 |
| granted | a manifest grants it, but it is reached through a picker or a record field rather than a screen | 5 |
| service | the SPA reads or writes it by name — no grant, no screen, no choice for a customer | 35 |
| engine | the engine itself runs on it, and `NEVER_GRANTED` refuses to let any space hand it out | 8 |
| refused | `NEVER_GRANTED` and nothing else uses it | 10 |
| log | named exactly once, to be left out of a restore, a quota or what OneAI may write | 9 |
| — | untouched | 123 |

So **52 of 194** are reachable from the product in some form, and 4 of those are a screen. The rest is the desk, the portal, and the platform's own bookkeeping.

## What is missing

The 123 untouched rows are mostly the desk and the portal, and those are gone
on purpose. Ten of them were not: the framework has the mechanism, we do not
have the product over it, and nothing else in this repository answers the
question instead. In the order a customer would meet them. Three are struck
through now, and all three are left here rather than deleted: the first because
what it assumed turned out to be wrong, the second because it over-estimated
the work by most of it, the third because only half of it is done.

**~~There is no global search.~~** Built — Ctrl+K, `onespace/finding.py` and
`components/shell/Finder.vue` — and not the way this paragraph assumed. It
said the index was already being written and the measurement says otherwise:
`__global_search` on the dev site is 1,348 rows of which 1,022 are `DocType`,
223 are `Report` and 55 are `Module Def`. It is the desk's own metadata. Two
things would still have been wrong with it if it were full: `MATCH … AGAINST`
in natural-language mode matches whole words, so `Meri` does not find
`Meridian`; and a hit is a doctype and an id with no idea which *screen* shows
it, which here is the difference between a search result and a row nobody can
open. So the screens are searched instead — one `like` per screen the reader
can open, 68 ms across all 146 the shipped manifests name — and going somewhere
needs no server at all, because the session payload is already the rail.

**~~Nothing is public.~~** Built — `docs/ONEFORMS.md`, seven stages, over
Frappe's own `Web Form`. The paragraph was right that dropping the website
builder took the forms with it and wrong about how much would have to be
written: v17's `Web Form` already had `anonymous`, `key_required` with a
`Web Form Request` per recipient, `show_list` scoped to one person's own
records, and `allow_edit`. What was missing was a builder, a page in this
product's look, and a way to send one — and the rest of the `Website` module is
still out, because a form has a URL and is not a site.

**A workflow can be honoured but not built.** Half struck. `docflow.py` drives
Frappe's engine properly — `get_workflow`, `apply_workflow`, `allow_edit` per
state — and `docstate.py` offers the transitions on the record. ~~`Workflow
Action`, the approvals inbox, is written beneath us and read by nobody, so
nobody has a list of what is waiting on them.~~ Built: `onespace/waiting.py`
and One's Approvals screen, which cost almost nothing because it adds nothing —
Frappe's own permission query conditions on that doctype are the scoping, and
pressing a verb calls the endpoint the record header already calls. What is
still absent is the builder: a customer cannot draw a workflow, so approval
works where an app shipped one and is unreachable where it did not.

**No SSO.** `Social Login Key`, `OAuth Client`, `OAuth Provider Settings` and
`LDAP Settings` are all out. Email and password, plus the two-factor toggle in
workspace settings, is the whole of it. A ministry buying this asks for SAML or
LDAP in the first meeting.

**No bulk mail.** `Email Group` and `Email Group Member` are Frappe's newsletter
store and nothing here sends to a list. The unsubscribe side, which is the half
that is hard, went to OneDesk's `one_mail` with the rest of mail — the sending
half is missing. OneCRM has campaigns as a field on a deal and no way to run one.

**No SMS.** Deliberate rather than forgotten — `alerts.py` says so at line 110,
and `SMS Settings` needs a gateway this platform does not run — but it is still
why an alert cannot reach somebody who is not at a screen, and why two-factor is
authenticator-only.

**No scheduled report.** `Auto Email Report` is out and nothing replaces it. A
screen can be printed and exported by the person looking at it; nothing arrives
on a Monday without somebody opening it.

**No data subject request.** `Personal Data Download Request` and `Personal Data
Deletion Request` are Frappe's DSAR machinery. `onelegal` writes the clause
promising an export and the promise is kept by hand: `spaceview/export.py`
exports a screen, and there is no "everything about this person" and no
erasure.

**Nobody is onboarded.** `Form Tour`, `Module Onboarding`, `Onboarding Step` and
`Success Action` are the desk's, and the SPA has no equivalent — a new
workspace opens on a rail of empty screens.

**No push.** `Push Notification Settings` is out and there is no service worker.
The bell is a page somebody has open. `docs/DESKTOP.md` stage 7 is the phone
answer and it is the one stage of that arc still pending.

Two smaller ones, for completeness. `Document Naming Rule` is conditional naming
— a series that depends on a field — and only `Document Naming Settings` is
wired, so a space gets one series per doctype. `Network Printer Settings` is
printing to a printer rather than to a PDF, which a counter clerk in an office
would expect.

## Automation (9)

Four of these landed in the week of 2026-09-19 and are a whole automation
engine: a flow over a doctype with a trigger field and a from/to transition, a
durable queue with attempts and a recursion depth, event subscriptions with a
correlation key and a resumable step, and a settings single with a failure
threshold and a drain window. WORK 7 built One's own automations and this is
more than it built — resumability and recursion depth in particular.

**It is not adopted yet and the rows say so**, because swapping an engine
under a shipped feature is an arc rather than a row in a table.
`docs/DESK.md` §5 is where it belongs and the borrowing guard is what will
stop it being forgotten. It is also the second thing in one hour that
upstream turned out to already have — the first was `@framework/ui` — which
is the argument for `frappe.watch` making itself.

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Assignment Rule | service | who a new record goes to |
| Auto Repeat | — | OneTask's `One Cycle` instead |
| Automation Flow | — | upstream's engine, newer than WORK 7's and not yet weighed against it — `docs/DESK.md` §5 |
| Automation Event Subscription | log | the engine's own bookkeeping, named to be excluded |
| Automation Trigger Queue | log | the engine's own bookkeeping, named to be excluded |
| Automation Settings *(single)* | — | nothing to configure until the engine above is adopted |
| Milestone | — | ERPNext's `Task.is_milestone` instead — OneProject `milestones` |
| Milestone Tracker | — | Frappe's own automation UI; One routes and repeats itself |
| Reminder | — | the bell and the diary instead |

## Contacts (5)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Address | granted | OneCRM, RUA — the party's address on the record |
| Address Template | — | reference data with no screen |
| Contact | **screen** | OneCRM `contacts` |
| Gender | **screen** | OneHR `genders` |
| Salutation | **screen** | OneHR `salutations` |

## Core (69)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| API Request Log | — | platform plumbing — logs, schema, sessions, the scheduler |
| Access Log | log | named once, only to be excluded |
| Activity Log | log | named once, only to be excluded |
| Audit Trail *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| Background Task | — | platform plumbing — logs, schema, sessions, the scheduler |
| Comment | service | the record's comment thread |
| Communication | service | every message OneMail holds |
| Custom DocPerm | engine | what the seat ladder writes |
| Custom Icon | — | platform plumbing — logs, schema, sessions, the scheduler |
| Custom Role | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| Data Export *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| Data Import | — | One has its own — `Import Plan`, `Import Run`, `Import Source` |
| Data Import Log | — | platform plumbing — logs, schema, sessions, the scheduler |
| Deleted Document | service | counted in a restore preview |
| DocShare | service | sharing a record with a colleague |
| DocType | engine | every screen is `get_meta` over one |
| DocType Layout | — | platform plumbing — logs, schema, sessions, the scheduler |
| DocType Settings Map | — | platform plumbing — logs, schema, sessions, the scheduler |
| Document Naming Rule | — | platform plumbing — logs, schema, sessions, the scheduler |
| Document Naming Settings *(single)* | service | the series a space names by |
| Document Share Key | — | platform plumbing — logs, schema, sessions, the scheduler |
| Domain | — | a tenant's custom domain is OneAdmin's, not this doctype |
| Domain Settings *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| DuckDB Sync | — | platform plumbing — logs, schema, sessions, the scheduler |
| Error Log | log | named once, only to be excluded |
| File | service | OneCloud, OneWriter and OneWorkbook are all `File` |
| Installed Applications *(single)* | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| Language | service | the language a print format renders in |
| Log Settings *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| MapReduce Job | — | platform plumbing — logs, schema, sessions, the scheduler |
| MapReduce Task | — | platform plumbing — logs, schema, sessions, the scheduler |
| Module Def | engine | a space declares one |
| Module Profile | — | platform plumbing — logs, schema, sessions, the scheduler |
| Navbar Settings *(single)* | service | where the logo is also written |
| Package | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| Package Import | — | platform plumbing — logs, schema, sessions, the scheduler |
| Package Release | — | platform plumbing — logs, schema, sessions, the scheduler |
| Page | — | platform plumbing — logs, schema, sessions, the scheduler |
| Patch Log | — | platform plumbing — logs, schema, sessions, the scheduler |
| Permission Inspector *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| Permission Log | — | platform plumbing — logs, schema, sessions, the scheduler |
| Permission Type | — | platform plumbing — logs, schema, sessions, the scheduler |
| Prepared Report | log | named once, only to be excluded |
| RQ Job | service | the queue depth OneAdmin shows |
| RQ Worker | — | platform plumbing — logs, schema, sessions, the scheduler |
| Recorder | — | platform plumbing — logs, schema, sessions, the scheduler |
| Report | — | a report is a view type over a screen |
| Role | engine | the four seats per space |
| Role Permission for Page and Report *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| Role Profile | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| SMS Log | — | platform plumbing — logs, schema, sessions, the scheduler |
| SMS Settings *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| Scheduled Job Log | log | named once, only to be excluded |
| Scheduled Job Type | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| Scheduler Event | — | platform plumbing — logs, schema, sessions, the scheduler |
| Security Settings *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| Server Script | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| Session Default Settings *(single)* | — | platform plumbing — logs, schema, sessions, the scheduler |
| Submission Queue | — | platform plumbing — logs, schema, sessions, the scheduler |
| Success Action | — | platform plumbing — logs, schema, sessions, the scheduler |
| System Settings *(single)* | engine | the site's own clock and number format |
| Translation | — | shipped `.po` files instead |
| User | engine | who is reading |
| User Group | — | platform plumbing — logs, schema, sessions, the scheduler |
| User Invitation | — | platform plumbing — logs, schema, sessions, the scheduler |
| User Permission | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| User Type | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| Version | service | the record's history strip |
| View Log | log | named once, only to be excluded |

## Custom (4)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Client Script | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| Custom Field | engine | the four fields we add to ERPNext |
| Customize Form *(single)* | — | the desk's customise-form surface |
| Property Setter | engine | a default we change without forking |

## Desk (37)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Bulk Update *(single)* | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Calendar View | — | a calendar is a view type |
| Console Log | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Custom HTML Block | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Custom Sidebar | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Custom Workspace | — | same |
| Dashboard | — | a dashboard is a view type over a screen |
| Dashboard Chart | — | a dashboard is a view type over a screen's own rows |
| Dashboard Chart Source | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Dashboard Settings | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Desktop Icon | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Desktop Layout | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Desktop Settings *(single)* | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Dock | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Document Template | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Event | service | the reader's own diary entries |
| Form Tour | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Global Search Settings *(single)* | — | says what goes in `__global_search`, which `finding.py` does not read — it searches the screens instead |
| Kanban Board | — | a board is a view type here, not a stored document |
| List Filter | — | `OneSpace Saved View` instead |
| List View Settings | — | `OneSpace Saved View` instead |
| Module Onboarding | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Note | — | OneWriter instead |
| Notification Log | service | the bell |
| Notification Settings | service | per-person delivery choices |
| Notification Type | service | the kinds the bell groups by |
| Number Card | — | same — a tile on a dashboard view |
| Onboarding Step | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Route History | log | named once, only to be excluded |
| Sidebar | — | the Frappe desk's own furniture; the SPA replaces it outright |
| System Console *(single)* | — | the Frappe desk's own furniture; the SPA replaces it outright |
| System Health Report *(single)* | — | the Frappe desk's own furniture; the SPA replaces it outright |
| Tag | service | the workspace's tag vocabulary |
| Tag Link | service | via Frappe's own `DocTags` |
| ToDo | service | an assignment, and OneTask's store |
| Workspace | — | the desk sidebar; the SPA's rail comes from the space manifest |
| Workspace Sidebar | — | the Frappe desk's own furniture; the SPA replaces it outright |

## Email (13)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Auto Email Report | — | not built |
| Document Follow | service | whether to notify a follower |
| Email Account | service | a mailbox |
| Email Domain | service | the domain behind it |
| Email Flag Queue | — | mail plumbing OneMail does not surface |
| Email Group | — | mail plumbing OneMail does not surface |
| Email Group Member | — | mail plumbing OneMail does not surface |
| Email Queue | service | what is on its way out |
| Email Rule | — | mail plumbing OneMail does not surface |
| Email Template | service | a canned reply |
| Email Unsubscribe | service | who asked to be left alone |
| Notification | service | the workspace's own alerts |
| Unhandled Email | — | mail plumbing OneMail does not surface |

## Geo (2)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Country | granted | OneCRM, OneHR — a picker |
| Currency | granted | five spaces — a picker |

## Integrations (18)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Connected App | — | third-party plumbing, configured by an operator if at all |
| Geolocation Settings *(single)* | — | third-party plumbing, configured by an operator if at all |
| Google Calendar | — | not wired |
| Google Contacts | — | not wired |
| Google Settings *(single)* | — | third-party plumbing, configured by an operator if at all |
| Integration Request | — | third-party plumbing, configured by an operator if at all |
| LDAP Settings *(single)* | — | third-party plumbing, configured by an operator if at all |
| OAuth Authorization Code | — | third-party plumbing, configured by an operator if at all |
| OAuth Bearer Token | — | third-party plumbing, configured by an operator if at all |
| OAuth Client | — | third-party plumbing, configured by an operator if at all |
| OAuth Provider Settings *(single)* | — | third-party plumbing, configured by an operator if at all |
| OAuth Settings *(single)* | — | third-party plumbing, configured by an operator if at all |
| Push Notification Settings *(single)* | — | third-party plumbing, configured by an operator if at all |
| Slack Webhook URL | — | third-party plumbing, configured by an operator if at all |
| Social Login Key | — | third-party plumbing, configured by an operator if at all |
| Token Cache | — | third-party plumbing, configured by an operator if at all |
| Webhook | refused | `NEVER_GRANTED` — power over permissions, schema or code |
| Webhook Request Log | — | third-party plumbing, configured by an operator if at all |

## Printing (8)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Letter Head | service | the paper a document prints on |
| Network Printer Settings | — | print internals |
| Print Format | service | the format a screen prints with |
| Print Format Field Template | — | print internals |
| Print Format Snippet | — | print internals |
| Print Heading | — | print internals |
| Print Settings *(single)* | service | page size and orientation |
| Print Style | service | the workspace's print style |

## Website (24)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| About Us Settings *(single)* | — | the portal and the website builder; we ship no portal |
| Color | — | brand colours come from the space manifest |
| Contact Us Settings *(single)* | — | the portal and the website builder; we ship no portal |
| Discussion Reply | — | the portal and the website builder; we ship no portal |
| Discussion Topic | — | the portal and the website builder; we ship no portal |
| Help Article | — | the portal and the website builder; we ship no portal |
| Help Category | — | the portal and the website builder; we ship no portal |
| Personal Data Deletion Request | — | the portal and the website builder; we ship no portal |
| Personal Data Download Request | — | the portal and the website builder; we ship no portal |
| Portal Settings *(single)* | — | the portal and the website builder; we ship no portal |
| UTM Campaign | granted | OneCRM — a picker on the deal |
| UTM Medium | granted | OneCRM — a picker on the deal |
| UTM Source | **screen** | OneCRM `sources` |
| Web Form | service | `oneforms/` — a form is a door into a doctype, and this is the door |
| Web Form Request | service | `oneforms/invite.py` — one recipient's key, its expiry, what it pre-fills and what it may touch |
| Web Page | — | the portal and the website builder; we ship no portal |
| Web Page View | — | the portal and the website builder; we ship no portal |
| Web Template | — | the portal and the website builder; we ship no portal |
| Website Route Meta | — | the portal and the website builder; we ship no portal |
| Website Script *(single)* | — | the portal and the website builder; we ship no portal |
| Website Settings *(single)* | service | the workspace's name and logo |
| Website Sidebar | — | the portal and the website builder; we ship no portal |
| Website Slideshow | — | the portal and the website builder; we ship no portal |
| Website Theme | — | the portal and the website builder; we ship no portal |

## Workflow (5)

| Doctype | In the SPA | How, or why not |
|---|---|---|
| Workflow | service | the state machine an app ships over `docstatus` — `docflow.py` reads it through `get_workflow` and drives it with `apply_workflow` |
| Workflow Action | service | `waiting.py` — the approvals inbox, and Frappe's own permission conditions on it are the whole of the scoping |
| Workflow Action Master | — | the named actions a transition offers; the framework resolves them and nothing here names one |
| Workflow State | service | the colour of a state chip |
| Workflow Transition Tasks | — | Frappe's own bookkeeping for a transition in flight |

## Child tables

107 of the 301 are child tables, which are never a screen anywhere — a child table is part of its parent's form. 9 of them the SPA reads directly:

* `Communication Link` — which record a message is filed against
* `Contact Email` — the addresses behind a contact
* `DocField` — the columns a screen offers
* `DocPerm` — read beside it
* `Dynamic Link` — contact → party resolution
* `Web Form Field` — which of a doctype's fields a form carries, and in what order
* `Event Participants` — the join that makes a diary mine
* `Has Role` — who holds a seat
* `IMAP Folder` — the folders in the rail
* `User Email` — which mailbox is whose

The other 97 are untouched.
