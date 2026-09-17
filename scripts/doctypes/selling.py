"""Selling: the stages a pipeline is made of, and what a deal does between them.

`docs/ONECRM.md` is the argument. OneCRM is ERPNext's CRM module the way
OnePeople is Frappe HR: their `Lead` is the lead, their `Opportunity` is the
deal, their `Quotation` is the quote. Nothing here is a second CRM.

What is here is the one thing their schema cannot express, and it is the same
thing `One Task State` is for a board of work. ERPNext's `Sales Stage` is a row
with a name and nothing else — no order, no colour, no meaning — so a board
drawn from it comes out in the order the values happened to arrive in, and the
engine cannot tell which column means *won*. Its `status` is a fixed Select of
six words, three of which describe a quotation rather than a deal.

Frappe CRM reached the same conclusion from the other direction: `CRM Deal
Status` carries a colour, a position, a type and a probability, and arriving at
the shape twice independently is the best argument for it there is.

So a stage is a **row**: a team names its own columns, orders them by dragging
a number, and the engine still knows which one means won because the row says
so. `status` and `probability` stay ERPNext's and are written *from* the stage
— one direction, one path, on save, in `onecrm/deal.py`.
"""

from .spec import MANAGER_PERMS, column, doctype, f, section

MODULE = "OneCRM"
TENANT = dict(app="tenant", module=MODULE, perms=MANAGER_PERMS)


# --------------------------------------------------------------------------- #
# A stage — which is how a pipeline gets its own columns without a schema change
#
# `category` is the part that earns its keep. A workspace may call its last
# column Won, Signed, Booked or Instructed; a forecast that had to know those
# four would be a forecast that breaks on the fifth. And the *order* is on the
# row rather than in a manifest, because a manifest is a second place for it to
# be true — which is what the declared `STAGES` list was, and why moving a
# stage used to mean a deployment.
# --------------------------------------------------------------------------- #
doctype(
    "One Deal Stage",
    autoname="field:stage_name",
    title_field="stage_name",
    search_fields="category",
    **TENANT,
    fields=[
        f("stage_name", "Data", "Name", reqd=1, unique=1, in_list_view=1,
          description="What this column is called on the pipeline. The id too, "
                      "so a deal points at the word a team chose."),
        f("category", "Select", reqd=1, default="Ongoing", in_list_view=1,
          options="Open\nOngoing\nOn hold\nWon\nLost",
          description="What it means, for the code that has to ask. ERPNext's "
                      "own `status` is written from this, so a deal in a "
                      "column called Instructed is Converted over there and "
                      "the accounting side agrees without being told."),
        f("probability", "Percent", "Probability", default="0", in_list_view=1,
          description="How likely a deal at this stage is to close, as a "
                      "starting point. Written onto the deal when it arrives "
                      "here and editable afterwards: the stage is what the "
                      "desk assumes and the number on the deal is what the "
                      "person selling it says."),
        column("cb_stage_look"),
        f("colour", "Select", "Colour", default="gray",
          options="gray\nblue\ngreen\namber\nred\nviolet\ncyan\norange\npink",
          description="The dot beside it, and the tint of its column."),
        f("position", "Int", "Position", default="0", in_list_view=1,
          description="Left to right on the pipeline. Ties break on the name. "
                      "The board reads this rather than a declared list — "
                      "`views._columns_from` — so moving a stage is one drag "
                      "and not a release."),
        section("sec_stage_what"),
        f("description", "Small Text", "Description",
          description="What has to be true for a deal to be here, for the "
                      "people who did not invent the pipeline."),
    ],
)


