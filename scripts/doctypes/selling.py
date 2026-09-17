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
