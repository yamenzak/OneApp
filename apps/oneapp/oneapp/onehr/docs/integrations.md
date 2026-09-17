# Integrations

## HRMS — the whole schema

This module owns no doctypes; every noun above is HRMS's. What is here is
views, four custom fields, about forty declared verbs, and the two subclasses
`boarding.py` registers.

`docs/ERP-SPACES.md` is the argument: HRMS ships around two hundred doctypes,
the desk cannot tell a place-a-person-works from an accounting artefact, so its
HR workspace is a wall of links and the first thing every HR officer does is
learn which nine of them they use. Twenty-nine screens under seven headings is
the choice, and the choice is the product.

**Two things are only wrong when both apps are installed**, and the README's §8
names them. They are the reason this space exists rather than a Frappe HR
deployment.

## ERPNext

Underneath HRMS. `Department`, `Cost Center`, `Account` and `Company` are
ERPNext's, which is why the space declares `requires_apps: "erpnext,hrms"` — a
site with one and not the other is a site where half these screens refuse their
own link fields.

`Supplier` is Read for a Manager, because an expense claim can name one.

## Frappe

**`Task` and `ToDo`** — every step of an onboarding or an exit is a Task HRMS
assigns as it creates it, and an assignment already notifies.

**`User`** is the bridge `custom_person` crosses, through
`Employee.user_id`.

**`Notification`** is where the sixteen alerts land, as the workspace's own.

## The engine (`onespace`)

* **`mine.py`** — `@me` and `@me:employee`. A twin screen is the same
  resolution the assistant uses, so **My leave** cannot come apart from "my
  leave".
* **`alerts.py`** — `addressable` is the function `custom_person` exists to
  satisfy. `sync._alert_role` composes a Frappe role name from a label,
  because a manifest cannot write one down.
* **`spaceview/actions.py`** — the forty verbs.
* **The record shell and the showcase** — a person is a face, a reporting line
  and their own tabs, drawn by the same showcase a project uses.
* **`onespace_chat_tools`** — the hook `assistant.py` registers through.

## OneCalendar

Leave, interviews and shifts are on somebody's week because this space's
manifest declares calendars over them. `Interview Detail.interviewer` is the
one place a doctype's shape shows through the merge — whose a row is lives in a
child table for that one.

## OneMail

**Hiring is deliberately absent from the alerts**, and mail is the reason.
Everything worth saying in hiring is said to a *candidate* — your interview is
on Tuesday, your offer is attached — and a candidate is not a login.
`Job Applicant.email_id` is the only address there is, which makes it mail
rather than an alert, with everything mail brings that an in-app row does not
have to think about: a template somebody approves, an unsubscribe, a record of
what was sent.

## OneCloud

An employee's documents and a candidate's CV are `File` rows. Nothing here does
anything about it.

## OneAI

`ai.md`. Two tools, and they exist because the engine's eight could not answer
the two questions this module is for.

## OneLegal

Nothing of its own — what a workspace does with personnel data is the
platform's clause rather than this space's.