# --------------------------------------------------------------------------- #
# A stage change — where a deal has been, and how long it sat there
#
# `docs/ONECRM.md` stage 2, and the question a pipeline review is actually
# held to answer: not "what is in Negotiation" but "what has been in
# Negotiation for forty days". Neither ERPNext nor OneCRM could answer it at
# all, and Frappe CRM's `CRM Status Change Log` is where the shape comes from.
#
# One row per stage *entered*, rather than one per transition. The two carry
# the same information and this one reads better on a record: a column of
# "New, 3 days · Qualifying, 40 days · Proposal, still here" is a history
# somebody can scan, where from/to pairs are a diff nobody reads.
#
# The row is written by `onecrm/deal.py` and by nothing else. It is a log, so
# it is `read_only` all the way across: a history somebody can edit is not one.
# --------------------------------------------------------------------------- #
doctype(
    "One Stage Change",
    istable=1,
    **TENANT,
    fields=[
        f("stage", "Link", "Stage", options="One Deal Stage", reqd=1,
          in_list_view=1, read_only=1,
          description="The column entered. A Link and not a copy of the name, "
                      "so renaming a stage renames it here too."),
        f("entered_on", "Datetime", "Entered", reqd=1, in_list_view=1,
          read_only=1),
        f("left_on", "Datetime", "Left", in_list_view=1, read_only=1,
          description="Empty on the row for the stage a deal is in now, which "
                      "is what makes 'still here' answerable without a second "
                      "field saying which row is current."),
        f("days", "Float", "Days", default="0", precision="2", in_list_view=1,
          read_only=1,
          description="How long it sat there, filled on the way out. Days and "
                      "not a Duration: a pipeline is read in days and a "
                      "Duration renders as '3d 4h 12m', which is a precision "
                      "nobody has about a deal."),
        f("moved_by", "Link", "Moved by", options="User", read_only=1),
    ],
)


# --------------------------------------------------------------------------- #
# A call — the commonest thing on a sales desk, and the one with nowhere to live
#
# `docs/ONECRM.md` stage 5. Frappe CRM integrates Twilio and Exotel, and the
# part of that worth copying is the part that needs neither: its `CRM Call Log`
# carries a `telephony_medium` of **Manual**, because most of the value of a
# call log is having one at all. A person rings somebody, writes three lines,
# and it is on the record for ever — that works with a desk phone, a mobile and
# a switchboard nobody has heard of.
#
# Not only for a deal. `about_doctype`/`about_name` is a dynamic pair, so a
# call about a job, a tenant, a patient or a supplier is the same row: every
# app in this product has to work for every business, and a call is the least
# industry-specific thing there is.
# --------------------------------------------------------------------------- #
doctype(
    "One Call",
    autoname="naming_series:",
    title_field="with_whom",
    search_fields="with_whom,number,about_name",
    track_changes=1,
    **TENANT,
    fields=[
        f("naming_series", "Data", "Series", hidden=1, default="CALL-.#####"),
        f("with_whom", "Data", "With", reqd=1, in_list_view=1,
          description="Who was on the other end, as a person would say it. "
                      "Data and not a Link to Contact: half the calls anybody "
                      "makes are to somebody who is not in the address book "
                      "yet, and a field that refuses them is a field people "
                      "stop filling in."),
        f("way", "Select", "Direction", reqd=1, default="Outgoing",
          options="Outgoing\nIncoming", in_list_view=1),
        f("number", "Data", "Number", options="Phone", in_list_view=1),
        f("contact", "Link", "Contact", options="Contact",
          description="Where the person *is* in the address book. Optional and "
                      "never required — see `with_whom`."),
        column("cb_call_when"),
        f("at", "Datetime", "When", reqd=1, in_list_view=1),
        f("minutes", "Int", "Minutes", default="0", in_list_view=1,
          description="How long it lasted. Minutes because every other unit is "
                      "an argument about seconds."),
        f("outcome", "Select", "Outcome", reqd=1, default="Answered",
          options="Answered\nNo answer\nVoicemail\nWrong number",
          in_list_view=1,
          description="Four words, and the three that are not Answered are the "
                      "point: a list of attempts is what tells you somebody is "
                      "avoiding you."),
        f("person", "Link", "Made by", options="User", reqd=1,
          description="Who on this side. Whoever logged it, unless somebody "
                      "logs a colleague's call for them."),
        section("sec_call_about"),
        f("about_doctype", "Link", "About", options="DocType",
          description="What the call was about — a deal, a job, a tenant. A "
                      "dynamic pair rather than a link to one doctype, because "
                      "a call is the least industry-specific thing there is."),
        f("about_name", "Dynamic Link", "Record", options="about_doctype",
          in_list_view=1),
        f("note", "Small Text", "What was said",
          description="Three lines, written while it is fresh. Not a "
                      "transcript and not a Text Editor: a call note somebody "
                      "has to format is a call note nobody writes."),
    ],
)


# --------------------------------------------------------------------------- #
# Answering, measured — `docs/ONECRM.md` stage 6
#
# `CRM Service Level Agreement` is 359 lines and the best-built thing in Frappe
# CRM: a condition deciding which records it applies to, a first-response
# target, working hours per weekday, a holiday list, and rolling responses.
# This is the same idea at a third of the surface, and the two things dropped
# are dropped on purpose.
#
# **No condition expression.** Theirs stores a Python condition on the row and
# evaluates it. A doctype an operator can edit must never become a doctype an
# operator can run code from — the argument `spaceview/actions.py` makes about
# declarations — so this narrows by one field and one value, which covers "web
# leads" and "government deals" and refuses everything that would need an
# interpreter.
#
# **No priorities.** Theirs has a priority table with a target each; this has
# one number. A desk that genuinely answers urgent leads faster makes a second
# target with a `when_field` — which is the same thing, spelled as a row
# somebody can read.
#
# What is kept is the part that is hard and that everybody gets wrong: a lead
# that arrives at six on Friday evening is not late at nine on Saturday
# morning. That takes a working week and a holiday list and nothing less.
# --------------------------------------------------------------------------- #
doctype(
    "One Working Day",
    istable=1,
    **TENANT,
    fields=[
        f("day", "Select", "Day", reqd=1, in_list_view=1,
          options="Monday\nTuesday\nWednesday\nThursday\nFriday\nSaturday\nSunday"),
        f("works", "Check", "A working day", default="1", in_list_view=1),
        f("from_time", "Time", "From", default="09:00:00", in_list_view=1),
        f("to_time", "Time", "To", default="17:00:00", in_list_view=1,
          description="The window the clock runs in. A target of four hours "
                      "against a seven-hour day is half a day and not four "
                      "hours of wall clock — which is the whole point of "
                      "measuring in working time."),
    ],
)


doctype(
    "One Response Target",
    autoname="field:target_name",
    title_field="target_name",
    search_fields="applies_to,hours",
    track_changes=1,
    **TENANT,
    fields=[
        f("target_name", "Data", "Name", reqd=1, unique=1, in_list_view=1),
        f("enabled", "Check", "In use", default="1", in_list_view=1),
        f("applies_to", "Link", "Applies to", options="DocType", reqd=1,
          in_list_view=1,
          description="Which records are measured. A Link to DocType and not a "
                      "Select of two: a target over a job, a ticket or an "
                      "application is the same row, and a CRM is only where "
                      "somebody asked for it first."),
        f("position", "Int", "Order", default="0",
          description="Which target wins when two of them fit. Lowest first, "
                      "so the narrow one goes above the catch-all."),
        column("cb_target_when"),
        f("when_field", "Data", "Only when",
          description="A fieldname on the doctype above. Left blank, the "
                      "target applies to all of them. Deliberately a field "
                      "and a value rather than a condition: a row an operator "
                      "edits must not be a row an operator runs code from."),
        f("when_value", "Data", "Is"),
        section("sec_target_clock", "The clock"),
        f("hours", "Float", "Answer within (working hours)", reqd=1,
          default="4", precision="2", in_list_view=1),
        f("holiday_list", "Link", "Holiday list", options="Holiday List",
          description="Days the clock does not run at all. ERPNext's own, so a "
                      "workspace keeps one list for payroll, projects and this."),
        f("week", "Table", "The working week", options="One Working Day",
          description="Empty means every day, all day — which is the honest "
                      "reading of a desk that has not said otherwise, and is "
                      "what a support line that runs at night actually wants."),
    ],
)
